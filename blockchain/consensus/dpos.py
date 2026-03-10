# blockchain/consensus/dpos.py

import time
from typing import List, Dict, Any, Optional, Set
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class DelegatedProofOfStake(BaseConsensus):
    """
    Delegated Proof of Stake Consensus
    
    Features:
    - Stakeholders vote for delegates
    - Fixed number of active delegates
    - Fast block production
    - Democratic validator selection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 3,
            'num_delegates': 21,  # Number of active block producers
            'round_length': 21,  # Blocks per round (one per delegate)
            'vote_update_interval': 100,  # Blocks between vote recalculation
            'max_block_size': 2000,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # Voting data
        self.votes: Dict[str, Dict[str, float]] = {}  # voter -> {delegate -> stake}
        self.delegate_votes: Dict[str, float] = {}  # delegate -> total votes
        self.active_delegates: List[str] = []
        
        # Round tracking
        self.current_round = 0
        self.blocks_in_round = 0
        
        self.last_vote_update = 0
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize DPoS"""
        super().initialize(blockchain)
        
        # Initialize delegates from validators
        validators = blockchain.state.get_active_validators()
        for validator in validators[:self.config['num_delegates']]:
            self.active_delegates.append(validator.address)
            self.delegate_votes[validator.address] = float(validator.power)
        
        print(f"DPoS initialized with {len(self.active_delegates)} delegates")
    
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
        """Prepare DPoS consensus data"""
        return {
            'consensus': 'dpos',
            'delegate': proposer_address,
            'round': self.current_round,
            'block_in_round': self.blocks_in_round,
            'total_delegates': len(self.active_delegates),
            'delegate_votes': self.delegate_votes.get(proposer_address, 0)
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using DPoS rules"""
        # Verify proposer is an active delegate
        if block.validator_address not in self.active_delegates:
            print(f"Proposer {block.validator_address} is not an active delegate")
            return False
        
        # Verify it's the correct delegate's turn
        expected_proposer = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_proposer:
            print(f"Wrong delegate turn. Expected: {expected_proposer}")
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """Select delegate for this block"""
        if not self.active_delegates:
            return None
        
        # Round-robin through active delegates
        delegate_index = height % len(self.active_delegates)
        return self.active_delegates[delegate_index]
    
    def cast_vote(self, voter_address: str, delegate_address: str, stake: float) -> bool:
        """
        Cast vote for a delegate
        
        Args:
            voter_address: Address of the voter
            delegate_address: Address of the delegate being voted for
            stake: Amount of stake voting with
        """
        if voter_address not in self.votes:
            self.votes[voter_address] = {}
        
        # Update vote
        self.votes[voter_address][delegate_address] = stake
        
        # Recalculate delegate votes
        self._recalculate_votes()
        
        print(f"{voter_address[:8]} voted for {delegate_address[:8]} with {stake} stake")
        return True
    
    def remove_vote(self, voter_address: str, delegate_address: str) -> bool:
        """Remove vote from a delegate"""
        if voter_address in self.votes and delegate_address in self.votes[voter_address]:
            del self.votes[voter_address][delegate_address]
            self._recalculate_votes()
            return True
        return False
    
    def _recalculate_votes(self) -> None:
        """Recalculate total votes for each delegate"""
        self.delegate_votes.clear()
        
        for voter, delegate_votes in self.votes.items():
            for delegate, stake in delegate_votes.items():
                if delegate not in self.delegate_votes:
                    self.delegate_votes[delegate] = 0
                self.delegate_votes[delegate] += stake
    
    def update_active_delegates(self) -> None:
        """Update active delegate set based on votes"""
        # Sort delegates by vote count
        sorted_delegates = sorted(
            self.delegate_votes.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Select top N delegates
        num_delegates = self.config['num_delegates']
        old_delegates = set(self.active_delegates)
        self.active_delegates = [addr for addr, _ in sorted_delegates[:num_delegates]]
        new_delegates = set(self.active_delegates)
        
        # Log changes
        added = new_delegates - old_delegates
        removed = old_delegates - new_delegates
        
        if added:
            print(f"New delegates: {[d[:8] + '...' for d in added]}")
        if removed:
            print(f"Removed delegates: {[d[:8] + '...' for d in removed]}")
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update DPoS state after block commit"""
        self.blocks_in_round += 1
        
        # Check if round completed
        if self.blocks_in_round >= self.config['round_length']:
            self.current_round += 1
            self.blocks_in_round = 0
            print(f"Round {self.current_round} completed")
        
        # Periodically update delegates based on votes
        if block.height - self.last_vote_update >= self.config['vote_update_interval']:
            self.update_active_delegates()
            self.last_vote_update = block.height
    
    def get_delegate_info(self, delegate_address: str) -> Dict[str, Any]:
        """Get information about a delegate"""
        return {
            'address': delegate_address,
            'votes': self.delegate_votes.get(delegate_address, 0),
            'is_active': delegate_address in self.active_delegates,
            'rank': self.active_delegates.index(delegate_address) + 1 if delegate_address in self.active_delegates else None
        }
    
    def get_voter_info(self, voter_address: str) -> Dict[str, Any]:
        """Get information about a voter"""
        votes = self.votes.get(voter_address, {})
        return {
            'address': voter_address,
            'total_votes_cast': sum(votes.values()),
            'delegates_voted_for': list(votes.keys()),
            'vote_distribution': votes
        }