# blockchain/permissions/rbac.py

from typing import Dict, List, Set, Optional
from .acl import AccessControlList, Permission


class Role:
    """Role definition with permissions"""
    
    def __init__(self, name: str, permissions: Optional[Set[str]] = None, description: str = ""):
        self.name = name
        self.permissions = permissions or set()
        self.description = description
    
    def add_permission(self, permission: str) -> None:
        """Add permission to role"""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: str) -> None:
        """Remove permission from role"""
        self.permissions.discard(permission)
    
    def has_permission(self, permission: str) -> bool:
        """Check if role has permission"""
        return permission in self.permissions
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'permissions': list(self.permissions),
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Role':
        return cls(
            name=data['name'],
            permissions=set(data.get('permissions', [])),
            description=data.get('description', '')
        )


class RoleBasedAccessControl:
    """
    Role-Based Access Control System
    
    Manages roles and assigns them to addresses
    """
    
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.role_assignments: Dict[str, Set[str]] = {}  # address -> roles
        self.acl = AccessControlList()
        
        # Initialize default roles
        self._initialize_default_roles()
    
    def _initialize_default_roles(self) -> None:
        """Initialize default roles"""
        # Validator role
        validator_role = Role(
            name="validator",
            permissions={
                Permission.CAN_VALIDATE.value,
                Permission.CAN_PROPOSE_BLOCK.value,
                Permission.CAN_SEND_TX.value,
                Permission.CAN_RECEIVE_TX.value,
                Permission.CAN_READ_STATE.value,
                Permission.CAN_READ_BLOCKS.value,
            },
            description="Block validator with proposal rights"
        )
        self.create_role(validator_role)
        
        # User role
        user_role = Role(
            name="user",
            permissions={
                Permission.CAN_SEND_TX.value,
                Permission.CAN_RECEIVE_TX.value,
                Permission.CAN_TRANSFER.value,
                Permission.CAN_READ_STATE.value,
                Permission.CAN_READ_BLOCKS.value,
            },
            description="Regular user with transaction rights"
        )
        self.create_role(user_role)
        
        # Admin role
        admin_role = Role(
            name="admin",
            permissions={
                Permission.CAN_GRANT_PERMISSIONS.value,
                Permission.CAN_REVOKE_PERMISSIONS.value,
                Permission.CAN_UPDATE_VALIDATORS.value,
                Permission.CAN_DEPLOY_CONTRACT.value,
                Permission.ADMIN.value,
            },
            description="Administrator with governance rights"
        )
        self.create_role(admin_role)
        
        # Observer role (read-only)
        observer_role = Role(
            name="observer",
            permissions={
                Permission.CAN_READ_STATE.value,
                Permission.CAN_READ_BLOCKS.value,
            },
            description="Read-only observer"
        )
        self.create_role(observer_role)
    
    def create_role(self, role: Role) -> bool:
        """Create a new role"""
        if role.name in self.roles:
            return False
        
        self.roles[role.name] = role
        return True
    
    def delete_role(self, role_name: str) -> bool:
        """Delete a role"""
        if role_name not in self.roles:
            return False
        
        # Remove role from all assignments
        for address in list(self.role_assignments.keys()):
            self.revoke_role(address, role_name)
        
        del self.roles[role_name]
        return True
    
    def assign_role(self, address: str, role_name: str) -> bool:
        """Assign role to address"""
        if role_name not in self.roles:
            return False
        
        if address not in self.role_assignments:
            self.role_assignments[address] = set()
        
        if role_name in self.role_assignments[address]:
            return False
        
        # Assign role
        self.role_assignments[address].add(role_name)
        
        # Grant permissions from role
        role = self.roles[role_name]
        for permission in role.permissions:
            self.acl.grant_permission(address, permission)
        
        return True
    
    def revoke_role(self, address: str, role_name: str) -> bool:
        """Revoke role from address"""
        if address not in self.role_assignments:
            return False
        
        if role_name not in self.role_assignments[address]:
            return False
        
        # Revoke role
        self.role_assignments[address].remove(role_name)
        
        # Revoke permissions from role
        role = self.roles[role_name]
        for permission in role.permissions:
            # Only revoke if no other assigned roles have this permission
            has_permission_from_other_role = False
            for other_role_name in self.role_assignments[address]:
                other_role = self.roles[other_role_name]
                if permission in other_role.permissions:
                    has_permission_from_other_role = True
                    break
            
            if not has_permission_from_other_role:
                self.acl.revoke_permission(address, permission)
        
        return True
    
    def has_role(self, address: str, role_name: str) -> bool:
        """Check if address has role"""
        if address not in self.role_assignments:
            return False
        return role_name in self.role_assignments[address]
    
    def has_permission(self, address: str, permission: str) -> bool:
        """Check if address has permission (through roles or direct grant)"""
        return self.acl.has_permission(address, permission)
    
    def get_roles(self, address: str) -> Set[str]:
        """Get all roles assigned to address"""
        return self.role_assignments.get(address, set()).copy()
    
    def get_permissions(self, address: str) -> Set[str]:
        """Get all permissions for address"""
        return self.acl.get_permissions(address)
    
    def get_role_permissions(self, role_name: str) -> Set[str]:
        """Get permissions for a role"""
        if role_name not in self.roles:
            return set()
        return self.roles[role_name].permissions.copy()
    
    def add_permission_to_role(self, role_name: str, permission: str) -> bool:
        """Add permission to a role"""
        if role_name not in self.roles:
            return False
        
        self.roles[role_name].add_permission(permission)
        
        # Update all addresses with this role
        for address, roles in self.role_assignments.items():
            if role_name in roles:
                self.acl.grant_permission(address, permission)
        
        return True
    
    def remove_permission_from_role(self, role_name: str, permission: str) -> bool:
        """Remove permission from a role"""
        if role_name not in self.roles:
            return False
        
        self.roles[role_name].remove_permission(permission)
        
        # Update all addresses with this role
        for address, roles in self.role_assignments.items():
            if role_name in roles:
                # Only revoke if no other role has this permission
                has_from_other = False
                for other_role in roles:
                    if other_role != role_name and permission in self.roles[other_role].permissions:
                        has_from_other = True
                        break
                
                if not has_from_other:
                    self.acl.revoke_permission(address, permission)
        
        return True
    
    def get_all_roles(self) -> List[Role]:
        """Get all defined roles"""
        return list(self.roles.values())
    
    def to_dict(self) -> dict:
        """Export RBAC to dictionary"""
        return {
            'roles': {name: role.to_dict() for name, role in self.roles.items()},
            'role_assignments': {
                addr: list(roles) for addr, roles in self.role_assignments.items()
            },
            'acl': self.acl.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RoleBasedAccessControl':
        """Import RBAC from dictionary"""
        rbac = cls()
        rbac.roles.clear()  # Clear default roles
        
        # Import roles
        for role_data in data.get('roles', {}).values():
            role = Role.from_dict(role_data)
            rbac.roles[role.name] = role
        
        # Import ACL
        rbac.acl = AccessControlList.from_dict(data.get('acl', {}))
        
        # Import role assignments
        for address, roles in data.get('role_assignments', {}).items():
            rbac.role_assignments[address] = set(roles)
        
        return rbac