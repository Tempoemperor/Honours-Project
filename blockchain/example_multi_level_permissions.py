# example_multi_level_permissions.py

"""
Example demonstrating the Multi-Level Permission System
"""

from blockchain import (
    Blockchain,
    RoundRobin,
    generate_validator_keys,
    MultiLevelPermissionSystem,
)


def example_multi_level_permissions():
    """Comprehensive example of multi-level permission system"""
    
    print("=" * 70)
    print("Multi-Level Permission System Example")
    print("=" * 70)
    
    # Generate validator keys
    validators = generate_validator_keys(5)
    creator = validators[0]
    
    # Define level names
    level_names = ["Public", "Internal", "Confidential", "Secret", "Top Secret"]
    
    # Create blockchain with 5 permission levels
    consensus = RoundRobin()
    chain = Blockchain(
        chain_id="classified-chain",
        consensus_mechanism=consensus,
        genesis_validators=validators,
        permission_levels=5,
        creator_address=creator['address'],
        level_names=level_names
    )
    
    perm_system = chain.permission_system
    
    print(f"\nBlockchain created with {perm_system.num_levels} permission levels")
    print(f"Creator: {creator['address'][:16]}... (Level {perm_system.max_level})")
    
    # Show security classifications
    print("\nSecurity Classifications:")
    for level in range(1, perm_system.num_levels + 1):
        classification = perm_system.get_classification_info(level)
        print(f"  Level {level}: {classification.name}")
    
    # New users default to level 1
    user1 = validators[1]['address']
    user2 = validators[2]['address']
    user3 = validators[3]['address']
    user4 = validators[4]['address']
    
    print(f"\nInitial user levels:")
    print(f"  User1: Level {perm_system.get_user_level(user1)}")
    print(f"  User2: Level {perm_system.get_user_level(user2)}")
    print(f"  User3: Level {perm_system.get_user_level(user3)}")
    print(f"  User4: Level {perm_system.get_user_level(user4)}")
    
    # Creator promotes users
    print("\n--- Creator Promotions ---")
    
    # Promote user1 to level 3
    success = perm_system.promote_user(creator['address'], user1, 3)
    print(f"Creator promotes User1 to level 3: {success}")
    print(f"  User1 now at: Level {perm_system.get_user_level(user1)}")
    
    # Promote user2 to level 2
    success = perm_system.promote_user(creator['address'], user2, 2)
    print(f"Creator promotes User2 to level 2: {success}")
    print(f"  User2 now at: Level {perm_system.get_user_level(user2)}")
    
    # User1 (level 3) tries to promote user3
    print("\n--- User1 (Level 3) Promotions ---")
    
    # User1 can promote user3 to level 2 (below their own level)
    success = perm_system.promote_user(user1, user3, 2)
    print(f"User1 promotes User3 to level 2: {success}")
    print(f"  User3 now at: Level {perm_system.get_user_level(user3)}")
    
    # User1 can promote user3 to level 3 (their own level)
    success = perm_system.promote_user(user1, user3, 3)
    print(f"User1 promotes User3 to level 3: {success}")
    print(f"  User3 now at: Level {perm_system.get_user_level(user3)}")
    
    # User1 CANNOT promote user4 to level 4 (above their own level)
    success = perm_system.promote_user(user1, user4, 4)
    print(f"User1 tries to promote User4 to level 4: {success} (DENIED - above User1's level)")
    
    # Store data at different security levels
    print("\n--- Storing Classified Data ---")
    
    # Creator stores top secret data (level 5)
    perm_system.store_data(
        data_id="nuclear_codes",
        content="Launch codes: Alpha-Bravo-Charlie-123",
        security_level=5,
        owner_address=creator['address'],
        metadata={'type': 'military', 'expires': '2030-01-01'}
    )
    print("Creator stored: 'nuclear_codes' (Level 5 - Top Secret)")
    
    # User1 (level 3) stores confidential data
    perm_system.store_data(
        data_id="project_plans",
        content="Project X development roadmap",
        security_level=3,
        owner_address=user1,
        metadata={'type': 'business', 'department': 'R&D'}
    )
    print("User1 stored: 'project_plans' (Level 3 - Confidential)")
    
    # User2 (level 2) stores internal data
    perm_system.store_data(
        data_id="meeting_notes",
        content="Q4 meeting notes and action items",
        security_level=2,
        owner_address=user2,
        metadata={'type': 'administrative'}
    )
    print("User2 stored: 'meeting_notes' (Level 2 - Internal)")
    
    # User3 (level 3) stores public data
    perm_system.store_data(
        data_id="company_blog",
        content="Welcome to our company blog!",
        security_level=1,
        owner_address=user3,
        metadata={'type': 'public'}
    )
    print("User3 stored: 'company_blog' (Level 1 - Public)")
    
    # Test data access
    print("\n--- Testing Data Access ---")
    
    # User4 (level 1) can only access public data
    print(f"\nUser4 (Level {perm_system.get_user_level(user4)}) access attempts:")
    
    data = perm_system.access_data(user4, "company_blog")
    print(f"  Access 'company_blog' (Level 1): {'SUCCESS' if data else 'DENIED'}")
    
    data = perm_system.access_data(user4, "meeting_notes")
    print(f"  Access 'meeting_notes' (Level 2): {'SUCCESS' if data else 'DENIED'}")
    
    data = perm_system.access_data(user4, "nuclear_codes")
    print(f"  Access 'nuclear_codes' (Level 5): {'SUCCESS' if data else 'DENIED'}")
    
    # User2 (level 2) can access level 1-2 data
    print(f"\nUser2 (Level {perm_system.get_user_level(user2)}) access attempts:")
    
    data = perm_system.access_data(user2, "company_blog")
    print(f"  Access 'company_blog' (Level 1): {'SUCCESS' if data else 'DENIED'}")
    
    data = perm_system.access_data(user2, "meeting_notes")
    print(f"  Access 'meeting_notes' (Level 2): {'SUCCESS' if data else 'DENIED'}")
    
    data = perm_system.access_data(user2, "project_plans")
    print(f"  Access 'project_plans' (Level 3): {'SUCCESS' if data else 'DENIED'}")
    
    # User1 (level 3) can access level 1-3 data
    print(f"\nUser1 (Level {perm_system.get_user_level(user1)}) access attempts:")
    
    data = perm_system.access_data(user1, "meeting_notes")
    print(f"  Access 'meeting_notes' (Level 2): {'SUCCESS' if data else 'DENIED'}")
    
    data = perm_system.access_data(user1, "project_plans")
    print(f"  Access 'project_plans' (Level 3): {'SUCCESS' if data else 'DENIED'}")
    
    data = perm_system.access_data(user1, "nuclear_codes")
    print(f"  Access 'nuclear_codes' (Level 5): {'SUCCESS' if data else 'DENIED'}")
    
    # Creator can access everything
    print(f"\nCreator (Level {perm_system.get_user_level(creator['address'])}) access attempts:")
    
    data = perm_system.access_data(creator['address'], "nuclear_codes")
    print(f"  Access 'nuclear_codes' (Level 5): {'SUCCESS' if data else 'DENIED'}")
    if data:
        print(f"  Content: {data}")
    
    # Get accessible data for each user
    print("\n--- Accessible Data Count ---")
    
    for i, user in enumerate([user4, user2, user1, creator['address']], 1):
        accessible = perm_system.get_accessible_data(user)
        level = perm_system.get_user_level(user)
        print(f"User at Level {level}: Can access {len(accessible)} data items")
    
    # Show level statistics
    print("\n--- User Distribution by Level ---")
    stats = perm_system.get_level_statistics()
    for level, count in stats.items():
        classification = perm_system.get_classification_info(level)
        print(f"Level {level} ({classification.name}): {count} users")
    
    # Show audit log
    print("\n--- Recent Audit Log (last 10 entries) ---")
    recent_logs = perm_system.get_audit_log(limit=10)
    for log in recent_logs[-5:]:  # Show last 5
        action = log['action']
        actor = log['actor'][:16] + "..."
        print(f"  {action} by {actor}")
    
    print("\n" + "=" * 70)
    print("Multi-Level Permission System Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    example_multi_level_permissions()