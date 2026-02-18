# blockchain/__init__.py (UPDATED)

"""
Permissioned Blockchain with Pluggable Consensus and Multi-Level Permissions
"""

__version__ = "1.0.0"

from .core.block import Block, GenesisBlock, BlockHeader
from .core.blockchain import Blockchain
from .core.transaction import (
    Transaction,
    TransactionType,
    TransferTransaction,
    ValidatorUpdateTransaction,
    PermissionTransaction
)
from .core.state import BlockchainState, AccountState, ValidatorState
from .core.merkle import MerkleTree, MerkleProof, build_merkle_tree_from_hashes

# All 10 Consensus mechanisms
from .consensus.base import BaseConsensus
from .consensus.tendermint import TendermintBFT
from .consensus.pbft import PBFT
from .consensus.raft import Raft
from .consensus.poa import ProofOfAuthority
from .consensus.pos import ProofOfStake
from .consensus.dpos import DelegatedProofOfStake
from .consensus.round_robin import RoundRobin
from .consensus.lottery import LotteryConsensus
from .consensus.voting import VotingBasedConsensus
from .consensus.hybrid import HybridConsensus

# Cryptography
from .crypto.keys import KeyPair, generate_keypair, generate_validator_keys
from .crypto.signatures import sign_message, verify_signature

# Permissions
from .permissions.acl import AccessControlList, Permission
from .permissions.rbac import RoleBasedAccessControl, Role
from .permissions.multi_level import (
    MultiLevelPermissionSystem,
    SecurityClassification,
    DataItem
)

__all__ = [
    # Core
    'Block',
    'GenesisBlock',
    'BlockHeader',
    'Blockchain',
    'Transaction',
    'TransactionType',
    'TransferTransaction',
    'ValidatorUpdateTransaction',
    'PermissionTransaction',
    'BlockchainState',
    'AccountState',
    'ValidatorState',
    'MerkleTree',
    'MerkleProof',
    'build_merkle_tree_from_hashes',
    
    # All 10 Consensus Mechanisms
    'BaseConsensus',
    'TendermintBFT',
    'PBFT',
    'Raft',
    'ProofOfAuthority',
    'ProofOfStake',
    'DelegatedProofOfStake',
    'RoundRobin',
    'LotteryConsensus',
    'VotingBasedConsensus',
    'HybridConsensus',
    
    # Crypto
    'KeyPair',
    'generate_keypair',
    'generate_validator_keys',
    'sign_message',
    'verify_signature',
    
    # Permissions
    'AccessControlList',
    'Permission',
    'RoleBasedAccessControl',
    'Role',
    'MultiLevelPermissionSystem',
    'SecurityClassification',
    'DataItem',
]