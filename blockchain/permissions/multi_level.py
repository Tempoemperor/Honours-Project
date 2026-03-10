# blockchain/permissions/multi_level.py

import time
from typing import Dict, List, Optional, Set
from enum import IntEnum


class PermissionLevel(IntEnum):
    """Permission levels - higher number = more access"""
    def __new__(cls, value):
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj


class SecurityClassification:
    """Security classification for data/resources"""
    
    def __init__(self, level: int, name: str, description: str = ""):
        self.level = level
        self.name = name
        self.description = description
    
    def __repr__(self):
        return f"Level {self.level}: {self.name}"
    
    def to_dict(self) -> dict:
        return {
            'level': self.level,
            'name': self.name,
            'description': self.description
        }


class DataItem:
    """Represents data with security classification"""
    
    def __init__(
        self,
        data_id: str,
        content: any,
        security_level: int,
        owner: str,
        metadata: Optional[Dict] = None
    ):
        self.data_id = data_id
        self.content = content
        self.security_level = security_level
        self.owner = owner
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.accessed_by: List[Dict] = []
    
    def record_access(self, accessor: str) -> None:
        """Record who accessed this data"""
        self.accessed_by.append({
            'accessor': accessor,
            'timestamp': time.time()
        })
    
    def to_dict(self) -> dict:
        return {
            'data_id': self.data_id,
            'security_level': self.security_level,
            'owner': self.owner,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'access_count': len(self.accessed_by)
        }


