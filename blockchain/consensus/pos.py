# blockchain/consensus/pos.py

import time
import random
import hashlib
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class ProofOfStake(BaseConsensus):
    """
    Proof of Stake Consensus
    
    Features:
    - Validators selected based on stake
    - Energy efficient
    - Randomized selection with stake weighting
    - Slashing for misbehavior
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 6,
            'min_stake': 100,  # Minimum stake to become validator
            'max_block_size': 1000,
            'epoch_length': 100,  # Blocks per epoch
            'slashing_penalty': 0.1,  # 10% stake slashed for misbehavior
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.stakes: Dict[str, float] = {}
        self.slashed_validators: Dict[str, float] = {}
        self.current_epoch = 0
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize PoS"""
        super().initialize(blockchain)
        
        # Initialize stakes from validator power
        validators = blockchain.state.get_active_validators()
        for validator in validators:
            self.stakes[validator.address] = float(validator.power * 10)
        
        print(f"PoS initialized with {len(self.stakes)} staked validators")
    
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
        """Prepare PoS consensus data"""
        return {
            'consensus': 'pos',
            'validator_stake': self.stakes.get(proposer_address, 0),
            'total_stake': sum(self.stakes.values()),
            'epoch': self.current_epoch
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using PoS rules"""
        # Verify validator has minimum stake
        validator_stake = self.stakes.get(block.validator_address, 0)
        if validator_stake < self.config['min_stake']:
            print(f"Validator stake too low: {validator_stake}")
            return False
        
        # Verify validator wasn't slashed
        if block.validator_address in self.slashed_validators:
            print(f"Validator was slashed")
            return False
        
        # Verify proposer selection
        expected_proposer = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected_proposer:
            print(f"Wrong proposer selected")
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """
        Select validator based on stake-weighted randomness
        Uses VRF-like selection
        """
        if not self.stakes:
            return None
        
        # Create deterministic randomness from height
        seed = hashlib.sha256(str(height).encode()).hexdigest()
        random.seed(int(seed, 16))
        
        # Filter validators with minimum stake
        eligible_validators = [
            (addr, stake) for addr, stake in self.stakes.items()
            if stake >= self.config['min_stake'] and addr not in self.slashed_validators
        ]
        
        if not eligible_validators:
            return None
        
        # Weighted random selection
        total_stake = sum(stake for _, stake in eligible_validators)
        rand_value = random.uniform(0, total_stake)
        
        cumulative = 0
        for address, stake in eligible_validators:
            cumulative += stake
            if cumulative >= rand_value:
                return address
        
        # Fallback
        return eligible_validators[0][0]
    
    def add_stake(self, validator_address: str, amount: float) -> None:
        """Add stake for validator"""
        current_stake = self.stakes.get(validator_address, 0)
        self.stakes[validator_address] = current_stake + amount
        print(f"Added {amount} stake to {validator_address}. Total: {self.stakes[validator_address]}")
    
    def remove_stake(self, validator_address: str, amount: float) -> bool:
        """Remove stake from validator"""
        current_stake = self.stakes.get(validator_address, 0)
        if current_stake < amount:
            return False
        
        self.stakes[validator_address] = current_stake - amount
        print(f"Removed {amount} stake from {validator_address}. Total: {self.stakes[validator_address]}")
        return True
    
    def slash_validator(self, validator_address: str, reason: str) -> None:
        """Slash validator for misbehavior"""
        if validator_address not in self.stakes:
            return
        
        stake = self.stakes[validator_address]
        penalty = stake * self.config['slashing_penalty']
        
        self.stakes[validator_address] -= penalty
        self.slashed_validators[validator_address] = penalty
        
        print(f"Slashed {validator_address}: {penalty} ({reason})")
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update PoS state after block commit"""
        # Check if epoch ended
        if block.height % self.config['epoch_length'] == 0:
            self.current_epoch += 1
            print(f"Epoch {self.current_epoch} started")