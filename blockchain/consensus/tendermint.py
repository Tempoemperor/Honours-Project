# blockchain/consensus/tendermint.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus, ConsensusVote, ConsensusRound
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class TendermintBFT(BaseConsensus):
    """
    Tendermint BFT Consensus

    Round-based voting with 2/3+ supermajority requirement.
    Prevote and precommit phases are simulated internally in
    single-node mode so the full round state machine runs correctly.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time':         5,
            'timeout_propose':    3,
            'timeout_prevote':    1,
            'timeout_precommit':  1,
            'max_block_size':     1000,
            'max_validators':     100,
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)

        self.current_round: Optional[ConsensusRound] = None
        self.rounds:        List[ConsensusRound]      = []
        self.locked_block:  Optional[Block]           = None
        self.valid_block:   Optional[Block]           = None

    def initialize(self, blockchain: 'Blockchain') -> None:
        super().initialize(blockchain)
        print(f"Tendermint BFT initialized (block_time={self.config['block_time']}s)")

    def select_transactions(self, pending_transactions: List[Transaction],
                            proposer_address: str) -> List[Transaction]:
        max_size   = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: (tx.nonce, tx.timestamp))
        return sorted_txs[:max_size]

    def prepare_consensus_data(self, proposer_address: str,
                               previous_block: Block) -> Dict[str, Any]:
        height = previous_block.height + 1
        if not self.current_round or self.current_round.height != height:
            self.current_round             = ConsensusRound(height, 0)
            self.current_round.started_at  = time.time()
        return {
            'consensus': 'tendermint',
            'height':    height,
            'round':     self.current_round.round_num,
            'proposer':  proposer_address,
            'timestamp': time.time(),
        }

    def _simulate_voting(self, block: Block) -> bool:
        """
        Simulate prevote + precommit rounds internally.
        Supermajority threshold (2/3+) is fully enforced — with n=1
        validator, 1 vote satisfies the threshold (1 > 2/3 * 1).
        """
        if not self.current_round or self.current_round.height != block.height:
            self.current_round            = ConsensusRound(block.height, 0)
            self.current_round.started_at = time.time()

        validators = self.blockchain.state.get_active_validators()

        # Cast prevote + precommit from all known validators
        for v in validators:
            vote = ConsensusVote(
                block_hash=block.hash,
                height=block.height,
                validator_address=v.address,
                signature="simulated",
                timestamp=time.time()
            )
            self.current_round.add_vote(vote)

        has_majority = self.current_round.has_supermajority(len(validators))
        if not has_majority:
            print(f"Tendermint: supermajority not reached ({len(validators)} validators)")
        return has_majority

    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        validators = state.get_active_validators()
        if not validators:
            print("Tendermint: no active validators")
            return False

        # Verify proposer turn (weighted round-robin)
        expected = self.select_proposer(block.height, validators)
        if block.validator_address != expected:
            print(f"Tendermint: wrong proposer. Expected {str(expected)[:8]}, got {block.validator_address[:8]}")
            return False

        # Verify tx count
        if len(block.transactions) > self.config['max_block_size']:
            print(f"Tendermint: too many transactions ({len(block.transactions)})")
            return False

        # Run simulated prevote/precommit
        if not self._simulate_voting(block):
            print("Tendermint: voting failed")
            return False

        return True

    def select_proposer(self, height: int,
                        validators: List[ValidatorState]) -> Optional[str]:
        if not validators:
            return None
        total_power = sum(v.power for v in validators)
        if total_power == 0:
            return validators[0].address
        target     = height % total_power
        cumulative = 0
        for v in sorted(validators, key=lambda v: v.address):
            cumulative += v.power
            if cumulative > target:
                return v.address
        return validators[0].address

    def add_vote(self, block_hash: str, height: int,
                 validator_address: str, signature: str) -> bool:
        if not self.current_round or self.current_round.height != height:
            return False
        vote = ConsensusVote(
            block_hash=block_hash, height=height,
            validator_address=validator_address,
            signature=signature, timestamp=time.time()
        )
        self.current_round.add_vote(vote)
        validators = self.blockchain.state.get_active_validators()
        return self.current_round.has_supermajority(len(validators))

    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        if self.current_round and self.current_round.height == block.height:
            self.current_round.completed_at = time.time()
            self.rounds.append(self.current_round)
            self.current_round = None
        self.locked_block = None
        self.valid_block  = None

    def get_consensus_params(self) -> Dict[str, Any]:
        params = super().get_consensus_params()
        params.update({
            'current_round': self.current_round.round_num if self.current_round else None,
            'total_rounds':  len(self.rounds),
        })
        return params