class MultiLevelPermissionSystem:
    """
    Multi-Level Permission System for Blockchain
    
    Features:
    - Configurable number of permission levels
    - Hierarchical access control
    - Users can only promote to their own level or below
    - Creator has maximum permission level
    - Audit trail of all permission changes
    """
    
    def __init__(self, num_levels: int, creator_address: str, level_names: Optional[List[str]] = None):
        """
        Initialize multi-level permission system
        
        Args:
            num_levels: Number of permission levels (2-10)
            creator_address: Address of blockchain creator (gets max level)
            level_names: Optional names for each level
        """
        if num_levels < 2 or num_levels > 10:
            raise ValueError("Number of levels must be between 2 and 10")
        
        self.num_levels = num_levels
        self.max_level = num_levels
        self.min_level = 1
        self.creator_address = creator_address
        
        # User permissions: address -> level
        self.user_levels: Dict[str, int] = {}
        
        # Set creator to max level
        self.user_levels[creator_address] = self.max_level
        
        # Security classifications
        self.security_classifications: Dict[int, SecurityClassification] = {}
        self._initialize_classifications(level_names)
        
        # Data storage with security levels
        self.data_store: Dict[str, DataItem] = {}
        
        # Audit log
        self.audit_log: List[Dict] = []
        
        # Default: all new users start at level 1
        self.default_level = self.min_level
        
        self._log_action("system_init", creator_address, {
            'num_levels': num_levels,
            'creator': creator_address
        })
    
    def _initialize_classifications(self, level_names: Optional[List[str]]) -> None:
        """Initialize security classifications"""
        if level_names and len(level_names) == self.num_levels:
            names = level_names
        else:
            # Default names
            default_names = [
                "Public", "Internal", "Confidential", "Secret", 
                "Top Secret", "Critical", "Ultra Secret", "Maximum Secret",
                "Cosmic Top Secret", "Beyond Black"
            ]
            names = default_names[:self.num_levels]
        
        for level in range(1, self.num_levels + 1):
            self.security_classifications[level] = SecurityClassification(
                level=level,
                name=names[level - 1],
                description=f"Security level {level}"
            )
    
    def get_user_level(self, address: str) -> int:
        """
        Get permission level for user
        New users default to level 1
        """
        if address not in self.user_levels:
            self.user_levels[address] = self.default_level
            self._log_action("user_registered", address, {
                'level': self.default_level,
                'auto_assigned': True
            })
        
        return self.user_levels[address]
    
    def promote_user(
        self,
        promoter_address: str,
        target_address: str,
        new_level: int
    ) -> bool:
        """
        Promote user to a higher permission level
        
        Rules:
        - Promoter must have higher level than target's current level
        - Can only promote to promoter's level or below
        - Cannot demote (use demote_user for that)
        - Creator can promote anyone to any level
        
        Args:
            promoter_address: Address of user doing the promotion
            target_address: Address of user being promoted
            new_level: New permission level
            
        Returns:
            True if promotion successful, False otherwise
        """
        # Validate level
        if new_level < self.min_level or new_level > self.max_level:
            return False
        
        promoter_level = self.get_user_level(promoter_address)
        target_current_level = self.get_user_level(target_address)
        
        # Check if trying to promote (not demote)
        if new_level <= target_current_level:
            return False
        
        # Creator can promote anyone to any level
        if promoter_address == self.creator_address:
            self.user_levels[target_address] = new_level
            self._log_action("promote", promoter_address, {
                'target': target_address,
                'old_level': target_current_level,
                'new_level': new_level,
                'by_creator': True
            })
            return True
        
        # Check promoter authority
        # Must have higher level than target
        if promoter_level <= target_current_level:
            return False
        
        # Can only promote to promoter's level or below
        if new_level > promoter_level:
            return False
        
        # Perform promotion
        self.user_levels[target_address] = new_level
        
        self._log_action("promote", promoter_address, {
            'target': target_address,
            'old_level': target_current_level,
            'new_level': new_level
        })
        
        return True
    
    def demote_user(
        self,
        demoter_address: str,
        target_address: str,
        new_level: int
    ) -> bool:
        """
        Demote user to a lower permission level
        
        Rules:
        - Similar to promotion rules
        - Can only demote users below demoter's level
        - Cannot demote creator
        
        Args:
            demoter_address: Address of user doing the demotion
            target_address: Address of user being demoted
            new_level: New permission level
            
        Returns:
            True if demotion successful, False otherwise
        """
        # Cannot demote creator
        if target_address == self.creator_address:
            return False
        
        # Validate level
        if new_level < self.min_level or new_level > self.max_level:
            return False
        
        demoter_level = self.get_user_level(demoter_address)
        target_current_level = self.get_user_level(target_address)
        
        # Check if trying to demote (not promote)
        if new_level >= target_current_level:
            return False
        
        # Creator can demote anyone
        if demoter_address == self.creator_address:
            self.user_levels[target_address] = new_level
            self._log_action("demote", demoter_address, {
                'target': target_address,
                'old_level': target_current_level,
                'new_level': new_level,
                'by_creator': True
            })
            return True
        
        # Must have higher level than target to demote
        if demoter_level <= target_current_level:
            return False
        
        # Perform demotion
        self.user_levels[target_address] = new_level
        
        self._log_action("demote", demoter_address, {
            'target': target_address,
            'old_level': target_current_level,
            'new_level': new_level
        })
        
        return True
    
    def can_access_data(self, user_address: str, security_level: int) -> bool:
        """
        Check if user can access data at given security level
        
        Rule: User can access data at their level or below
        
        Args:
            user_address: Address of user
            security_level: Security level of data
            
        Returns:
            True if user has access, False otherwise
        """
        user_level = self.get_user_level(user_address)
        return user_level >= security_level
    
    def store_data(
        self,
        data_id: str,
        content: any,
        security_level: int,
        owner_address: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Store data with security classification
        
        Args:
            data_id: Unique identifier for data
            content: Data content
            security_level: Security level (1 to num_levels)
            owner_address: Address of data owner
            metadata: Optional metadata
            
        Returns:
            True if stored successfully, False otherwise
        """
        # Validate security level
        if security_level < self.min_level or security_level > self.max_level:
            return False
        
        # Check if owner has sufficient level to create data at this level
        owner_level = self.get_user_level(owner_address)
        if owner_level < security_level:
            return False
        
        # Store data
        data_item = DataItem(
            data_id=data_id,
            content=content,
            security_level=security_level,
            owner=owner_address,
            metadata=metadata
        )
        
        self.data_store[data_id] = data_item
        
        self._log_action("store_data", owner_address, {
            'data_id': data_id,
            'security_level': security_level
        })
        
        return True
    
    def access_data(self, user_address: str, data_id: str) -> Optional[any]:
        """
        Access data if user has sufficient permission
        
        Args:
            user_address: Address of user accessing data
            data_id: ID of data to access
            
        Returns:
            Data content if accessible, None otherwise
        """
        if data_id not in self.data_store:
            return None
        
        data_item = self.data_store[data_id]
        
        # Check access permission
        if not self.can_access_data(user_address, data_item.security_level):
            self._log_action("access_denied", user_address, {
                'data_id': data_id,
                'required_level': data_item.security_level,
                'user_level': self.get_user_level(user_address)
            })
            return None
        
        # Record access
        data_item.record_access(user_address)
        
        self._log_action("access_data", user_address, {
            'data_id': data_id,
            'security_level': data_item.security_level
        })
        
        return data_item.content
    
    def get_accessible_data(self, user_address: str) -> List[DataItem]:
        """
        Get all data items accessible to user
        
        Args:
            user_address: Address of user
            
        Returns:
            List of accessible data items
        """
        user_level = self.get_user_level(user_address)
        
        accessible = []
        for data_item in self.data_store.values():
            if user_level >= data_item.security_level:
                accessible.append(data_item)
        
        return accessible
    
    def get_users_by_level(self, level: int) -> List[str]:
        """Get all users at a specific permission level"""
        return [
            address for address, user_level in self.user_levels.items()
            if user_level == level
        ]
    
    def get_level_statistics(self) -> Dict[int, int]:
        """Get count of users at each level"""
        stats = {level: 0 for level in range(self.min_level, self.max_level + 1)}
        
        for user_level in self.user_levels.values():
            stats[user_level] += 1
        
        return stats
    
    def get_classification_info(self, level: int) -> Optional[SecurityClassification]:
        """Get security classification information for a level"""
        return self.security_classifications.get(level)
    
    def _log_action(self, action: str, actor: str, details: Dict) -> None:
        """Log action to audit trail"""
        self.audit_log.append({
            'action': action,
            'actor': actor,
            'details': details,
            'timestamp': time.time()
        })
    
    def get_audit_log(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get audit log with optional filters
        
        Args:
            actor: Filter by actor address
            action: Filter by action type
            limit: Maximum number of entries to return
            
        Returns:
            Filtered audit log entries
        """
        filtered = self.audit_log
        
        if actor:
            filtered = [e for e in filtered if e['actor'] == actor]
        
        if action:
            filtered = [e for e in filtered if e['action'] == action]
        
        if limit:
            filtered = filtered[-limit:]
        
        return filtered
    
    def to_dict(self) -> dict:
        """Export permission system to dictionary"""
        return {
            'num_levels': self.num_levels,
            'creator_address': self.creator_address,
            'user_levels': self.user_levels,
            'classifications': {
                level: classification.to_dict()
                for level, classification in self.security_classifications.items()
            },
            'data_count': len(self.data_store),
            'audit_log': self.audit_log
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MultiLevelPermissionSystem':
        """Import permission system from dictionary"""
        system = cls(
            num_levels=data['num_levels'],
            creator_address=data['creator_address']
        )
        
        system.user_levels = data['user_levels']
        system.audit_log = data.get('audit_log', [])
        
        return system