# blockchain/core/blockchain.py

import time
from typing import List, Optional, Dict, Any, Type
from .block import Block, GenesisBlock
from .transaction import Transaction
from .state import BlockchainState
import json
import os


class Blockchain:
    """
    Main Blockchain class with pluggable consensus
    """
    
    def __init__(
        self,
        chain_id: str,
        consensus_mechanism: 'BaseConsensus',
        genesis_validators: Optional[List[dict]] = None,
        data_dir: Optional[str] = None
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
            # TODO: Implement proper signature verification
            pass
        
        # Check nonce
        account = self.state.get_account(transaction.sender)
        if transaction.nonce < account.nonce:
            return False
        
        # Check permissions
        if not self._check_transaction_permissions(transaction):
            return False
        
        return True
    
    def _check_transaction_permissions(self, transaction: Transaction) -> bool:
        """Check if sender has permission to execute transaction"""
        from .transaction import TransactionType
        
        # Define required permissions for each transaction type
        permission_map = {
            TransactionType.TRANSFER: "can_transfer",
            TransactionType.VALIDATOR_UPDATE: "can_update_validators",
            TransactionType.PERMISSION_GRANT: "can_grant_permissions",
            TransactionType.PERMISSION_REVOKE: "can_revoke_permissions",
        }
        
        required_permission = permission_map.get(transaction.tx_type)
        if required_permission:
            return self.state.has_permission(transaction.sender, required_permission)
        
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
        from .transaction import TransactionType
        
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
    
    def _execute_permission_grant(self, tx: Transaction) -> None:
        """Execute permission grant transaction"""
        target = tx.data['target_address']
        permission = tx.data['permission']
        self.state.grant_permission(target, permission)
    
    def _execute_permission_revoke(self, tx: Transaction) -> None:
        """Execute permission revoke transaction"""
        target = tx.data['target_address']
        permission = tx.data['permission']
        self.state.revoke_permission(target, permission)
    
    def _execute_custom_transaction(self, tx: Transaction) -> None:
        """Execute custom transaction (override in subclass)"""
        pass
    
    def _save_chain(self) -> None:
        """Save blockchain to disk"""
        # Save blocks
        blocks_file = os.path.join(self.data_dir, "blocks.json")
        with open(blocks_file, 'w') as f:
            json.dump([block.to_dict() for block in self.blocks], f)
        
        # Save state
        state_file = os.path.join(self.data_dir, "state.json")
        with open(state_file, 'w') as f:
            json.dump(self.state.to_dict(), f)
    
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
            
            print(f"Loaded chain {self.chain_id} with {len(self.blocks)} blocks")
            return True
            
        except Exception as e:
            print(f"Error loading chain: {e}")
            return False
    
    def get_chain_info(self) -> dict:
        """Get blockchain information"""
        return {
            'chain_id': self.chain_id,
            'height': self.get_height(),
            'last_block_hash': self.state.last_block_hash,
            'app_hash': self.state.app_hash,
            'total_transactions': sum(len(b.transactions) for b in self.blocks),
            'pending_transactions': len(self.pending_transactions),
            'validators': len(self.state.get_active_validators()),
            'consensus': self.consensus.__class__.__name__
        }