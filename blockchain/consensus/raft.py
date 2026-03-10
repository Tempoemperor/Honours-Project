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
    """Raft node states"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RaftLog:
    """Raft log entry"""
    
    def __init__(self, term: int, index: int, block: Block):
        self.term = term
        self.index = index
        self.block = block
        self.committed = False


class Raft(BaseConsensus):
    """
    Raft Consensus Algorithm
    
    Features:
    - Leader election
    - Log replication
    - Safety through leader completeness
    - Simpler than traditional BFT
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'election_timeout_min': 150,  # milliseconds
            'election_timeout_max': 300,
            'heartbeat_interval': 50,
            'max_block_size': 1000,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.current_leader: Optional[str] = None
        
        self.log: List[RaftLog] = []
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Timing
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize Raft"""
        super().initialize(blockchain)
        print("Raft consensus initialized")
    
    def _random_election_timeout(self) -> float:
        """Get random election timeout"""
        min_timeout = self.config['election_timeout_min'] / 1000
        max_timeout = self.config['election_timeout_max'] / 1000
        return random.uniform(min_timeout, max_timeout)
    
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
        """Prepare Raft consensus data"""
        return {
            'consensus': 'raft',
            'term': self.current_term,
            'leader': self.current_leader,
            'log_index': len(self.log)
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using Raft rules"""
        # Only leader can propose blocks
        if self.state != RaftState.LEADER:
            return False
        
        # Verify proposer is current leader
        if block.validator_address != self.current_leader:
            return False
        
        # Verify term
        consensus_data = block.consensus_data
        if consensus_data.get('term', -1) < self.current_term:
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """Return current leader"""
        return self.current_leader
    
    def start_election(self, node_address: str) -> None:
        """Start leader election"""
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = node_address
        self.election_timeout = self._random_election_timeout()
        
        print(f"Node {node_address[:8]} starting election for term {self.current_term}")
    
    def receive_vote(self, voter: str, term: int, granted: bool) -> None:
        """Receive vote from another node"""
        if term > self.current_term:
            self.current_term = term
            self.state = RaftState.FOLLOWER
            self.voted_for = None
    
    def become_leader(self, node_address: str, validators: List[ValidatorState]) -> None:
        """Become leader after winning election"""
        self.state = RaftState.LEADER
        self.current_leader = node_address
        
        # Initialize leader state
        self.next_index = {v.address: len(self.log) for v in validators}
        self.match_index = {v.address: 0 for v in validators}
        
        print(f"Node {node_address[:8]} became leader for term {self.current_term}")
    
    def step_down(self) -> None:
        """Step down from leader/candidate to follower"""
        self.state = RaftState.FOLLOWER
        self.current_leader = None
    
    def append_entry(self, block: Block) -> None:
        """Append block to Raft log"""
        entry = RaftLog(
            term=self.current_term,
            index=len(self.log),
            block=block
        )
        self.log.append(entry)
    
    def commit_entry(self, index: int) -> None:
        """Commit log entry"""
        if index < len(self.log):
            self.log[index].committed = True
            self.commit_index = max(self.commit_index, index)
    
    def check_heartbeat_timeout(self, node_address: str, validators: List[ValidatorState]) -> bool:
        """Check if election should be started"""
        if self.state == RaftState.LEADER:
            return False
        
        time_since_heartbeat = time.time() - self.last_heartbeat
        if time_since_heartbeat > self.election_timeout:
            self.start_election(node_address)
            return True
        
        return False
    
    def send_heartbeat(self) -> None:
        """Send heartbeat (called by leader)"""
        self.last_heartbeat = time.time()
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Update Raft state after block commit"""
        # Commit corresponding log entry
        for i, entry in enumerate(self.log):
            if entry.block.hash == block.hash:
                self.commit_entry(i)
                break