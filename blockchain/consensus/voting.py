# blockchain/consensus/voting.py

import time
from typing import List, Dict, Any, Optional, Set
from .base import BaseConsensus, ConsensusVote
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class VotingBasedConsensus(BaseConsensus):
    """
    Voting-Based Consensus
    
    Features:
    - Validators vote on proposed blocks
    - Simple majority or supermajority voting
    - Democratic block selection
    - Multiple proposals can compete
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 4,
            'max_block_size': 1000,
            'voting_threshold': 0.66,  # 66% agreement needed (supermajority)
            'proposal_timeout': 10,  # seconds
            'max_concurrent_proposals': 3,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # Track proposals and votes
        self.proposals: Dict[str, Block] = {}  # block_hash -> Block
        self.votes: Dict[str, Set[str]] = {}  # block_hash -> set of voter addresses
        self.proposal_times: Dict[str, float] = {}  # block_hash -> timestamp
        
        self.last_committed_height = 0
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize Voting consensus"""
        super().initialize(blockchain)
        print("Voting-based consensus initialized")
    
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
        """Prepare Voting consensus data"""
        return {
            'consensus': 'voting',
            'proposer': proposer_address,
            'voting_threshold': self.config['voting_threshold'],
            'proposal_time': time.time()
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using Voting rules"""
        # Check if proposer is a validator
        validator = state.get_validator(block.validator_address)
        if not validator or not validator.active:
            return False
        
        # Check if enough votes were collected
        if block.hash in self.votes:
            validators = state.get_active_validators()
            vote_count = len(self.votes[block.hash])
            required_votes = int(len(validators) * self.config['voting_threshold'])
            
            if vote_count < required_votes:
                print(f"Not enough votes: {vote_count}/{required_votes}")
                return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """
        Any validator can propose, but all must vote
        Returns first active validator for simplicity
        """
        active_validators = [v for v in validators if v.active]
        if not active_validators:
            return None
        
        # Rotate through validators
        index = height % len(active_validators)
        return active_validators[index].address
    
    def propose_block_for_voting(self, block: Block) -> bool:
        """
        Submit a block proposal for voting
        
        Args:
            block: Block to propose
            
        Returns:
            True if proposal accepted, False otherwise
        """
        # Check if too many concurrent proposals
        active_proposals = self._get_active_proposals()
        if len(active_proposals) >= self.config['max_concurrent_proposals']:
            print("Too many concurrent proposals")
            return False
        
        # Check if already proposed
        if block.hash in self.proposals:
            return False
        
        # Add proposal
        self.proposals[block.hash] = block
        self.votes[block.hash] = set()
        self.proposal_times[block.hash] = time.time()
        
        print(f"Block proposal submitted: {block.hash[:8]}... by {block.validator_address[:8]}...")
        return True
    
    def cast_vote(
        self,
        block_hash: str,
        voter_address: str,
        signature: str
    ) -> bool:
        """
        Cast vote for a block proposal
        
        Args:
            block_hash: Hash of the block being voted on
            voter_address: Address of the voter
            signature: Signature of the vote
            
        Returns:
            True if vote accepted, False otherwise
        """
        # Verify proposal exists
        if block_hash not in self.proposals:
            print(f"Proposal not found: {block_hash[:8]}")
            return False
        
        # Check if proposal timed out
        if self._is_proposal_expired(block_hash):
            print(f"Proposal expired: {block_hash[:8]}")
            self._remove_proposal(block_hash)
            return False
        
        # Verify voter is a validator
        if not self.blockchain:
            return False
        
        validator = self.blockchain.state.get_validator(voter_address)
        if not validator or not validator.active:
            print(f"Invalid voter: {voter_address[:8]}")
            return False
        
        # Check if already voted
        if voter_address in self.votes[block_hash]:
            print(f"Already voted: {voter_address[:8]}")
            return False
        
        # Add vote
        self.votes[block_hash].add(voter_address)
        
        print(f"Vote cast by {voter_address[:8]} for block {block_hash[:8]}")
        
        # Check if threshold reached
        return self._check_voting_threshold(block_hash)
    
    def _check_voting_threshold(self, block_hash: str) -> bool:
        """Check if voting threshold is reached"""
        if not self.blockchain:
            return False
        
        validators = self.blockchain.state.get_active_validators()
        total_validators = len(validators)
        votes_received = len(self.votes[block_hash])
        
        required_votes = int(total_validators * self.config['voting_threshold'])
        
        if votes_received >= required_votes:
            print(f"Voting threshold reached for {block_hash[:8]}: {votes_received}/{total_validators}")
            return True
        
        return False
    
    def get_winning_proposal(self, height: int) -> Optional[Block]:
        """
        Get the block proposal that won the vote
        
        Args:
            height: Block height
            
        Returns:
            Winning block or None
        """
        if not self.blockchain:
            return None
        
        validators = self.blockchain.state.get_active_validators()
        total_validators = len(validators)
        required_votes = int(total_validators * self.config['voting_threshold'])
        
        # Find proposal with enough votes
        for block_hash, block in self.proposals.items():
            if block.height == height:
                vote_count = len(self.votes.get(block_hash, set()))
                if vote_count >= required_votes:
                    return block
        
        return None
    
    def _get_active_proposals(self) -> List[str]:
        """Get list of active (non-expired) proposal hashes"""
        active = []
        current_time = time.time()
        
        for block_hash, proposal_time in list(self.proposal_times.items()):
            if current_time - proposal_time < self.config['proposal_timeout']:
                active.append(block_hash)
            else:
                self._remove_proposal(block_hash)
        
        return active
    
    def _is_proposal_expired(self, block_hash: str) -> bool:
        """Check if proposal has expired"""
        if block_hash not in self.proposal_times:
            return True
        
        proposal_time = self.proposal_times[block_hash]
        return time.time() - proposal_time > self.config['proposal_timeout']
    
    def _remove_proposal(self, block_hash: str) -> None:
        """Remove expired or completed proposal"""
        if block_hash in self.proposals:
            del self.proposals[block_hash]
        if block_hash in self.votes:
            del self.votes[block_hash]
        if block_hash in self.proposal_times:
            del self.proposal_times[block_hash]
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Clean up after block commit"""
        self.last_committed_height = block.height
        
        # Remove committed block's proposal
        if block.hash in self.proposals:
            self._remove_proposal(block.hash)
        
        # Remove any proposals for this height
        for block_hash in list(self.proposals.keys()):
            proposal_block = self.proposals[block_hash]
            if proposal_block.height <= block.height:
                self._remove_proposal(block_hash)
    
    def get_proposal_status(self, block_hash: str) -> Optional[Dict[str, Any]]:
        """Get status of a proposal"""
        if block_hash not in self.proposals:
            return None
        
        block = self.proposals[block_hash]
        votes = self.votes.get(block_hash, set())
        
        if not self.blockchain:
            return None
        
        validators = self.blockchain.state.get_active_validators()
        required_votes = int(len(validators) * self.config['voting_threshold'])
        
        return {
            'block_hash': block_hash,
            'height': block.height,
            'proposer': block.validator_address,
            'votes_received': len(votes),
            'votes_required': required_votes,
            'voters': list(votes),
            'proposal_time': self.proposal_times.get(block_hash),
            'expired': self._is_proposal_expired(block_hash)
        }