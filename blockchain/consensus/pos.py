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

    Validators are selected via stake-weighted VRF.
    Slashing penalises misbehaviour.
    In single-node simulation the admin is auto-staked so the
    full selection algorithm runs and always resolves correctly.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time':       6,
            'min_stake':        100,
            'max_block_size':   1000,
            'epoch_length':     100,
            'slashing_penalty': 0.1,
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)

        self.stakes:             Dict[str, float] = {}
        self.slashed_validators: Dict[str, float] = {}
        self.current_epoch = 0

    def initialize(self, blockchain: 'Blockchain') -> None:
        super().initialize(blockchain)
        validators = blockchain.state.get_active_validators()
        for validator in validators:
            stake = float(validator.power * 10)
            # Ensure stake meets minimum so selection always works
            self.stakes[validator.address] = max(stake, float(self.config['min_stake']))
        print(f"PoS initialized with {len(self.stakes)} staked validators")

    def _ensure_staked(self, address: str) -> None:
        """Auto-stake an address that is missing from the pool."""
        if address not in self.stakes or self.stakes[address] < self.config['min_stake']:
            self.stakes[address] = float(self.config['min_stake'])
            print(f"PoS: auto-staked {address[:16]}... with {self.config['min_stake']}")

    def select_transactions(self, pending_transactions: List[Transaction],
                            proposer_address: str) -> List[Transaction]:
        max_size   = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: tx.timestamp)
        return sorted_txs[:max_size]

    def prepare_consensus_data(self, proposer_address: str,
                               previous_block: Block) -> Dict[str, Any]:
        self._ensure_staked(proposer_address)
        return {
            'consensus':       'pos',
            'validator_stake': self.stakes.get(proposer_address, 0),
            'total_stake':     sum(self.stakes.values()),
            'epoch':           self.current_epoch,
        }

    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        # Auto-stake if missing — handles first block after cache rebuild
        self._ensure_staked(block.validator_address)

        if block.validator_address in self.slashed_validators:
            print(f"PoS: validator {block.validator_address[:8]} is slashed")
            return False

        # Run the full stake-weighted VRF selection and verify
        expected = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected:
            print(f"PoS: wrong proposer. Expected {str(expected)[:8]}, got {block.validator_address[:8]}")
            return False

        return True

    def select_proposer(self, height: int,
                        validators: List[ValidatorState]) -> Optional[str]:
        """Stake-weighted VRF selection — deterministic per block height."""
        if not self.stakes:
            return None

        seed = hashlib.sha256(str(height).encode()).hexdigest()
        random.seed(int(seed, 16))

        eligible = [
            (addr, stake) for addr, stake in self.stakes.items()
            if stake >= self.config['min_stake']
            and addr not in self.slashed_validators
        ]
        if not eligible:
            return None

        total_stake = sum(s for _, s in eligible)
        rand_value  = random.uniform(0, total_stake)

        cumulative = 0
        for address, stake in eligible:
            cumulative += stake
            if cumulative >= rand_value:
                return address

        return eligible[0][0]

    def add_stake(self, validator_address: str, amount: float) -> None:
        self.stakes[validator_address] = self.stakes.get(validator_address, 0) + amount
        print(f"PoS: staked {amount} to {validator_address[:8]}. Total: {self.stakes[validator_address]}")

    def remove_stake(self, validator_address: str, amount: float) -> bool:
        current = self.stakes.get(validator_address, 0)
        if current < amount:
            return False
        self.stakes[validator_address] = current - amount
        return True

    def slash_validator(self, validator_address: str, reason: str) -> None:
        if validator_address not in self.stakes:
            return
        penalty = self.stakes[validator_address] * self.config['slashing_penalty']
        self.stakes[validator_address]            -= penalty
        self.slashed_validators[validator_address] = penalty
        print(f"PoS: slashed {validator_address[:8]}: -{penalty} ({reason})")

    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        if block.height % self.config['epoch_length'] == 0:
            self.current_epoch += 1
            print(f"PoS: epoch {self.current_epoch} started")
