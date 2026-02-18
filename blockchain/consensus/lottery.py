# blockchain/consensus/lottery.py

import time
import random
import hashlib
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class LotteryConsensus(BaseConsensus):
    """
    Lottery-Based Consensus
    
    Features:
    - Random selection of block producer
    - Fairness through randomness
    - Can be weighted by stake or reputation
    - Prevents predictable attacks
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 5,
            'max_block_size': 1000,
            'weighted': True,  # Weight lottery by validator power
            'min_tickets': 1,  # Minimum tickets per validator
            'randomness_source': 'block_hash',  # 'block_hash' or 'timestamp'
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.ticket_pool: Dict[str, int] = {}  # validator -> number of tickets
        self.winning_history: List[Dict[str, Any]] = []
        self.last_winner: Optional[str] = None
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize Lottery consensus"""
        super().initialize(blockchain)
        
        # Initialize ticket pool
        validators = blockchain.state.get_active_validators()
        for validator in validators:
            if self.config['weighted']:
                # Weight by validator power
                self.ticket_pool[validator.address] = max(
                    validator.power,
                    self.config['min_tickets']
                )
            else:
                # Equal tickets for all
                self.ticket_pool[validator.address] = self.config['min_tickets']
        
        print(f"Lottery consensus initialized with {len(self.ticket_pool)} validators")
    
    def select_transactions(
        self,
        pending_transactions: List[Transaction],
        proposer_address: str
    ) -> List[Transaction]:
        """Select transactions for block"""
        max_size = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: tx.timestamp)
        return sorted_txs[:max_size]
    
    def prepare_consensus_data(
        self,
        proposer_address: str,
        previous_block: Block
    ) -> Dict[str, Any]:
        """Prepare Lottery consensus data"""
        return {
            'consensus': 'lottery',
            'winner': proposer_address,
            'tickets': self.ticket_pool.get(proposer_address, 0),
            'total_tickets': sum(self.ticket_pool.values()),
            'win_probability': self._calculate_win_probability(proposer_address)
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using Lottery rules"""
        # Verify proposer has tickets
        if block.validator_address not in self.ticket_pool:
            return False
        
        if self.ticket_pool[block.validator_address] < 1:
            return False
        
        # Verify proposer was selected correctly
        expected_winner = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_winner:
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """
        Select winner through weighted lottery
        """
        if not self.ticket_pool:
            return None
        
        # Generate deterministic randomness from height and previous block
        if self.config['randomness_source'] == 'block_hash' and self.blockchain:
            previous_block = self.blockchain.get_block(height - 1)
            if previous_block:
                seed = int(previous_block.hash, 16) + height
            else:
                seed = height
        else:
            seed = int(time.time() * 1000) + height
        
        random.seed(seed)
        
        # Create weighted lottery
        tickets = []
        for validator_addr, num_tickets in self.ticket_pool.items():
            # Check if validator is active
            validator = next((v for v in validators if v.address == validator_addr), None)
            if validator and validator.active:
                tickets.extend([validator_addr] * num_tickets)
        
        if not tickets:
            return None
        
        # Draw winner
        winner = random.choice(tickets)
        self.last_winner = winner
        
        return winner
    
    def _calculate_win_probability(self, validator_address: str) -> float:
        """Calculate win probability for a validator"""
        validator_tickets = self.ticket_pool.get(validator_address, 0)
        total_tickets = sum(self.ticket_pool.values())
        
        if total_tickets == 0:
            return 0.0
        
        return (validator_tickets / total_tickets) * 100
    
    def add_tickets(self, validator_address: str, num_tickets: int) -> None:
        """Add tickets to validator"""
        if validator_address not in self.ticket_pool:
            self.ticket_pool[validator_address] = 0
        
        self.ticket_pool[validator_address] += num_tickets
        print(f"Added {num_tickets} tickets to {validator_address[:8]}. Total: {self.ticket_pool[validator_address]}")
    
    def remove_tickets(self, validator_address: str, num_tickets: int) -> bool:
        """Remove tickets from validator"""
        if validator_address not in self.ticket_pool:
            return False
        
        current = self.ticket_pool[validator_address]
        new_amount = max(self.config['min_tickets'], current - num_tickets)
        self.ticket_pool[validator_address] = new_amount
        
        print(f"Removed {num_tickets} tickets from {validator_address[:8]}. Total: {new_amount}")
        return True
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Record winning history"""
        self.winning_history.append({
            'height': block.height,
            'winner': block.validator_address,
            'tickets': self.ticket_pool.get(block.validator_address, 0),
            'timestamp': block.timestamp
        })
        
        # Keep only last 100 wins
        if len(self.winning_history) > 100:
            self.winning_history.pop(0)
    
    def get_win_statistics(self, validator_address: str) -> Dict[str, Any]:
        """Get winning statistics for a validator"""
        wins = [w for w in self.winning_history if w['winner'] == validator_address]
        
        return {
            'total_wins': len(wins),
            'win_percentage': (len(wins) / len(self.winning_history) * 100) if self.winning_history else 0,
            'expected_probability': self._calculate_win_probability(validator_address),
            'current_tickets': self.ticket_pool.get(validator_address, 0)
        }