# blockchain/consensus/round_robin.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class RoundRobin(BaseConsensus):
    """
    Simple Round Robin Consensus
    
    Features:
    - Simplest consensus mechanism
    - Validators take turns producing blocks
    - Deterministic and predictable
    - Good for testing and development
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 2,
            'max_block_size': 1000,
            'skip_inactive_validators': True,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.validator_list: List[str] = []
        self.current_index = 0
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize Round Robin"""
        super().initialize(blockchain)
        
        # Get initial validator list
        validators = blockchain.state.get_active_validators()
        self.validator_list = [v.address for v in validators]
        
        print(f"Round Robin initialized with {len(self.validator_list)} validators")
    
    def select_transactions(
        self,
        pending_transactions: List[Transaction],
        proposer_address: str
    ) -> List[Transaction]:
        """Select transactions for block"""
        max_size = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: (tx.nonce, tx.timestamp))
        return sorted_txs[:max_size]
    
    def prepare_consensus_data(
        self,
        proposer_address: str,
        previous_block: Block
    ) -> Dict[str, Any]:
        """Prepare Round Robin consensus data"""
        return {
            'consensus': 'round_robin',
            'proposer_index': self.current_index,
            'total_validators': len(self.validator_list),
            'rotation_position': self.current_index
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using Round Robin rules"""
        # Verify proposer is in validator list
        if block.validator_address not in self.validator_list:
            print(f"Proposer not in validator list")
            return False
        
        # Verify correct turn
        expected_proposer = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_proposer:
            print(f"Wrong validator turn")
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """Select next validator in round-robin order"""
        if not self.validator_list:
            return None
        
        # Simple round-robin
        index = height % len(self.validator_list)
        self.current_index = index
        
        proposer = self.validator_list[index]
        
        # Skip inactive validators if configured
        if self.config['skip_inactive_validators']:
            validator = next((v for v in validators if v.address == proposer), None)
            if validator and not validator.active:
                # Move to next validator
                return self.select_proposer(height + 1, validators)
        
        return proposer
    
    def add_validator(self, validator_address: str) -> None:
        """Add validator to rotation"""
        if validator_address not in self.validator_list:
            self.validator_list.append(validator_address)
            print(f"Added validator to rotation: {validator_address[:8]}...")
    
    def remove_validator(self, validator_address: str) -> None:
        """Remove validator from rotation"""
        if validator_address in self.validator_list:
            self.validator_list.remove(validator_address)
            print(f"Removed validator from rotation: {validator_address[:8]}...")
    
    def reorder_validators(self, new_order: List[str]) -> bool:
        """Manually reorder validator list"""
        # Verify all validators are in the list
        if set(new_order) != set(self.validator_list):
            return False
        
        self.validator_list = new_order
        print("Validator order updated")
        return True
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update after block commit"""
        # Move to next validator
        self.current_index = (self.current_index + 1) % len(self.validator_list)