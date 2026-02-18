# blockchain/consensus/tendermint.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus, ConsensusVote, ConsensusRound
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class TendermintBFT(BaseConsensus):
    """
    Tendermint Byzantine Fault Tolerant Consensus
    
    Features:
    - BFT consensus with instant finality
    - Requires 2/3+ validator agreement
    - Round-based voting
    - Fork prevention
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 5,  # seconds
            'timeout_propose': 3,  # seconds
            'timeout_prevote': 1,  # seconds
            'timeout_precommit': 1,  # seconds
            'max_block_size': 1000,  # transactions
            'max_validators': 100,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.current_round: Optional[ConsensusRound] = None
        self.rounds: List[ConsensusRound] = []
        self.locked_block: Optional[Block] = None
        self.valid_block: Optional[Block] = None
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize Tendermint with blockchain"""
        super().initialize(blockchain)
        print(f"Tendermint BFT initialized with block time: {self.config['block_time']}s")
    
    def select_transactions(
        self,
        pending_transactions: List[Transaction],
        proposer_address: str
    ) -> List[Transaction]:
        """Select transactions for the next block"""
        max_size = self.config['max_block_size']
        
        # Sort by nonce/timestamp
        sorted_txs = sorted(pending_transactions, key=lambda tx: (tx.nonce, tx.timestamp))
        
        # Take up to max_block_size transactions
        return sorted_txs[:max_size]
    
    def prepare_consensus_data(
        self,
        proposer_address: str,
        previous_block: Block
    ) -> Dict[str, Any]:
        """Prepare Tendermint consensus data"""
        height = previous_block.height + 1
        
        # Start new round if needed
        if not self.current_round or self.current_round.height != height:
            self.current_round = ConsensusRound(height, 0)
            self.current_round.started_at = time.time()
        
        return {
            'consensus': 'tendermint',
            'height': height,
            'round': self.current_round.round_num,
            'proposer': proposer_address,
            'timestamp': time.time()
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using Tendermint rules"""
        # Check if proposer is valid validator
        validator = state.get_validator(block.validator_address)
        if not validator or not validator.active:
            print(f"Invalid proposer: {block.validator_address}")
            return False
        
        # Check if it's the correct proposer's turn
        expected_proposer = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_proposer:
            print(f"Wrong proposer. Expected: {expected_proposer}, Got: {block.validator_address}")
            return False
        
        # Verify block time
        if block.timestamp < time.time() - self.config['block_time'] * 2:
            print(f"Block too old")
            return False
        
        # Check transaction count
        if len(block.transactions) > self.config['max_block_size']:
            print(f"Too many transactions: {len(block.transactions)}")
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """
        Select proposer using weighted round-robin based on voting power
        """
        if not validators:
            return None
        
        # Calculate total voting power
        total_power = sum(v.power for v in validators)
        
        # Deterministic selection based on height
        # Weight by validator power
        cumulative = 0
        target = height % total_power
        
        for validator in sorted(validators, key=lambda v: v.address):
            cumulative += validator.power
            if cumulative > target:
                return validator.address
        
        # Fallback to first validator
        return validators[0].address
    
    def add_vote(
        self,
        block_hash: str,
        height: int,
        validator_address: str,
        signature: str
    ) -> bool:
        """Add a prevote/precommit vote"""
        if not self.current_round or self.current_round.height != height:
            return False
        
        vote = ConsensusVote(
            block_hash=block_hash,
            height=height,
            validator_address=validator_address,
            signature=signature,
            timestamp=time.time()
        )
        
        self.current_round.add_vote(vote)
        
        # Check if we have supermajority
        validators = self.blockchain.state.get_active_validators()
        if self.current_round.has_supermajority(len(validators)):
            return True
        
        return False
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update Tendermint state after block commit"""
        # Clear round data
        if self.current_round and self.current_round.height == block.height:
            self.current_round.completed_at = time.time()
            self.rounds.append(self.current_round)
            self.current_round = None
        
        # Clear locked/valid blocks
        self.locked_block = None
        self.valid_block = None
    
    def get_consensus_params(self) -> Dict[str, Any]:
        """Get Tendermint parameters"""
        params = super().get_consensus_params()
        params.update({
            'current_round': self.current_round.round_num if self.current_round else None,
            'total_rounds': len(self.rounds)
        })
        return params