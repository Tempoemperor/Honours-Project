# blockchain/consensus/pbft.py

import time
from typing import List, Dict, Any, Optional, Set
from .base import BaseConsensus, ConsensusVote
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState
from enum import Enum


class PBFTPhase(Enum):
    PRE_PREPARE = "pre_prepare"
    PREPARE     = "prepare"
    COMMIT      = "commit"
    COMMITTED   = "committed"


class PBFTMessage:
    def __init__(self, phase: PBFTPhase, sequence: int, block_hash: str,
                 validator: str, signature: str):
        self.phase      = phase
        self.sequence   = sequence
        self.block_hash = block_hash
        self.validator  = validator
        self.signature  = signature
        self.timestamp  = time.time()


class PBFT(BaseConsensus):
    """
    Practical Byzantine Fault Tolerant Consensus

    Three-phase commit: PRE-PREPARE → PREPARE → COMMIT
    Tolerates up to f = (n-1)/3 Byzantine faults.
    In single-node simulation, all phases are run internally,
    preserving the full state machine and certificate logic.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time':          3,
            'view_change_timeout': 10,
            'max_block_size':      1000,
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)

        self.view     = 0
        self.sequence = 0
        self.messages:                Dict[int, List[PBFTMessage]] = {}
        self.prepared_certificates:   Dict[str, Set[str]]          = {}
        self.committed_certificates:  Dict[str, Set[str]]          = {}

    def initialize(self, blockchain: 'Blockchain') -> None:
        super().initialize(blockchain)
        print("PBFT consensus initialized")

    def select_transactions(self, pending_transactions: List[Transaction],
                            proposer_address: str) -> List[Transaction]:
        max_size   = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: tx.timestamp)
        return sorted_txs[:max_size]

    def prepare_consensus_data(self, proposer_address: str,
                               previous_block: Block) -> Dict[str, Any]:
        self.sequence += 1
        return {
            'consensus': 'pbft',
            'view':      self.view,
            'sequence':  self.sequence,
            'primary':   proposer_address,
            'phase':     PBFTPhase.PRE_PREPARE.value,
        }

    def _simulate_consensus(self, block: Block) -> bool:
        """
        Simulate the PREPARE and COMMIT phases internally.
        In a real multi-node network these messages come from peer validators.
        Here, the single known validator acts as all replicas.
        The quorum math (2f+1) is fully preserved — with n=1, f=0, required=1.
        """
        validators = self.blockchain.state.get_active_validators()
        required   = 2 * self._calculate_f(len(validators)) + 1

        # PREPARE phase — collect prepare messages
        if block.hash not in self.prepared_certificates:
            self.prepared_certificates[block.hash] = set()
        for v in validators:
            self.prepared_certificates[block.hash].add(v.address)
        prepared = len(self.prepared_certificates[block.hash]) >= required

        # COMMIT phase — collect commit messages
        if block.hash not in self.committed_certificates:
            self.committed_certificates[block.hash] = set()
        for v in validators:
            self.committed_certificates[block.hash].add(v.address)
        committed = len(self.committed_certificates[block.hash]) >= required

        if not prepared:
            print(f"PBFT: insufficient PREPARE messages ({len(self.prepared_certificates[block.hash])}/{required})")
        if not committed:
            print(f"PBFT: insufficient COMMIT messages ({len(self.committed_certificates[block.hash])}/{required})")

        return prepared and committed

    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        validators = state.get_active_validators()
        primary    = self._get_primary(validators)

        if block.validator_address != primary:
            print(f"PBFT: proposer {block.validator_address[:8]} is not primary {str(primary)[:8]}")
            return False

        consensus_data = block.consensus_data
        if consensus_data.get('sequence', 0) != self.sequence:
            print(f"PBFT: sequence mismatch (expected {self.sequence}, got {consensus_data.get('sequence')})")
            return False
        if consensus_data.get('view', -1) != self.view:
            print(f"PBFT: view mismatch (expected {self.view}, got {consensus_data.get('view')})")
            return False

        # Run simulated three-phase commit
        if not self._simulate_consensus(block):
            print("PBFT: three-phase commit failed")
            return False

        return True

    def select_proposer(self, height: int,
                        validators: List[ValidatorState]) -> Optional[str]:
        return self._get_primary(validators)

    def _get_primary(self, validators: List[ValidatorState]) -> Optional[str]:
        if not validators:
            return None
        sorted_validators = sorted(validators, key=lambda v: v.address)
        primary_index     = self.view % len(sorted_validators)
        return sorted_validators[primary_index].address

    def add_prepare_message(self, block_hash: str, validator: str,
                            signature: str) -> bool:
        if block_hash not in self.prepared_certificates:
            self.prepared_certificates[block_hash] = set()
        self.prepared_certificates[block_hash].add(validator)
        validators = self.blockchain.state.get_active_validators()
        required   = 2 * self._calculate_f(len(validators)) + 1
        return len(self.prepared_certificates[block_hash]) >= required

    def add_commit_message(self, block_hash: str, validator: str,
                           signature: str) -> bool:
        if block_hash not in self.committed_certificates:
            self.committed_certificates[block_hash] = set()
        self.committed_certificates[block_hash].add(validator)
        validators = self.blockchain.state.get_active_validators()
        required   = 2 * self._calculate_f(len(validators)) + 1
        return len(self.committed_certificates[block_hash]) >= required

    def _calculate_f(self, n: int) -> int:
        """Maximum Byzantine failures tolerated: f = (n-1)/3"""
        return (n - 1) // 3

    def trigger_view_change(self) -> None:
        self.view += 1
        self.prepared_certificates.clear()
        self.committed_certificates.clear()
        print(f"PBFT: view changed to {self.view}")

    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        if block.hash in self.prepared_certificates:
            del self.prepared_certificates[block.hash]
        if block.hash in self.committed_certificates:
            del self.committed_certificates[block.hash]
