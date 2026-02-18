# blockchain/consensus/hybrid.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class HybridConsensus(BaseConsensus):
    """
    Hybrid Consensus Mechanism
    
    Combines multiple consensus approaches:
    - PoA for fast block production
    - Voting for important decisions
    - PoS for long-term validator selection
    
    Features:
    - Fast block times with PoA authorities
    - Democratic decision making through voting
    - Economic security through staking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 3,
            'max_block_size': 1500,
            
            # PoA settings
            'num_authorities': 5,
            'authority_rotation_interval': 100,  # blocks
            
            # Voting settings
            'important_tx_voting': True,
            'voting_threshold': 0.66,
            
            # PoS settings
            'min_stake': 100,
            'stake_weight': 0.5,  # How much stake influences selection
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # PoA state
        self.authorities: List[str] = []
        self.current_authority_index = 0
        
        # Voting state
        self.pending_votes: Dict[str, Dict[str, bool]] = {}  # tx_hash -> {voter -> vote}
        
        # PoS state
        self.stakes: Dict[str, float] = {}
        self.validator_scores: Dict[str, float] = {}
        
        self.last_rotation_height = 0
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize Hybrid consensus"""
        super().initialize(blockchain)
        
        # Initialize authorities and stakes
        validators = blockchain.state.get_active_validators()
        
        for validator in validators:
            # Initialize stake
            self.stakes[validator.address] = float(validator.power * 10)
            # Calculate initial score (combination of stake and reputation)
            self.validator_scores[validator.address] = self._calculate_validator_score(validator)
        
        # Select initial authorities based on scores
        self._select_authorities()
        
        print(f"Hybrid consensus initialized with {len(self.authorities)} authorities")
    
    def select_transactions(
        self,
        pending_transactions: List[Transaction],
        proposer_address: str
    ) -> List[Transaction]:
        """Select transactions, checking for those requiring votes"""
        max_size = self.config['max_block_size']
        
        approved_txs = []
        
        for tx in sorted(pending_transactions, key=lambda t: t.timestamp)[:max_size]:
            # Check if transaction requires voting
            if self._requires_voting(tx):
                if self._has_sufficient_votes(tx):
                    approved_txs.append(tx)
            else:
                approved_txs.append(tx)
        
        return approved_txs
    
    def prepare_consensus_data(
        self,
        proposer_address: str,
        previous_block: Block
    ) -> Dict[str, Any]:
        """Prepare Hybrid consensus data"""
        return {
            'consensus': 'hybrid',
            'authority': proposer_address,
            'authority_index': self.current_authority_index,
            'total_authorities': len(self.authorities),
            'validator_stake': self.stakes.get(proposer_address, 0),
            'validator_score': self.validator_scores.get(proposer_address, 0),
            'epoch': previous_block.height // self.config['authority_rotation_interval']
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using Hybrid rules"""
        # Verify proposer is current authority
        if block.validator_address not in self.authorities:
            print(f"Proposer is not an authority")
            return False
        
        expected_authority = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_authority:
            print(f"Wrong authority turn")
            return False
        
        # Verify proposer has minimum stake
        stake = self.stakes.get(block.validator_address, 0)
        if stake < self.config['min_stake']:
            print(f"Insufficient stake: {stake}")
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """Select current authority in rotation"""
        if not self.authorities:
            return None
        
        # Check if authorities need rotation
        if height - self.last_rotation_height >= self.config['authority_rotation_interval']:
            self._select_authorities()
            self.last_rotation_height = height
        
        # Round-robin through authorities
        index = height % len(self.authorities)
        self.current_authority_index = index
        
        return self.authorities[index]
    
    def _select_authorities(self) -> None:
        """Select authorities based on validator scores (stake + reputation)"""
        if not self.blockchain:
            return
        
        validators = self.blockchain.state.get_active_validators()
        
        # Sort by score
        sorted_validators = sorted(
            validators,
            key=lambda v: self.validator_scores.get(v.address, 0),
            reverse=True
        )
        
        # Select top N as authorities
        num_authorities = min(self.config['num_authorities'], len(sorted_validators))
        old_authorities = set(self.authorities)
        self.authorities = [v.address for v in sorted_validators[:num_authorities]]
        new_authorities = set(self.authorities)
        
        # Log changes
        added = new_authorities - old_authorities
        removed = old_authorities - new_authorities
        
        if added or removed:
            print(f"Authority rotation: +{len(added)} -{len(removed)}")
    
    def _calculate_validator_score(self, validator: ValidatorState) -> float:
        """
        Calculate validator score based on stake and performance
        
        Score = (stake * stake_weight) + (performance * (1 - stake_weight))
        """
        stake = self.stakes.get(validator.address, 0)
        stake_weight = self.config['stake_weight']
        
        # Calculate performance score (blocks proposed/signed ratio)
        total_blocks = validator.total_blocks_proposed + validator.total_blocks_signed
        if total_blocks > 0:
            performance = (validator.total_blocks_signed / total_blocks) * 100
        else:
            performance = 50.0  # Default
        
        # Combined score
        score = (stake * stake_weight) + (performance * (1 - stake_weight))
        
        return score
    
    def _requires_voting(self, transaction: Transaction) -> bool:
        """Check if transaction requires validator voting"""
        if not self.config['important_tx_voting']:
            return False
        
        from ..core.transaction import TransactionType
        
        # These transaction types require voting
        voting_required_types = [
            TransactionType.VALIDATOR_UPDATE,
            TransactionType.PERMISSION_GRANT,
            TransactionType.PERMISSION_REVOKE,
        ]
        
        return transaction.tx_type in voting_required_types
    
    def cast_vote_for_transaction(
        self,
        tx_hash: str,
        voter_address: str,
        approve: bool
    ) -> bool:
        """Cast vote for a transaction"""
        if not self.blockchain:
            return False
        
        # Verify voter is a validator
        validator = self.blockchain.state.get_validator(voter_address)
        if not validator or not validator.active:
            return False
        
        if tx_hash not in self.pending_votes:
            self.pending_votes[tx_hash] = {}
        
        self.pending_votes[tx_hash][voter_address] = approve
        
        return True
    
    def _has_sufficient_votes(self, transaction: Transaction) -> bool:
        """Check if transaction has sufficient approval votes"""
        tx_hash = transaction.hash()
        
        if tx_hash not in self.pending_votes:
            return False
        
        votes = self.pending_votes[tx_hash]
        approve_count = sum(1 for vote in votes.values() if vote)
        
        if not self.blockchain:
            return False
        
        validators = self.blockchain.state.get_active_validators()
        required_votes = int(len(validators) * self.config['voting_threshold'])
        
        return approve_count >= required_votes
    
    def add_stake(self, validator_address: str, amount: float) -> None:
        """Add stake for validator"""
        current_stake = self.stakes.get(validator_address, 0)
        self.stakes[validator_address] = current_stake + amount
        
        # Recalculate score
        if self.blockchain:
            validator = self.blockchain.state.get_validator(validator_address)
            if validator:
                self.validator_scores[validator_address] = self._calculate_validator_score(validator)
    
    def remove_stake(self, validator_address: str, amount: float) -> bool:
        """Remove stake from validator"""
        current_stake = self.stakes.get(validator_address, 0)
        if current_stake < amount:
            return False
        
        self.stakes[validator_address] = current_stake - amount
        
        # Recalculate score
        if self.blockchain:
            validator = self.blockchain.state.get_validator(validator_address)
            if validator:
                self.validator_scores[validator_address] = self._calculate_validator_score(validator)
        
        return True
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update hybrid consensus state after block commit"""
        # Update validator scores
        validator = state.get_validator(block.validator_address)
        if validator:
            self.validator_scores[block.validator_address] = self._calculate_validator_score(validator)
        
        # Clean up voted transactions
        for tx in block.transactions:
            tx_hash = tx.hash()
            if tx_hash in self.pending_votes:
                del self.pending_votes[tx_hash]
        
        # Check for authority rotation
        if block.height - self.last_rotation_height >= self.config['authority_rotation_interval']:
            self._select_authorities()
            self.last_rotation_height = block.height
    
    def get_authority_info(self) -> Dict[str, Any]:
        """Get information about current authorities"""
        return {
            'authorities': self.authorities,
            'current_index': self.current_authority_index,
            'rotation_interval': self.config['authority_rotation_interval'],
            'blocks_until_rotation': self.config['authority_rotation_interval'] - 
                                    (self.blockchain.get_height() - self.last_rotation_height) 
                                    if self.blockchain else 0
        }