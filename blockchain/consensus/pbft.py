# blockchain/consensus/pbft.py

import time
from typing import List, Dict, Any, Optional, Set
from .base import BaseConsensus, ConsensusVote
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState
from enum import Enum


class PBFTPhase(Enum):
    """PBFT consensus phases"""
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    COMMITTED = "committed"


class PBFTMessage:
    """PBFT consensus message"""
    
    def __init__(
        self,
        phase: PBFTPhase,
        sequence: int,
        block_hash: str,
        validator: str,
        signature: str
    ):
        self.phase = phase
        self.sequence = sequence
        self.block_hash = block_hash
        self.validator = validator
        self.signature = signature
        self.timestamp = time.time()


class PBFT(BaseConsensus):
    """
    Practical Byzantine Fault Tolerant Consensus
    
    Features:
    - Three-phase commit protocol
    - Tolerates up to f = (n-1)/3 Byzantine faults
    - Primary-backup replication
    - View changes for fault tolerance
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time': 3,
            'view_change_timeout': 10,
            'max_block_size': 1000,
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        self.view = 0
        self.sequence = 0
        self.messages: Dict[int, List[PBFTMessage]] = {}
        self.prepared_certificates: Dict[str, Set[str]] = {}
        self.committed_certificates: Dict[str, Set[str]] = {}
    
    def initialize(self, blockchain: 'Blockchain') -> None:
        """Initialize PBFT"""
        super().initialize(blockchain)
        print("PBFT consensus initialized")
    
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
        """Prepare PBFT consensus data"""
        self.sequence += 1
        
        return {
            'consensus': 'pbft',
            'view': self.view,
            'sequence': self.sequence,
            'primary': proposer_address,
            'phase': PBFTPhase.PRE_PREPARE.value
        }
    
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """Validate block using PBFT rules"""
        # Verify proposer is the primary
        validators = state.get_active_validators()
        primary = self._get_primary(validators)
        
        if block.validator_address != primary:
            return False
        
        # Verify sequence number
        consensus_data = block.consensus_data
        if consensus_data.get('sequence', 0) != self.sequence:
            return False
        
        # Verify view number
        if consensus_data.get('view', -1) != self.view:
            return False
        
        return True
    
    def select_proposer(self, height: int, validators: List[ValidatorState]) -> Optional[str]:
        """Select primary validator"""
        return self._get_primary(validators)
    
    def _get_primary(self, validators: List[ValidatorState]) -> Optional[str]:
        """Get current primary based on view"""
        if not validators:
            return None
        
        sorted_validators = sorted(validators, key=lambda v: v.address)
        primary_index = self.view % len(sorted_validators)
        return sorted_validators[primary_index].address
    
    def add_prepare_message(
        self,
        block_hash: str,
        validator: str,
        signature: str
    ) -> bool:
        """Add PREPARE message"""
        if block_hash not in self.prepared_certificates:
            self.prepared_certificates[block_hash] = set()
        
        self.prepared_certificates[block_hash].add(validator)
        
        # Check if we have 2f+1 PREPARE messages
        validators = self.blockchain.state.get_active_validators()
        required = 2 * self._calculate_f(len(validators)) + 1
        
        return len(self.prepared_certificates[block_hash]) >= required
    
    def add_commit_message(
        self,
        block_hash: str,
        validator: str,
        signature: str
    ) -> bool:
        """Add COMMIT message"""
        if block_hash not in self.committed_certificates:
            self.committed_certificates[block_hash] = set()
        
        self.committed_certificates[block_hash].add(validator)
        
        # Check if we have 2f+1 COMMIT messages
        validators = self.blockchain.state.get_active_validators()
        required = 2 * self._calculate_f(len(validators)) + 1
        
        return len(self.committed_certificates[block_hash]) >= required
    
    def _calculate_f(self, n: int) -> int:
        """Calculate maximum Byzantine failures: f = (n-1)/3"""
        return (n - 1) // 3
    
    def trigger_view_change(self) -> None:
        """Trigger view change (when primary is faulty)"""
        self.view += 1
        self.prepared_certificates.clear()
        self.committed_certificates.clear()
        print(f"View changed to {self.view}")
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """Cleanup after block commit"""
        # Clear certificates for this block
        if block.hash in self.prepared_certificates:
            del self.prepared_certificates[block.hash]
        if block.hash in self.committed_certificates:
            del self.committed_certificates[block.hash]