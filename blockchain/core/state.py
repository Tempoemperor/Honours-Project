# blockchain/core/state.py

import json
from typing import Dict, Any, Optional, List
from collections import defaultdict
import copy


class AccountState:
    """Individual account state"""
    
    def __init__(self, address: str, balance: float = 0.0, nonce: int = 0):
        self.address = address
        self.balance = balance
        self.nonce = nonce
        self.storage: Dict[str, Any] = {}
        self.permissions: List[str] = []
    
    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'balance': self.balance,
            'nonce': self.nonce,
            'storage': self.storage,
            'permissions': self.permissions
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AccountState':
        account = cls(data['address'], data['balance'], data['nonce'])
        account.storage = data.get('storage', {})
        account.permissions = data.get('permissions', [])
        return account


class ValidatorState:
    """Validator state"""
    
    def __init__(self, address: str, pub_key: str, power: int = 10, name: str = ""):
        self.address = address
        self.pub_key = pub_key
        self.power = power
        self.name = name
        self.active = True
        self.total_blocks_proposed = 0
        self.total_blocks_signed = 0
    
    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'pub_key': self.pub_key,
            'power': self.power,
            'name': self.name,
            'active': self.active,
            'total_blocks_proposed': self.total_blocks_proposed,
            'total_blocks_signed': self.total_blocks_signed
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ValidatorState':
        validator = cls(
            data['address'],
            data['pub_key'],
            data.get('power', 10),
            data.get('name', '')
        )
        validator.active = data.get('active', True)
        validator.total_blocks_proposed = data.get('total_blocks_proposed', 0)
        validator.total_blocks_signed = data.get('total_blocks_signed', 0)
        return validator


class BlockchainState:
    """
    Manages the entire blockchain state
    """
    
    def __init__(self, chain_id: str):
        self.chain_id = chain_id
        self.accounts: Dict[str, AccountState] = {}
        self.validators: Dict[str, ValidatorState] = {}
        self.height = 0
        self.last_block_hash = "0" * 64
        self.app_hash = "0" * 64
        
        # Custom state storage
        self.custom_state: Dict[str, Any] = {}
    
    def get_account(self, address: str) -> AccountState:
        """Get account state, create if doesn't exist"""
        if address not in self.accounts:
            self.accounts[address] = AccountState(address)
        return self.accounts[address]
    
    def get_validator(self, address: str) -> Optional[ValidatorState]:
        """Get validator state"""
        return self.validators.get(address)
    
    def add_validator(self, validator: ValidatorState) -> None:
        """Add or update validator"""
        self.validators[validator.address] = validator
    
    def remove_validator(self, address: str) -> None:
        """Remove validator"""
        if address in self.validators:
            self.validators[address].active = False
    
    def get_active_validators(self) -> List[ValidatorState]:
        """Get list of active validators"""
        return [v for v in self.validators.values() if v.active]
    
    def transfer(self, from_address: str, to_address: str, amount: float) -> bool:
        """Execute transfer"""
        sender = self.get_account(from_address)
        recipient = self.get_account(to_address)
        
        if sender.balance < amount:
            return False
        
        sender.balance -= amount
        recipient.balance += amount
        sender.nonce += 1
        
        return True
    
    def grant_permission(self, address: str, permission: str) -> None:
        """Grant permission to address"""
        account = self.get_account(address)
        if permission not in account.permissions:
            account.permissions.append(permission)
    
    def revoke_permission(self, address: str, permission: str) -> None:
        """Revoke permission from address"""
        account = self.get_account(address)
        if permission in account.permissions:
            account.permissions.remove(permission)
    
    def has_permission(self, address: str, permission: str) -> bool:
        """Check if address has permission"""
        account = self.get_account(address)
        return permission in account.permissions
    
    def calculate_app_hash(self) -> str:
        """Calculate application state hash"""
        import hashlib
        state_dict = self.to_dict()
        state_string = json.dumps(state_dict, sort_keys=True)
        self.app_hash = hashlib.sha256(state_string.encode()).hexdigest()
        return self.app_hash
    
    def snapshot(self) -> 'BlockchainState':
        """Create state snapshot"""
        return copy.deepcopy(self)
    
    def to_dict(self) -> dict:
        """Convert state to dictionary"""
        return {
            'chain_id': self.chain_id,
            'height': self.height,
            'last_block_hash': self.last_block_hash,
            'app_hash': self.app_hash,
            'accounts': {addr: acc.to_dict() for addr, acc in self.accounts.items()},
            'validators': {addr: val.to_dict() for addr, val in self.validators.items()},
            'custom_state': self.custom_state
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BlockchainState':
        """Create state from dictionary"""
        state = cls(data['chain_id'])
        state.height = data['height']
        state.last_block_hash = data['last_block_hash']
        state.app_hash = data['app_hash']
        state.accounts = {
            addr: AccountState.from_dict(acc)
            for addr, acc in data.get('accounts', {}).items()
        }
        state.validators = {
            addr: ValidatorState.from_dict(val)
            for addr, val in data.get('validators', {}).items()
        }
        state.custom_state = data.get('custom_state', {})
        return state