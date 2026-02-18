# blockchain/network/validator.py

import time
from typing import Dict, List, Optional
from ..core.state import ValidatorState


class ValidatorManager:
    """Manages validator set and rotations"""
    
    def __init__(self):
        self.validators: Dict[str, ValidatorState] = {}
        self.validator_history: List[Dict] = []
    
    def add_validator(self, validator: ValidatorState) -> bool:
        """Add validator"""
        if validator.address in self.validators:
            return False
        
        self.validators[validator.address] = validator
        
        self.validator_history.append({
            'action': 'add',
            'validator': validator.address,
            'timestamp': time.time()
        })
        
        return True
    
    def remove_validator(self, address: str) -> bool:
        """Remove validator"""
        if address not in self.validators:
            return False
        
        self.validators[address].active = False
        
        self.validator_history.append({
            'action': 'remove',
            'validator': address,
            'timestamp': time.time()
        })
        
        return True
    
    def get_validator(self, address: str) -> Optional[ValidatorState]:
        """Get validator by address"""
        return self.validators.get(address)
    
    def get_active_validators(self) -> List[ValidatorState]:
        """Get all active validators"""
        return [v for v in self.validators.values() if v.active]
    
    def get_total_voting_power(self) -> int:
        """Get total voting power of active validators"""
        return sum(v.power for v in self.get_active_validators())
    
    def update_validator_power(self, address: str, new_power: int) -> bool:
        """Update validator voting power"""
        if address not in self.validators:
            return False
        
        old_power = self.validators[address].power
        self.validators[address].power = new_power
        
        self.validator_history.append({
            'action': 'update_power',
            'validator': address,
            'old_power': old_power,
            'new_power': new_power,
            'timestamp': time.time()
        })
        
        return True
    
    def get_validator_stats(self, address: str) -> Optional[Dict]:
        """Get validator statistics"""
        validator = self.get_validator(address)
        if not validator:
            return None
        
        return {
            'address': validator.address,
            'power': validator.power,
            'active': validator.active,
            'blocks_proposed': validator.total_blocks_proposed,
            'blocks_signed': validator.total_blocks_signed,
            'uptime_percentage': self._calculate_uptime(validator)
        }
    
    def _calculate_uptime(self, validator: ValidatorState) -> float:
        """Calculate validator uptime percentage"""
        total_blocks = validator.total_blocks_proposed + validator.total_blocks_signed
        if total_blocks == 0:
            return 100.0
        
        # Simplified uptime calculation
        return min(100.0, (validator.total_blocks_signed / total_blocks) * 100)