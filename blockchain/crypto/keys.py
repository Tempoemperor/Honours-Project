# blockchain/crypto/keys.py

import hashlib
import secrets
from typing import Tuple, Optional
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from ecdsa.util import sigencode_string, sigdecode_string
import base64


class KeyPair:
    """Cryptographic key pair for blockchain operations"""
    
    def __init__(self, private_key: Optional[str] = None):
        """
        Initialize key pair
        
        Args:
            private_key: Hex-encoded private key (generates new if None)
        """
        if private_key:
            self.private_key = SigningKey.from_string(
                bytes.fromhex(private_key),
                curve=SECP256k1
            )
        else:
            self.private_key = SigningKey.generate(curve=SECP256k1)
        
        self.public_key = self.private_key.get_verifying_key()
    
    def get_private_key_hex(self) -> str:
        """Get private key as hex string"""
        return self.private_key.to_string().hex()
    
    def get_public_key_hex(self) -> str:
        """Get public key as hex string"""
        return self.public_key.to_string().hex()
    
    def get_address(self) -> str:
        """
        Generate address from public key
        Similar to Ethereum address generation
        """
        # Hash public key
        pub_key_bytes = self.public_key.to_string()
        hash_obj = hashlib.sha256(pub_key_bytes)
        hash_bytes = hash_obj.digest()
        
        # Take last 20 bytes and encode as hex
        address = hash_bytes[-20:].hex()
        return f"0x{address}"
    
    def to_dict(self) -> dict:
        """Export key pair to dictionary"""
        return {
            'private_key': self.get_private_key_hex(),
            'public_key': self.get_public_key_hex(),
            'address': self.get_address()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'KeyPair':
        """Import key pair from dictionary"""
        return cls(private_key=data['private_key'])


def generate_keypair() -> KeyPair:
    """Generate a new cryptographic key pair"""
    return KeyPair()


def generate_validator_keys(num_validators: int) -> List[dict]:
    """
    Generate keys for multiple validators
    
    Args:
        num_validators: Number of validator key pairs to generate
        
    Returns:
        List of validator info dictionaries
    """
    validators = []
    
    for i in range(num_validators):
        keypair = generate_keypair()
        validators.append({
            'name': f'validator_{i}',
            'address': keypair.get_address(),
            'pub_key': keypair.get_public_key_hex(),
            'private_key': keypair.get_private_key_hex(),
            'power': 10
        })
    
    return validators


def address_from_public_key(public_key_hex: str) -> str:
    """
    Generate address from public key
    
    Args:
        public_key_hex: Hex-encoded public key
        
    Returns:
        Address string
    """
    pub_key_bytes = bytes.fromhex(public_key_hex)
    hash_obj = hashlib.sha256(pub_key_bytes)
    hash_bytes = hash_obj.digest()
    address = hash_bytes[-20:].hex()
    return f"0x{address}"


def generate_random_bytes(length: int = 32) -> bytes:
    """Generate cryptographically secure random bytes"""
    return secrets.token_bytes(length)


def hash_data(data: bytes) -> str:
    """Hash data using SHA-256"""
    return hashlib.sha256(data).hexdigest()


def hash_string(text: str) -> str:
    """Hash string using SHA-256"""
    return hashlib.sha256(text.encode()).hexdigest()