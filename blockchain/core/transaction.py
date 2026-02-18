# blockchain/core/transaction.py

import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


class TransactionType(Enum):
    """Transaction types"""
    TRANSFER = "transfer"
    DEPLOY_CONTRACT = "deploy_contract"
    CALL_CONTRACT = "call_contract"
    VALIDATOR_UPDATE = "validator_update"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    GENESIS = "genesis"
    CUSTOM = "custom"


@dataclass
class TransactionInput:
    """Transaction input"""
    from_address: str
    amount: Optional[float] = None
    data: Optional[Dict[str, Any]] = None


@dataclass
class TransactionOutput:
    """Transaction output"""
    to_address: str
    amount: Optional[float] = None
    data: Optional[Dict[str, Any]] = None


class Transaction:
    """
    Base transaction class
    """
    
    def __init__(
        self,
        tx_type: TransactionType,
        sender: str,
        inputs: List[TransactionInput],
        outputs: List[TransactionOutput],
        data: Optional[Dict[str, Any]] = None,
        nonce: Optional[int] = None,
        timestamp: Optional[float] = None,
        signature: Optional[str] = None,
        public_key: Optional[str] = None
    ):
        self.tx_type = tx_type
        self.sender = sender
        self.inputs = inputs
        self.outputs = outputs
        self.data = data or {}
        self.nonce = nonce or 0
        self.timestamp = timestamp or time.time()
        self.signature = signature or ""
        self.public_key = public_key or ""  # Store public key to allow verification
        self._hash: Optional[str] = None
    
    def hash(self) -> str:
        """Calculate transaction hash"""
        if self._hash:
            return self._hash
        
        tx_dict = {
            'type': self.tx_type.value,
            'sender': self.sender,
            'inputs': [asdict(inp) for inp in self.inputs],
            'outputs': [asdict(out) for out in self.outputs],
            'data': self.data,
            'nonce': self.nonce,
            'timestamp': self.timestamp,
            # Note: Signature and Public Key are NOT part of the hash
        }
        
        tx_string = json.dumps(tx_dict, sort_keys=True)
        self._hash = hashlib.sha256(tx_string.encode()).hexdigest()
        return self._hash
    
    def sign(self, private_key: str) -> None:
        """Sign transaction with private key and attach public key"""
        from ..crypto.signatures import sign_message
        from ..crypto.keys import KeyPair
        
        # 1. Sign the message
        message = self.hash()
        self.signature = sign_message(message, private_key)
        
        # 2. Derive and store the public key (Required for verification)
        # We assume private_key is hex string
        key_pair = KeyPair(private_key)
        self.public_key = key_pair.get_public_key_hex()
    
    def verify_signature(self, public_key: str = None) -> bool:
        """Verify transaction signature"""
        from ..crypto.signatures import verify_signature
        
        # Use provided key or stored key
        key_to_use = public_key or self.public_key
        if not key_to_use:
            return False
            
        message = self.hash()
        return verify_signature(message, self.signature, key_to_use)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'hash': self.hash(),
            'type': self.tx_type.value,
            'sender': self.sender,
            'inputs': [asdict(inp) for inp in self.inputs],
            'outputs': [asdict(out) for out in self.outputs],
            'data': self.data,
            'nonce': self.nonce,
            'timestamp': self.timestamp,
            'signature': self.signature,
            'public_key': self.public_key
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        """Create transaction from dictionary"""
        tx_type = TransactionType(data['type'])
        inputs = [TransactionInput(**inp) for inp in data['inputs']]
        outputs = [TransactionOutput(**out) for out in data['outputs']]
        
        return cls(
            tx_type=tx_type,
            sender=data['sender'],
            inputs=inputs,
            outputs=outputs,
            data=data.get('data'),
            nonce=data.get('nonce', 0),
            timestamp=data['timestamp'],
            signature=data.get('signature', ''),
            public_key=data.get('public_key', '')
        )
    
    def __repr__(self) -> str:
        return f"Transaction(type={self.tx_type.value}, hash={self.hash()[:8]}...)"


class GenesisTransaction(Transaction):
    """Special genesis transaction"""
    
    def __init__(self, chain_id: str, validators: List[dict], timestamp: Optional[float] = None):
        super().__init__(
            tx_type=TransactionType.GENESIS,
            sender="genesis",
            inputs=[],
            outputs=[],
            data={
                'chain_id': chain_id,
                'validators': validators,
                'genesis_time': timestamp or time.time()
            },
            timestamp=timestamp or time.time()
        )
        
        # Genesis transaction is self-signed/special
        self.signature = "genesis_signature"


class TransferTransaction(Transaction):
    """Simple transfer transaction"""
    
    def __init__(
        self,
        sender: str,
        recipient: str,
        amount: float,
        nonce: int,
        timestamp: Optional[float] = None
    ):
        super().__init__(
            tx_type=TransactionType.TRANSFER,
            sender=sender,
            inputs=[TransactionInput(from_address=sender, amount=amount)],
            outputs=[TransactionOutput(to_address=recipient, amount=amount)],
            nonce=nonce,
            timestamp=timestamp
        )


class ValidatorUpdateTransaction(Transaction):
    """Update validator set"""
    
    def __init__(
        self,
        sender: str,
        validator_address: str,
        action: str,  # "add" or "remove"
        power: int = 10,
        nonce: int = 0,
        timestamp: Optional[float] = None
    ):
        super().__init__(
            tx_type=TransactionType.VALIDATOR_UPDATE,
            sender=sender,
            inputs=[],
            outputs=[],
            data={
                'validator_address': validator_address,
                'action': action,
                'power': power
            },
            nonce=nonce,
            timestamp=timestamp
        )

class PermissionTransaction(Transaction):
    """Grant or revoke permissions or Change Security Levels"""
    
    def __init__(
        self,
        sender: str,
        target_address: str,
        permission: Optional[str] = None,
        action: str = "grant",  # "grant", "revoke", or "set_level"
        level: Optional[int] = None,
        nonce: int = 0,
        timestamp: Optional[float] = None
    ):
        if action == "set_level":
            tx_type = TransactionType.PERMISSION_GRANT
        else:
            tx_type = TransactionType.PERMISSION_GRANT if action == "grant" else TransactionType.PERMISSION_REVOKE
        
        data_payload = {
            'target_address': target_address,
            'action': action
        }
        
        if permission:
            data_payload['permission'] = permission
        if level is not None:
            data_payload['new_level'] = level

        super().__init__(
            tx_type=tx_type,
            sender=sender,
            inputs=[],
            outputs=[],
            data=data_payload,
            nonce=nonce,
            timestamp=timestamp
        )