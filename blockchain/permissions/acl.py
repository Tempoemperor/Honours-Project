# blockchain/permissions/acl.py

from typing import Dict, List, Set, Optional
from enum import Enum


class Permission(Enum):
    """Standard blockchain permissions"""
    
    # Transaction permissions
    CAN_SEND_TX = "can_send_tx"
    CAN_RECEIVE_TX = "can_receive_tx"
    CAN_TRANSFER = "can_transfer"
    
    # Validator permissions
    CAN_VALIDATE = "can_validate"
    CAN_PROPOSE_BLOCK = "can_propose_block"
    
    # Governance permissions
    CAN_UPDATE_VALIDATORS = "can_update_validators"
    CAN_GRANT_PERMISSIONS = "can_grant_permissions"
    CAN_REVOKE_PERMISSIONS = "can_revoke_permissions"
    CAN_UPDATE_CONSENSUS = "can_update_consensus"
    
    # Smart contract permissions
    CAN_DEPLOY_CONTRACT = "can_deploy_contract"
    CAN_CALL_CONTRACT = "can_call_contract"
    
    # Admin permissions
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    
    # Read permissions
    CAN_READ_STATE = "can_read_state"
    CAN_READ_BLOCKS = "can_read_blocks"


class AccessControlList:
    """
    Access Control List for permissioned blockchain
    
    Manages permissions for addresses
    """
    
    def __init__(self):
        # address -> set of permissions
        self.permissions: Dict[str, Set[str]] = {}
        
        # permission -> set of addresses
        self.reverse_index: Dict[str, Set[str]] = {}
        
        # Track permission grants/revocations
        self.audit_log: List[Dict] = []
    
    def grant_permission(
        self,
        address: str,
        permission: str,
        granted_by: Optional[str] = None
    ) -> bool:
        """
        Grant permission to an address
        
        Args:
            address: Address to grant permission to
            permission: Permission to grant
            granted_by: Address that granted the permission
            
        Returns:
            True if permission was granted, False if already had it
        """
        if address not in self.permissions:
            self.permissions[address] = set()
        
        if permission in self.permissions[address]:
            return False
        
        # Grant permission
        self.permissions[address].add(permission)
        
        # Update reverse index
        if permission not in self.reverse_index:
            self.reverse_index[permission] = set()
        self.reverse_index[permission].add(address)
        
        # Audit log
        self.audit_log.append({
            'action': 'grant',
            'address': address,
            'permission': permission,
            'granted_by': granted_by,
            'timestamp': __import__('time').time()
        })
        
        return True
    
    def revoke_permission(
        self,
        address: str,
        permission: str,
        revoked_by: Optional[str] = None
    ) -> bool:
        """
        Revoke permission from an address
        
        Args:
            address: Address to revoke permission from
            permission: Permission to revoke
            revoked_by: Address that revoked the permission
            
        Returns:
            True if permission was revoked, False if didn't have it
        """
        if address not in self.permissions:
            return False
        
        if permission not in self.permissions[address]:
            return False
        
        # Revoke permission
        self.permissions[address].remove(permission)
        
        # Update reverse index
        if permission in self.reverse_index:
            self.reverse_index[permission].discard(address)
        
        # Audit log
        self.audit_log.append({
            'action': 'revoke',
            'address': address,
            'permission': permission,
            'revoked_by': revoked_by,
            'timestamp': __import__('time').time()
        })
        
        return True
    
    def has_permission(self, address: str, permission: str) -> bool:
        """
        Check if address has permission
        
        Args:
            address: Address to check
            permission: Permission to check for
            
        Returns:
            True if address has permission, False otherwise
        """
        if address not in self.permissions:
            return False
        
        # Check for specific permission
        if permission in self.permissions[address]:
            return True
        
        # Check for admin permissions
        if Permission.SUPER_ADMIN.value in self.permissions[address]:
            return True
        
        if Permission.ADMIN.value in self.permissions[address]:
            # Admin has most permissions except super admin actions
            if permission != Permission.SUPER_ADMIN.value:
                return True
        
        return False
    
    def get_permissions(self, address: str) -> Set[str]:
        """Get all permissions for an address"""
        return self.permissions.get(address, set()).copy()
    
    def get_addresses_with_permission(self, permission: str) -> Set[str]:
        """Get all addresses with a specific permission"""
        return self.reverse_index.get(permission, set()).copy()
    
    def revoke_all_permissions(self, address: str, revoked_by: Optional[str] = None) -> int:
        """
        Revoke all permissions from an address
        
        Returns:
            Number of permissions revoked
        """
        if address not in self.permissions:
            return 0
        
        permissions_to_revoke = list(self.permissions[address])
        count = 0
        
        for permission in permissions_to_revoke:
            if self.revoke_permission(address, permission, revoked_by):
                count += 1
        
        return count
    
    def grant_admin(self, address: str, granted_by: Optional[str] = None) -> bool:
        """Grant admin permissions to an address"""
        return self.grant_permission(address, Permission.ADMIN.value, granted_by)
    
    def grant_super_admin(self, address: str, granted_by: Optional[str] = None) -> bool:
        """Grant super admin permissions to an address"""
        return self.grant_permission(address, Permission.SUPER_ADMIN.value, granted_by)
    
    def is_admin(self, address: str) -> bool:
        """Check if address is an admin"""
        return self.has_permission(address, Permission.ADMIN.value)
    
    def is_super_admin(self, address: str) -> bool:
        """Check if address is a super admin"""
        return self.has_permission(address, Permission.SUPER_ADMIN.value)
    
    def get_audit_log(
        self,
        address: Optional[str] = None,
        permission: Optional[str] = None,
        action: Optional[str] = None
    ) -> List[Dict]:
        """
        Get audit log with optional filters
        
        Args:
            address: Filter by address
            permission: Filter by permission
            action: Filter by action ('grant' or 'revoke')
            
        Returns:
            Filtered audit log entries
        """
        filtered_log = self.audit_log
        
        if address:
            filtered_log = [e for e in filtered_log if e['address'] == address]
        
        if permission:
            filtered_log = [e for e in filtered_log if e['permission'] == permission]
        
        if action:
            filtered_log = [e for e in filtered_log if e['action'] == action]
        
        return filtered_log
    
    def to_dict(self) -> dict:
        """Export ACL to dictionary"""
        return {
            'permissions': {
                addr: list(perms) for addr, perms in self.permissions.items()
            },
            'audit_log': self.audit_log
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AccessControlList':
        """Import ACL from dictionary"""
        acl = cls()
        
        for address, permissions in data.get('permissions', {}).items():
            for permission in permissions:
                acl.grant_permission(address, permission)
        
        acl.audit_log = data.get('audit_log', [])
        
        return acl