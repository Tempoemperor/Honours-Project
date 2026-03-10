# blockchain/consensus/raft.py

import time
import random
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState
from enum import Enum


class RaftState(Enum):
    FOLLOWER  = "follower"
    CANDIDATE = "candidate"
    LEADER    = "leader"


class RaftLog:
    def __init__(self, term: int, index: int, block: Block):
        self.term      = term
        self.index     = index
        self.block     = block
        self.committed = False


class Raft(BaseConsensus):
    """
    Raft Consensus

    Leader election → log replication → commit.
    In single-node simulation the node immediately wins its own
    election (majority of 1), becoming leader before the first block.
    Full term/log state is maintained correctly.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'election_timeout_min': 150,
            'election_timeout_max': 300,
            'heartbeat_interval':   50,
            'max_block_size':       1000,
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)

        self.state:           RaftState      = RaftState.FOLLOWER
        self.current_term:    int            = 0
        self.voted_for:       Optional[str]  = None
        self.current_leader:  Optional[str]  = None

        self.log:             List[RaftLog]  = []
        self.commit_index:    int            = 0
        self.last_applied:    int            = 0

        self.next_index:      Dict[str, int] = {}
        self.match_index:     Dict[str, int] = {}

        self.last_heartbeat:    float = time.time()
        self.election_timeout:  float = self._random_election_timeout()

    def initialize(self, blockchain: 'Blockchain') -> None:
        super().initialize(blockchain)
        # Simulate election immediately — single node always wins
        validators = blockchain.state.get_active_validators()
        if validators:
            self._simulate_election(validators[0].address, validators)
        print("Raft consensus initialized")

    def _random_election_timeout(self) -> float:
        return random.uniform(
            self.config['election_timeout_min'] / 1000,
            self.config['election_timeout_max'] / 1000
        )

    def _simulate_election(self, node_address: str,
                           validators: List[ValidatorState]) -> None:
        """
        Simulate leader election. With n=1, one vote = majority.
        Full term increment and vote tracking are preserved.
        """
        self.state        = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for    = node_address
        print(f"Raft: node {node_address[:8]} running election for term {self.current_term}")

        # Single node wins immediately with its own vote (majority = 1)
        self.state          = RaftState.LEADER
        self.current_leader = node_address
        self.next_index     = {v.address: len(self.log) for v in validators}
        self.match_index    = {v.address: 0 for v in validators}
        print(f"Raft: node {node_address[:8]} elected leader (term {self.current_term})")

    def select_transactions(self, pending_transactions: List[Transaction],
                            proposer_address: str) -> List[Transaction]:
        max_size   = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: tx.timestamp)
        return sorted_txs[:max_size]

    def prepare_consensus_data(self, proposer_address: str,
                               previous_block: Block) -> Dict[str, Any]:
        # Re-elect if leader state was lost (e.g. after cache rebuild)
        if self.state != RaftState.LEADER or self.current_leader != proposer_address:
            validators = self.blockchain.state.get_active_validators()
            self._simulate_election(proposer_address, validators)
        return {
            'consensus': 'raft',
            'term':      self.current_term,
            'leader':    self.current_leader,
            'log_index': len(self.log),
        }

    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        # Re-elect if needed (handles restart / cache rebuild)
        if self.state != RaftState.LEADER or self.current_leader != block.validator_address:
            validators = state.get_active_validators()
            self._simulate_election(block.validator_address, validators)

        if block.validator_address != self.current_leader:
            print(f"Raft: proposer {block.validator_address[:8]} is not the leader")
            return False

        consensus_data = block.consensus_data
        if consensus_data.get('term', -1) < self.current_term:
            print(f"Raft: stale term in block ({consensus_data.get('term')} < {self.current_term})")
            return False

        # Append to Raft log (replication step)
        self.append_entry(block)
        return True

    def select_proposer(self, height: int,
                        validators: List[ValidatorState]) -> Optional[str]:
        return self.current_leader

    def start_election(self, node_address: str) -> None:
        validators = self.blockchain.state.get_active_validators()
        self._simulate_election(node_address, validators)

    def receive_vote(self, voter: str, term: int, granted: bool) -> None:
        if term > self.current_term:
            self.current_term = term
            self.state        = RaftState.FOLLOWER
            self.voted_for    = None

    def become_leader(self, node_address: str,
                      validators: List[ValidatorState]) -> None:
        self._simulate_election(node_address, validators)

    def step_down(self) -> None:
        self.state          = RaftState.FOLLOWER
        self.current_leader = None

    def append_entry(self, block: Block) -> None:
        entry = RaftLog(term=self.current_term, index=len(self.log), block=block)
        self.log.append(entry)

    def commit_entry(self, index: int) -> None:
        if index < len(self.log):
            self.log[index].committed = True
            self.commit_index         = max(self.commit_index, index)

    def send_heartbeat(self) -> None:
        self.last_heartbeat = time.time()

    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        for i, entry in enumerate(self.log):
            if entry.block.hash == block.hash:
                self.commit_entry(i)
                break
