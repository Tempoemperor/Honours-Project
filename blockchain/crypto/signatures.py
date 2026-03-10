# blockchain/crypto/signatures.py

import hashlib
from typing import Tuple
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.util import sigencode_string, sigdecode_string


def sign_message(message: str, private_key_hex: str) -> str:
    """
    Sign a message with private key
    
    Args:
        message: Message to sign
        private_key_hex: Hex-encoded private key
        
    Returns:
        Hex-encoded signature
    """
    # Create signing key
    private_key = SigningKey.from_string(
        bytes.fromhex(private_key_hex),
        curve=SECP256k1
    )
    
    # Hash message
    message_hash = hashlib.sha256(message.encode()).digest()
    
    # Sign
    signature = private_key.sign(
        message_hash,
        sigencode=sigencode_string
    )
    
    return signature.hex()


def verify_signature(message: str, signature_hex: str, public_key_hex: str) -> bool:
    """
    Verify a signature
    
    Args:
        message: Original message
        signature_hex: Hex-encoded signature
        public_key_hex: Hex-encoded public key
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Create verifying key
        public_key = VerifyingKey.from_string(
            bytes.fromhex(public_key_hex),
            curve=SECP256k1
        )
        
        # Hash message
        message_hash = hashlib.sha256(message.encode()).digest()
        
        # Verify signature
        signature = bytes.fromhex(signature_hex)
        public_key.verify(
            signature,
            message_hash,
            sigdecode=sigdecode_string
        )
        
        return True
        
    except (BadSignatureError, Exception):
        return False


def sign_transaction(transaction_hash: str, private_key_hex: str) -> str:
    """
    Sign a transaction hash
    
    Args:
        transaction_hash: Hash of the transaction
        private_key_hex: Hex-encoded private key
        
    Returns:
        Hex-encoded signature
    """
    return sign_message(transaction_hash, private_key_hex)


def verify_transaction_signature(
    transaction_hash: str,
    signature_hex: str,
    public_key_hex: str
) -> bool:
    """
    Verify a transaction signature
    
    Args:
        transaction_hash: Hash of the transaction
        signature_hex: Hex-encoded signature
        public_key_hex: Hex-encoded public key
        
    Returns:
        True if signature is valid, False otherwise
    """
    return verify_signature(transaction_hash, signature_hex, public_key_hex)


def sign_block(block_hash: str, private_key_hex: str) -> str:
    """
    Sign a block hash
    
    Args:
        block_hash: Hash of the block
        private_key_hex: Hex-encoded private key
        
    Returns:
        Hex-encoded signature
    """
    return sign_message(block_hash, private_key_hex)


def verify_block_signature(
    block_hash: str,
    signature_hex: str,
    public_key_hex: str
) -> bool:
    """
    Verify a block signature
    
    Args:
        block_hash: Hash of the block
        signature_hex: Hex-encoded signature
        public_key_hex: Hex-encoded public key
        
    Returns:
        True if signature is valid, False otherwise
    """
    return verify_signature(block_hash, signature_hex, public_key_hex)


def multisig_sign(message: str, private_keys: list) -> list:
    """
    Create multiple signatures for multisig
    
    Args:
        message: Message to sign
        private_keys: List of hex-encoded private keys
        
    Returns:
        List of hex-encoded signatures
    """
    signatures = []
    for private_key in private_keys:
        signature = sign_message(message, private_key)
        signatures.append(signature)
    
    return signatures


def multisig_verify(
    message: str,
    signatures: list,
    public_keys: list,
    threshold: int
) -> bool:
    """
    Verify multisig signatures
    
    Args:
        message: Original message
        signatures: List of hex-encoded signatures
        public_keys: List of hex-encoded public keys
        threshold: Minimum number of valid signatures required
        
    Returns:
        True if threshold met, False otherwise
    """
    valid_count = 0
    
    for signature, public_key in zip(signatures, public_keys):
        if verify_signature(message, signature, public_key):
            valid_count += 1
    
    return valid_count >= threshold