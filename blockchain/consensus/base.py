# blockchain/consensus/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState


class BaseConsensus(ABC):
    """
    Base class for all consensus mechanisms
    Provides a plugin interface for different consensus algorithms
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.blockchain = None
        self.name = self.__class__.__name__
        
    @abstractmethod
    def initialize(self, blockchain: 'Blockchain') -> None:
        """
        Initialize consensus mechanism with blockchain instance
        Called when blockchain is created
        """
        self.blockchain = blockchain
    
    @abstractmethod
    def select_transactions(
        self,
        pending_transactions: List[Transaction],
        proposer_address: str
    ) -> List[Transaction]:
        """
        Select transactions to include in the next block
        Returns: List of transactions to include
        """
        pass
    
    @abstractmethod
    def prepare_consensus_data(
        self,
        proposer_address: str,
        previous_block: Block
    ) -> Dict[str, Any]:
        """
        Prepare consensus-specific data for block header
        Returns: Dictionary of consensus data
        """
        pass
    
    @abstractmethod
    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        """
        Validate a proposed block according to consensus rules
        Returns: True if block is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def select_proposer(self, height: int, validators: List) -> Optional[str]:
        """
        Select the next block proposer
        Returns: Validator address who should propose the next block
        """
        pass
    
    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        """
        Callback when a block is committed to the chain
        Can be used to update consensus-specific state
        """
        pass
    
    def get_consensus_params(self) -> Dict[str, Any]:
        """
        Get current consensus parameters
        """
        return self.config
    
    def update_consensus_params(self, params: Dict[str, Any]) -> None:
        """
        Update consensus parameters
        """
        self.config.update(params)


class ConsensusVote:
    """Vote for block validation"""
    
    def __init__(
        self,
        block_hash: str,
        height: int,
        validator_address: str,
        signature: str,
        timestamp: float
    ):
        self.block_hash = block_hash
        self.height = height
        self.validator_address = validator_address
        self.signature = signature
        self.timestamp = timestamp
    
    def to_dict(self) -> dict:
        return {
            'block_hash': self.block_hash,
            'height': self.height,
            'validator_address': self.validator_address,
            'signature': self.signature,
            'timestamp': self.timestamp
        }


class ConsensusRound:
    """Represents a consensus round"""
    
    def __init__(self, height: int, round_num: int):
        self.height = height
        self.round_num = round_num
        self.votes: List[ConsensusVote] = []
        self.proposed_block: Optional[Block] = None
        self.started_at = None
        self.completed_at = None
    
    def add_vote(self, vote: ConsensusVote) -> None:
        """Add a vote to this round"""
        self.votes.append(vote)
    
    def get_vote_count(self) -> int:
        """Get total number of votes"""
        return len(self.votes)
    
    def has_supermajority(self, total_validators: int) -> bool:
        """Check if we have 2/3+ votes"""
        return self.get_vote_count() >= (2 * total_validators // 3) + 1