import time
import json
import os
# 1. Add TYPE_CHECKING here
from typing import List, Optional, Dict, Any, Type, TYPE_CHECKING

from .block import Block, GenesisBlock
from .transaction import Transaction, TransactionType
from .state import BlockchainState

# 2. Add this block to fix the "Not Defined" error safely
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
        """
        Initialize blockchain
        
        Args:
            chain_id: Unique identifier for this blockchain
            consensus_mechanism: Consensus mechanism instance
            genesis_validators: Initial validator set
            data_dir: Directory for blockchain data storage
            permission_levels: Number of permission levels (2-10) for multi-level system
            creator_address: Address of blockchain creator (required if permission_levels set)
            level_names: Optional names for permission levels
        """
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
        """Get current blockchain height"""
        return len(self.blocks) - 1
    
    def get_last_block(self) -> Block:
        """Get the last block"""
        return self.blocks[-1] if self.blocks else None
    
    def get_block(self, height: int) -> Optional[Block]:
        """Get block by height"""
        if 0 <= height < len(self.blocks):
            return self.blocks[height]
        return None
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get block by hash"""
        for block in self.blocks:
            if block.hash == block_hash:
                return block
        return None
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to pending pool"""
        # Verify transaction
        if not self._verify_transaction(transaction):
            return False
        
        # Check if already in pending
        for tx in self.pending_transactions:
            if tx.hash() == transaction.hash():
                return False
        
        self.pending_transactions.append(transaction)
        return True
    
    def _verify_transaction(self, transaction: Transaction) -> bool:
        """Verify transaction validity"""
        # Check signature
        if transaction.signature:
            # TODO: Implement proper signature verification with public keys
            pass
        
        # Check nonce
        account = self.state.get_account(transaction.sender)
        if transaction.nonce < account.nonce:
            return False
        
        # Check permissions (both traditional and multi-level)
        if not self._check_transaction_permissions(transaction):
            return False
        
        return True
    
    def _check_transaction_permissions(self, transaction: Transaction) -> bool:
        """Check if sender has permission to execute transaction"""
        # Define required permissions for each transaction type
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
        
        # Check multi-level permissions if enabled
        if self.permission_system:
            # For transactions involving data, check security clearance
            if 'security_level' in transaction.data:
                required_level = transaction.data['security_level']
                user_level = self.permission_system.get_user_level(transaction.sender)
                if user_level < required_level:
                    return False
        
        return True
    
    def propose_block(self, validator_address: str, private_key: str) -> Optional[Block]:
        """Propose a new block"""
        # Check if validator
        validator = self.state.get_validator(validator_address)
        if not validator or not validator.active:
            return None
        
        # Let consensus decide which transactions to include
        transactions = self.consensus.select_transactions(
            self.pending_transactions,
            validator_address
        )
        
        # Create block
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
        
        # Sign block
        from ..crypto.signatures import sign_message
        signature = sign_message(block.merkle_root, private_key)
        block.finalize(signature)
        
        return block
    
    def add_block(self, block: Block) -> bool:
        """Add block to blockchain after consensus validation"""
        # Verify block
        if not self._verify_block(block):
            print(f"Block verification failed: {block}")
            return False
        
        # Let consensus validate
        if not self.consensus.validate_block(block, self.state):
            print(f"Consensus validation failed: {block}")
            return False
        
        # Execute transactions and update state
        if not self._execute_block_transactions(block):
            print(f"Transaction execution failed: {block}")
            return False
        
        # Add block
        self.blocks.append(block)
        
        # Update state
        self.state.height = block.height
        self.state.last_block_hash = block.hash
        self.state.calculate_app_hash()
        
        # Remove executed transactions from pending
        executed_hashes = {tx.hash() for tx in block.transactions}
        self.pending_transactions = [
            tx for tx in self.pending_transactions
            if tx.hash() not in executed_hashes
        ]
        
        # Update validator stats
        validator = self.state.get_validator(block.validator_address)
        if validator:
            validator.total_blocks_proposed += 1
        
        # Notify consensus
        self.consensus.on_block_committed(block, self.state)
        
        # Save chain
        self._save_chain()
        
        print(f"Block {block.height} added by {block.validator_address[:8]}...")
        return True
    
    def _verify_block(self, block: Block) -> bool:
        """Verify block structure and integrity"""
        # Check height
        if block.height != self.get_height() + 1:
            return False
        
        # Check previous hash
        last_block = self.get_last_block()
        if block.previous_hash != last_block.hash:
            return False
        
        # Verify merkle root
        if not block.verify_merkle_root():
            return False
        
        # Verify transactions
        for tx in block.transactions:
            if not self._verify_transaction(tx):
                return False
        
        return True
    
    def _execute_block_transactions(self, block: Block) -> bool:
        """Execute all transactions in block"""
        # Create state snapshot for rollback
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
                    pass  # Genesis already handled
                else:
                    # Custom transaction handling
                    self._execute_custom_transaction(tx)
            
            return True
            
        except Exception as e:
            # Rollback state
            self.state = snapshot
            print(f"Transaction execution error: {e}")
            return False
    
    def _execute_transfer(self, tx: Transaction) -> None:
        """Execute transfer transaction"""
        if tx.inputs and tx.outputs:
            from_addr = tx.inputs[0].from_address
            to_addr = tx.outputs[0].to_address
            amount = tx.outputs[0].amount
            
            if not self.state.transfer(from_addr, to_addr, amount):
                raise Exception(f"Transfer failed: insufficient balance")
    
    def _execute_validator_update(self, tx: Transaction) -> None:
        """Execute validator update transaction"""
        from .state import ValidatorState
        
        validator_addr = tx.data['validator_address']
        action = tx.data['action']
        
        if action == "add":
            # Add new validator
            validator = ValidatorState(
                address=validator_addr,
                pub_key=tx.data.get('pub_key', ''),
                power=tx.data.get('power', 10)
            )
            self.state.add_validator(validator)
        elif action == "remove":
            # Remove validator
            self.state.remove_validator(validator_addr)
    
    # blockchain/core/blockchain.py (Snippet of the fix)

    # ... inside Blockchain class ...

    def _execute_permission_grant(self, tx: Transaction) -> None:
        """Execute permission grant or level update"""
        target = tx.data['target_address']
        action = tx.data.get('action', 'grant')

        # Case 1: Standard Permission Grant (e.g., "can_deploy_contract")
        if 'permission' in tx.data and action == 'grant':
            permission = tx.data['permission']
            self.state.grant_permission(target, permission)
            print(f"Granted '{permission}' to {target[:8]}...")

        # Case 2: Multi-Level Promotion (The "Level Up" logic)
        # We check specifically for 'new_level' which we added in transaction.py
        if self.permission_system and 'new_level' in tx.data:
            new_level = tx.data['new_level']
            # The permission system handles the logic: 
            # "Can sender promote target to this level?"
            success = self.permission_system.promote_user(tx.sender, target, new_level)
            if success:
                print(f"Promoted {target[:8]}... to Level {new_level}")
            else:
                print(f"Promotion failed: {tx.sender[:8]}... cannot promote {target[:8]}... to {new_level}")

    def _execute_permission_revoke(self, tx: Transaction) -> None:
        """Execute permission revoke or level demotion"""
        target = tx.data['target_address']
        action = tx.data.get('action', 'revoke')

        # Case 1: Standard Permission Revoke
        if 'permission' in tx.data and action == 'revoke':
            permission = tx.data['permission']
            self.state.revoke_permission(target, permission)
            print(f"Revoked '{permission}' from {target[:8]}...")

        # Case 2: Multi-Level Demotion
        if self.permission_system and 'new_level' in tx.data and action == 'set_level':
             # Logic for demotion if you handle it via this tx type
             pass
    
    def _execute_custom_transaction(self, tx: Transaction) -> None:
        """Execute custom transaction (override in subclass)"""
        pass
    
    def _save_chain(self) -> None:
        """Save blockchain to disk"""
        # Save blocks
        blocks_file = os.path.join(self.data_dir, "blocks.json")
        with open(blocks_file, 'w') as f:
            json.dump([block.to_dict() for block in self.blocks], f, indent=2)
        
        # Save state
        state_file = os.path.join(self.data_dir, "state.json")
        with open(state_file, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)
        
        # Save permission system if enabled
        if self.permission_system:
            perm_file = os.path.join(self.data_dir, "permissions.json")
            with open(perm_file, 'w') as f:
                json.dump(self.permission_system.to_dict(), f, indent=2)
    
    def _load_chain(self) -> bool:
        """Load blockchain from disk"""
        blocks_file = os.path.join(self.data_dir, "blocks.json")
        state_file = os.path.join(self.data_dir, "state.json")
        
        if not os.path.exists(blocks_file) or not os.path.exists(state_file):
            return False
        
        try:
            # Load blocks
            with open(blocks_file, 'r') as f:
                blocks_data = json.load(f)
                self.blocks = [Block.from_dict(b) for b in blocks_data]
            
            # Load state
            with open(state_file, 'r') as f:
                state_data = json.load(f)
                self.state = BlockchainState.from_dict(state_data)
            
            # Load permission system if exists
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
        """Get blockchain information"""
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
        
        # Add permission system info if enabled
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
    
    def store_data(
        self,
        data_id: str,
        content: any,
        security_level: int,
        owner_address: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Store data with security classification (requires multi-level permissions)
        
        Args:
            data_id: Unique identifier for data
            content: Data content
            security_level: Security level (1 to num_levels)
            owner_address: Address of data owner
            metadata: Optional metadata
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.permission_system:
            print("Multi-level permission system not enabled")
            return False
        
        return self.permission_system.store_data(
            data_id=data_id,
            content=content,
            security_level=security_level,
            owner_address=owner_address,
            metadata=metadata
        )
    
    def access_data(self, user_address: str, data_id: str) -> Optional[any]:
        """
        Access data if user has sufficient permission (requires multi-level permissions)
        
        Args:
            user_address: Address of user accessing data
            data_id: ID of data to access
            
        Returns:
            Data content if accessible, None otherwise
        """
        if not self.permission_system:
            print("Multi-level permission system not enabled")
            return None
        
        return self.permission_system.access_data(user_address, data_id)
    
    def promote_user(
        self,
        promoter_address: str,
        target_address: str,
        new_level: int
    ) -> bool:
        """
        Promote user to higher permission level (requires multi-level permissions)
        
        Args:
            promoter_address: Address of user doing the promotion
            target_address: Address of user being promoted
            new_level: New permission level
            
        Returns:
            True if promotion successful, False otherwise
        """
        if not self.permission_system:
            print("Multi-level permission system not enabled")
            return False
        
        return self.permission_system.promote_user(
            promoter_address,
            target_address,
            new_level
        )
    
    def demote_user(
        self,
        demoter_address: str,
        target_address: str,
        new_level: int
    ) -> bool:
        """
        Demote user to lower permission level (requires multi-level permissions)
        
        Args:
            demoter_address: Address of user doing the demotion
            target_address: Address of user being demoted
            new_level: New permission level
            
        Returns:
            True if demotion successful, False otherwise
        """
        if not self.permission_system:
            print("Multi-level permission system not enabled")
            return False
        
        return self.permission_system.demote_user(
            demoter_address,
            target_address,
            new_level
        )
    
    def get_user_permission_level(self, address: str) -> Optional[int]:
        """
        Get user's permission level (requires multi-level permissions)
        
        Args:
            address: User address
            
        Returns:
            Permission level or None if system not enabled
        """
        if not self.permission_system:
            return None
        
        return self.permission_system.get_user_level(address)
    
    def get_accessible_data(self, user_address: str) -> List:
        """
        Get all data accessible to user (requires multi-level permissions)
        
        Args:
            user_address: User address
            
        Returns:
            List of accessible data items
        """
        if not self.permission_system:
            return []
        
        return self.permission_system.get_accessible_data(user_address)
    
    def get_permission_audit_log(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get permission system audit log (requires multi-level permissions)
        
        Args:
            actor: Filter by actor address
            action: Filter by action type
            limit: Maximum number of entries
            
        Returns:
            Filtered audit log entries
        """
        if not self.permission_system:
            return []
        
        return self.permission_system.get_audit_log(actor, action, limit)