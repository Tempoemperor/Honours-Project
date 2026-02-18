# blockchain/consensus/poa.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class ProofOfAuthority(BaseConsensus):
    """
    Proof of Authority Consensus
    
    Features:
    - Pre-approved validators (authorities)
    - Round-robin block production
    - High throughput, low latency
    - Permissioned network
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 2,  # seconds
            'max_block_size': 2000,
            'authorities': [],  # List of authorized validators
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.authorities: List[str] = self.config.get('authorities', [])
        self.current_proposer_index = 0
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize PoA"""
        super().initialize(blockchain)
        
        # If no authorities specified, use all validators
        if not self.authorities:
            validators = blockchain.state.get_active_validators()
            self.authorities = [v.address for v in validators]
        
        print(f"PoA initialized with {len(self.authorities)} authorities")
    
    def select_transactions(
        self,
        pending_transactions: List[Transaction],
        proposer_address: str
    ) -> List[Transaction]:
        """Select transactions for block"""
        max_size = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: (tx.timestamp, tx.nonce))
        return sorted_txs[:max_size]
    
    def prepare_consensus_data(
        self,
        proposer_address: str,
        previous_block: Block
    ) -> Dict[str, Any]:
        """Prepare PoA consensus data"""
        return {
            'consensus': 'poa',
            'authority': proposer_address,
            'authority_index': self.current_proposer_index,
            'total_authorities': len(self.authorities)
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using PoA rules"""
        # Verify proposer is an authority
        if block.validator_address not in self.authorities:
            print(f"Proposer {block.validator_address} is not an authority")
            return False
        
        # Verify it's the correct authority's turn
        expected_proposer = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_proposer:
            print(f"Wrong authority turn. Expected: {expected_proposer}")
            return False
        
        # Check block time
        if previous_block := state.blockchain.get_block(block.height - 1):
            time_diff = block.timestamp - previous_block.timestamp
            if time_diff < self.config['block_time'] * 0.5:
                print(f"Block produced too quickly: {time_diff}s")
                return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """Select next authority in round-robin fashion"""
        if not self.authorities:
            return None
        
        # Round-robin selection
        index = height % len(self.authorities)
        self.current_proposer_index = index
        
        return self.authorities[index]
    
    def add_authority(self, address: str) -> bool:
        """Add new authority"""
        if address not in self.authorities:
            self.authorities.append(address)
            print(f"Added authority: {address}")
            return True
        return False
    
    def remove_authority(self, address: str) -> bool:
        """Remove authority"""
        if address in self.authorities:
            self.authorities.remove(address)
            print(f"Removed authority: {address}")
            return True
        return False
    
    def is_authority(self, address: str) -> bool:
        """Check if address is an authority"""
        return address in self.authorities
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update after block commit"""
        # Rotate to next proposer
        self.current_proposer_index = (self.current_proposer_index + 1) % len(self.authorities)