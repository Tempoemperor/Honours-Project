# blockchain/core/block.py

import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class BlockHeader:
    """Block header containing metadata"""
    version: int
    height: int
    timestamp: float
    previous_hash: str
    merkle_root: str
    validator_address: str
    validator_signature: str
    consensus_data: Dict[str, Any]  # Consensus-specific data
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def hash(self) -> str:
        """Calculate header hash"""
        header_string = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(header_string.encode()).hexdigest()


class Block:
    """
    Core Block class supporting multiple consensus mechanisms
    """
    
    def __init__(
        self,
        height: int,
        previous_hash: str,
        transactions: List['Transaction'],
        validator_address: str,
        consensus_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
        version: int = 1
    ):
        self.height = height
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.validator_address = validator_address
        self.timestamp = timestamp or time.time()
        self.version = version
        self.consensus_data = consensus_data or {}
        
        # Calculate merkle root
        self.merkle_root = self._calculate_merkle_root()
        
        # Header and signature (to be set)
        self.validator_signature = ""
        self.header: Optional[BlockHeader] = None
        self.hash: Optional[str] = None
        
    def _calculate_merkle_root(self) -> str:
        """Calculate Merkle root of transactions"""
        if not self.transactions:
            return hashlib.sha256(b"").hexdigest()
        
        # Get transaction hashes
        tx_hashes = [tx.hash() for tx in self.transactions]
        
        # Build merkle tree
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])  # Duplicate last hash
            
            next_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            
            tx_hashes = next_level
        
        return tx_hashes[0]
    
    def finalize(self, signature: str) -> None:
        """Finalize block with validator signature"""
        self.validator_signature = signature
        
        # Create header
        self.header = BlockHeader(
            version=self.version,
            height=self.height,
            timestamp=self.timestamp,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            validator_address=self.validator_address,
            validator_signature=self.validator_signature,
            consensus_data=self.consensus_data
        )
        
        # Calculate block hash
        self.hash = self.header.hash()
    
    def verify_merkle_root(self) -> bool:
        """Verify merkle root matches transactions"""
        calculated_root = self._calculate_merkle_root()
        return calculated_root == self.merkle_root
    
    def to_dict(self) -> dict:
        """Convert block to dictionary"""
        return {
            'height': self.height,
            'hash': self.hash,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'validator_address': self.validator_address,
            'validator_signature': self.validator_signature,
            'merkle_root': self.merkle_root,
            'consensus_data': self.consensus_data,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Block':
        """Create block from dictionary"""
        from .transaction import Transaction
        
        transactions = [Transaction.from_dict(tx) for tx in data['transactions']]
        
        block = cls(
            height=data['height'],
            previous_hash=data['previous_hash'],
            transactions=transactions,
            validator_address=data['validator_address'],
            consensus_data=data.get('consensus_data', {}),
            timestamp=data['timestamp'],
            version=data.get('version', 1)
        )
        
        block.finalize(data['validator_signature'])
        return block
    
    def __repr__(self) -> str:
        return f"Block(height={self.height}, hash={self.hash[:8]}..., txs={len(self.transactions)})"


class GenesisBlock(Block):
    """Special genesis block"""
    
    def __init__(self, chain_id: str, initial_validators: List[dict], genesis_time: Optional[float] = None):
        self.chain_id = chain_id
        self.initial_validators = initial_validators
        
        # Create genesis transaction
        from .transaction import GenesisTransaction
        genesis_tx = GenesisTransaction(
            chain_id=chain_id,
            validators=initial_validators,
            timestamp=genesis_time or time.time()
        )
        
        super().__init__(
            height=0,
            previous_hash="0" * 64,
            transactions=[genesis_tx],
            validator_address="genesis",
            timestamp=genesis_time or time.time(),
            consensus_data={
                'chain_id': chain_id,
                'genesis': True
            }
        )
        
        # Self-sign genesis block
        self.finalize("genesis_signature")
    
    def __repr__(self) -> str:
        return f"GenesisBlock(chain_id={self.chain_id}, validators={len(self.initial_validators)})"