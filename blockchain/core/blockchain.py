# blockchain/core/blockchain.py

import time
import json
import os
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from .block import Block, GenesisBlock
from .transaction import Transaction, TransactionType
from .state import BlockchainState

if TYPE_CHECKING:
    from ..consensus.base import BaseConsensus

class Blockchain:
    """
    Main Blockchain class with pluggable consensus and multi-level permissions
    """
    
    def __init__(
        self,
        chain_id: str,
        consensus_mechanism: 'BaseConsensus',
        genesis_validators: Optional[List[dict]] = None,
        data_dir: Optional[str] = None,
        permission_levels: Optional[int] = None,
        creator_address: Optional[str] = None,
        level_names: Optional[List[str]] = None
    ):
        self.chain_id = chain_id
        self.consensus = consensus_mechanism
        self.data_dir = data_dir or f"./data/{chain_id}"
        
        # Initialize storage
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Blockchain data
        self.blocks: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        
        # State management
        self.state = BlockchainState(chain_id)
        
        # Multi-level permission system
        self.permission_system: Optional['MultiLevelPermissionSystem'] = None
        if permission_levels and creator_address:
            from ..permissions.multi_level import MultiLevelPermissionSystem
            self.permission_system = MultiLevelPermissionSystem(
                num_levels=permission_levels,
                creator_address=creator_address,
                level_names=level_names
            )
            print(f"Multi-level permission system enabled: {permission_levels} levels")
        
        # Initialize consensus with this blockchain
        self.consensus.initialize(self)
        
        # Load or create genesis
        if not self._load_chain():
            self._create_genesis(genesis_validators or [])
    
    def _create_genesis(self, validators: List[dict]) -> None:
        """Create genesis block"""
        genesis = GenesisBlock(
            chain_id=self.chain_id,
            initial_validators=validators
        )
        
        # Initialize validators in state
        from .state import ValidatorState
        for val in validators:
            validator = ValidatorState(
                address=val['address'],
                pub_key=val['pub_key'],
                power=val.get('power', 10),
                name=val.get('name', '')
            )
            self.state.add_validator(validator)
        
        self.blocks.append(genesis)
        self.state.height = 0
        self.state.last_block_hash = genesis.hash
        self.state.calculate_app_hash()
        
        self._save_chain()
        print(f"Genesis block created for chain {self.chain_id}")
    
    def get_height(self) -> int:
        return len(self.blocks) - 1
    
    def get_last_block(self) -> Block:
        return self.blocks[-1] if self.blocks else None
    
    def get_block(self, height: int) -> Optional[Block]:
        if 0 <= height < len(self.blocks):
            return self.blocks[height]
        return None
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        for block in self.blocks:
            if block.hash == block_hash:
                return block
        return None
    
    def add_transaction(self, transaction: Transaction) -> bool:
        if not self._verify_transaction(transaction):
            return False
        
        for tx in self.pending_transactions:
            if tx.hash() == transaction.hash():
                return False
        
        self.pending_transactions.append(transaction)
        return True
    
    def _verify_transaction(self, transaction: Transaction) -> bool:
        """Verify transaction validity with full signature checks"""
        
        # 1. Skip checks for GENESIS transactions
        if transaction.tx_type == TransactionType.GENESIS:
            return True

        # 2. Check Signature and Public Key
        # Now we implement the logic that was previously a TODO
        if transaction.signature:
            if not transaction.public_key:
                print(f"[Validation Fail] Transaction {transaction.hash()[:8]} has signature but no public key.")
                return False
            
            # Verify the Public Key belongs to the Sender
            from ..crypto.keys import address_from_public_key
            derived_address = address_from_public_key(transaction.public_key)
            if derived_address != transaction.sender:
                print(f"[Validation Fail] Public key derives to {derived_address[:8]}, but sender is {transaction.sender[:8]}")
                return False

            # Verify the Signature itself
            if not transaction.verify_signature():
                print(f"[Validation Fail] Invalid signature for tx {transaction.hash()[:8]}")
                return False
        else:
            # Reject unsigned transactions (unless specific types allow it, but generally unsafe)
            print(f"[Validation Fail] Transaction {transaction.hash()[:8]} is not signed.")
            return False
        
        # 3. Check nonce
        account = self.state.get_account(transaction.sender)
        if transaction.nonce < account.nonce:
            print(f"[Validation Fail] Invalid nonce {transaction.nonce} (expected >= {account.nonce})")
            return False
        
        # 4. Check permissions
        if not self._check_transaction_permissions(transaction):
            print(f"[Validation Fail] Permission denied for {transaction.sender[:8]}")
            return False
        
        return True
    
    def _check_transaction_permissions(self, transaction: Transaction) -> bool:
        """Check if sender has permission to execute transaction"""
        permission_map = {
            TransactionType.TRANSFER: "can_transfer",
            TransactionType.VALIDATOR_UPDATE: "can_update_validators",
            TransactionType.PERMISSION_GRANT: "can_grant_permissions",
            TransactionType.PERMISSION_REVOKE: "can_revoke_permissions",
        }
        
        required_permission = permission_map.get(transaction.tx_type)
        if required_permission:
            has_permission = self.state.has_permission(transaction.sender, required_permission)
            if not has_permission:
                return False
        
        if self.permission_system:
            if 'security_level' in transaction.data:
                required_level = transaction.data['security_level']
                user_level = self.permission_system.get_user_level(transaction.sender)
                if user_level < required_level:
                    return False
        
        return True
    
    def propose_block(self, validator_address: str, private_key: str) -> Optional[Block]:
        validator = self.state.get_validator(validator_address)
        if not validator or not validator.active:
            return None
        
        transactions = self.consensus.select_transactions(
            self.pending_transactions,
            validator_address
        )
        
        last_block = self.get_last_block()
        consensus_data = self.consensus.prepare_consensus_data(
            validator_address,
            last_block
        )
        
        block = Block(
            height=self.get_height() + 1,
            previous_hash=last_block.hash,
            transactions=transactions,
            validator_address=validator_address,
            consensus_data=consensus_data
        )
        
        from ..crypto.signatures import sign_message
        signature = sign_message(block.merkle_root, private_key)
        block.finalize(signature)
        
        return block
    
    def add_block(self, block: Block) -> bool:
        if not self._verify_block(block):
            print(f"Block verification failed: {block}")
            return False
        
        if not self.consensus.validate_block(block, self.state):
            print(f"Consensus validation failed: {block}")
            return False
        
        if not self._execute_block_transactions(block):
            print(f"Transaction execution failed: {block}")
            return False
        
        self.blocks.append(block)
        
        self.state.height = block.height
        self.state.last_block_hash = block.hash
        self.state.calculate_app_hash()
        
        executed_hashes = {tx.hash() for tx in block.transactions}
        self.pending_transactions = [
            tx for tx in self.pending_transactions
            if tx.hash() not in executed_hashes
        ]
        
        validator = self.state.get_validator(block.validator_address)
        if validator:
            validator.total_blocks_proposed += 1
        
        self.consensus.on_block_committed(block, self.state)
        self._save_chain()
        
        print(f"Block {block.height} added by {block.validator_address[:8]}...")
        return True
    
    def _verify_block(self, block: Block) -> bool:
        if block.height != self.get_height() + 1:
            return False
        
        last_block = self.get_last_block()
        if block.previous_hash != last_block.hash:
            return False
        
        if not block.verify_merkle_root():
            return False
        
        for tx in block.transactions:
            if not self._verify_transaction(tx):
                return False
        
        return True
    
    def _execute_block_transactions(self, block: Block) -> bool:
        snapshot = self.state.snapshot()
        try:
            for tx in block.transactions:
                if tx.tx_type == TransactionType.TRANSFER:
                    self._execute_transfer(tx)
                elif tx.tx_type == TransactionType.VALIDATOR_UPDATE:
                    self._execute_validator_update(tx)
                elif tx.tx_type == TransactionType.PERMISSION_GRANT:
                    self._execute_permission_grant(tx)
                elif tx.tx_type == TransactionType.PERMISSION_REVOKE:
                    self._execute_permission_revoke(tx)
                elif tx.tx_type == TransactionType.GENESIS:
                    pass
                else:
                    self._execute_custom_transaction(tx)
            return True
        except Exception as e:
            self.state = snapshot
            print(f"Transaction execution error: {e}")
            return False
    
    def _execute_transfer(self, tx: Transaction) -> None:
        if tx.inputs and tx.outputs:
            from_addr = tx.inputs[0].from_address
            to_addr = tx.outputs[0].to_address
            amount = tx.outputs[0].amount
            
            if not self.state.transfer(from_addr, to_addr, amount):
                raise Exception(f"Transfer failed: insufficient balance")
    
    def _execute_validator_update(self, tx: Transaction) -> None:
        from .state import ValidatorState
        validator_addr = tx.data['validator_address']
        action = tx.data['action']
        
        if action == "add":
            validator = ValidatorState(
                address=validator_addr,
                pub_key=tx.data.get('pub_key', ''),
                power=tx.data.get('power', 10)
            )
            self.state.add_validator(validator)
        elif action == "remove":
            self.state.remove_validator(validator_addr)
    
    def _execute_permission_grant(self, tx: Transaction) -> None:
        target = tx.data['target_address']
        action = tx.data.get('action', 'grant')

        # Standard Permission
        if 'permission' in tx.data and action == 'grant':
            permission = tx.data['permission']
            self.state.grant_permission(target, permission)
            print(f"Granted '{permission}' to {target[:8]}...")

        # Multi-Level Promotion
        if self.permission_system and 'new_level' in tx.data:
            new_level = tx.data['new_level']
            success = self.permission_system.promote_user(tx.sender, target, new_level)
            if success:
                print(f"Promoted {target[:8]}... to Level {new_level}")
            else:
                print(f"Promotion failed: {tx.sender[:8]}... cannot promote {target[:8]}... to {new_level}")

    def _execute_permission_revoke(self, tx: Transaction) -> None:
        target = tx.data['target_address']
        action = tx.data.get('action', 'revoke')
        
        # Standard Permission
        if 'permission' in tx.data and action == 'revoke':
            permission = tx.data['permission']
            self.state.revoke_permission(target, permission)
            print(f"Revoked '{permission}' from {target[:8]}...")

        # Multi-Level Demotion
        if self.permission_system and 'new_level' in tx.data and action == 'set_level':
             new_level = tx.data['new_level']
             success = self.permission_system.demote_user(tx.sender, target, new_level)
             if success:
                 print(f"Demoted {target[:8]}... to Level {new_level}")
    
    def _execute_custom_transaction(self, tx: Transaction) -> None:
        pass
    
    def _save_chain(self) -> None:
        blocks_file = os.path.join(self.data_dir, "blocks.json")
        with open(blocks_file, 'w') as f:
            json.dump([block.to_dict() for block in self.blocks], f, indent=2)
        
        state_file = os.path.join(self.data_dir, "state.json")
        with open(state_file, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)
        
        if self.permission_system:
            perm_file = os.path.join(self.data_dir, "permissions.json")
            with open(perm_file, 'w') as f:
                json.dump(self.permission_system.to_dict(), f, indent=2)
    
    def _load_chain(self) -> bool:
        blocks_file = os.path.join(self.data_dir, "blocks.json")
        state_file = os.path.join(self.data_dir, "state.json")
        
        if not os.path.exists(blocks_file) or not os.path.exists(state_file):
            return False
        
        try:
            with open(blocks_file, 'r') as f:
                blocks_data = json.load(f)
                self.blocks = [Block.from_dict(b) for b in blocks_data]
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
                self.state = BlockchainState.from_dict(state_data)
            
            perm_file = os.path.join(self.data_dir, "permissions.json")
            if os.path.exists(perm_file):
                with open(perm_file, 'r') as f:
                    perm_data = json.load(f)
                    from ..permissions.multi_level import MultiLevelPermissionSystem
                    self.permission_system = MultiLevelPermissionSystem.from_dict(perm_data)
            
            print(f"Loaded chain {self.chain_id} with {len(self.blocks)} blocks")
            return True
            
        except Exception as e:
            print(f"Error loading chain: {e}")
            return False
    
    def get_chain_info(self) -> dict:
        info = {
            'chain_id': self.chain_id,
            'height': self.get_height(),
            'last_block_hash': self.state.last_block_hash,
            'app_hash': self.state.app_hash,
            'total_transactions': sum(len(b.transactions) for b in self.blocks),
            'pending_transactions': len(self.pending_transactions),
            'validators': len(self.state.get_active_validators()),
            'consensus': self.consensus.__class__.__name__
        }
        
        if self.permission_system:
            info['permission_system'] = {
                'enabled': True,
                'num_levels': self.permission_system.num_levels,
                'total_users': len(self.permission_system.user_levels),
                'data_items': len(self.permission_system.data_store)
            }
        else:
            info['permission_system'] = {'enabled': False}
        
        return info
    
    # Wrapper methods for Permission System
    def store_data(self, data_id: str, content: any, security_level: int, owner_address: str, metadata: Optional[Dict] = None) -> bool:
        if not self.permission_system:
            return False
        return self.permission_system.store_data(data_id, content, security_level, owner_address, metadata)
    
    def access_data(self, user_address: str, data_id: str) -> Optional[any]:
        if not self.permission_system:
            return None
        return self.permission_system.access_data(user_address, data_id)
    
    def promote_user(self, promoter_address: str, target_address: str, new_level: int) -> bool:
        if not self.permission_system:
            return False
        return self.permission_system.promote_user(promoter_address, target_address, new_level)
    
    def demote_user(self, demoter_address: str, target_address: str, new_level: int) -> bool:
        if not self.permission_system:
            return False
        return self.permission_system.demote_user(demoter_address, target_address, new_level)
    
    def get_user_permission_level(self, address: str) -> Optional[int]:
        if not self.permission_system:
            return None
        return self.permission_system.get_user_level(address)
    
    def get_accessible_data(self, user_address: str) -> List:
        if not self.permission_system:
            return []
        return self.permission_system.get_accessible_data(user_address)
    
    def get_permission_audit_log(self, actor: Optional[str] = None, action: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        if not self.permission_system:
            return []
        return self.permission_system.get_audit_log(actor, action, limit)