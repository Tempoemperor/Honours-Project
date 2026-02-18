# test_full_scenario.py

import time
from blockchain import (
    Blockchain,
    RoundRobin,
    generate_validator_keys,
    TransactionType,
    PermissionTransaction,
    Transaction,
    TransactionInput,
    TransactionOutput
)

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def print_header(msg):
    print(f"\n{'='*60}")
    print(f" {msg}")
    print(f"{'='*60}")

def mine_block(chain, miner_info):
    """
    Simulates the consensus process:
    1. Validator proposes block
    2. Chain accepts block
    3. Transactions execute
    """
    print(f"\n[Mining] {miner_info['name']} is mining a block...")
    
    # 1. Propose
    block = chain.propose_block(
        validator_address=miner_info['address'], 
        private_key=miner_info['private_key']
    )
    
    # 2. Add/Validate
    if block:
        success = chain.add_block(block)
        if success:
            print(f"   -> Block #{block.height} added! ({len(block.transactions)} txs)")
        else:
            print("   -> Block rejected.")
    else:
        print("   -> No block produced (maybe no transactions?)")

def send_promotion_tx(chain, sender, target_addr, new_level):
    """Creates and sends a Permission Transaction to change levels"""
    tx = PermissionTransaction(
        sender=sender['address'],
        target_address=target_addr,
        action="set_level",
        level=new_level,
        nonce=int(time.time()) # Simple nonce for testing
    )
    tx.sign(sender['private_key'])
    
    if chain.add_transaction(tx):
        print(f"   [Tx Submitted] {sender['name']} promotes Target to Lvl {new_level}")
    else:
        print(f"   [Tx Rejected] {sender['name']} failed to submit promotion tx")

def send_data_tx(chain, sender, data_id, content, level):
    """
    In a real app, storing data would be a transaction type.
    Since your current code has 'store_data' as a direct method, 
    we will use that for storage, but wrap it in a visual log to simulate a TX.
    """
    # NOTE: To make this purely blockchain-based, you'd add a DATA_STORE tx type.
    # For now, we simulate the 'write' happening after mining.
    print(f"   [Data Tx] {sender['name']} storing '{data_id}' (Security Lvl {level})")
    chain.store_data(
        data_id=data_id, 
        content=content, 
        security_level=level, 
        owner_address=sender['address']
    )

# ==========================================
# MAIN TEST SCRIPT
# ==========================================

def run_full_test():
    print_header("INITIALIZING MILITARY BLOCKCHAIN SIMULATION")

    # 1. GENERATE ACTORS
    # -------------------------------------------------
    keys = generate_validator_keys(5)
    
    # Assign Roles
    general = keys[0]   # The Creator (Level 5)
    general['name'] = "General (L5)"
    
    colonel = keys[1]   # Will be promoted to Level 4
    colonel['name'] = "Colonel (L4)"
    
    major   = keys[2]   # Will be promoted to Level 3
    major['name']   = "Major (L3)"
    
    private = keys[3]   # Will stay Level 1
    private['name'] = "Private (L1)"
    
    hacker  = keys[4]   # Level 1, tries to break in
    hacker['name']  = "Hacker (L1)"

    # 2. CREATE CHAIN
    # -------------------------------------------------
    level_names = ["Unclassified", "Restricted", "Confidential", "Secret", "Top Secret"]
    
    chain = Blockchain(
        chain_id="mil-net-alpha",
        consensus_mechanism=RoundRobin(),
        genesis_validators=[general], # Only General is a validator initially
        permission_levels=5,
        creator_address=general['address'],
        level_names=level_names
    )

    print(f"Chain Created with 5 Security Levels: {level_names}")
    print(f"Creator: {general['name']}")

    # -------------------------------------------------
    # PHASE 1: PROMOTIONS (Hierarchy Setup)
    # -------------------------------------------------
    print_header("PHASE 1: ESTABLISHING HIERARCHY")
    
    # General promotes Colonel to Lvl 4
    send_promotion_tx(chain, general, colonel['address'], 4)
    
    # General promotes Major to Lvl 3
    send_promotion_tx(chain, general, major['address'], 3)
    
    # Mine these promotions
    mine_block(chain, general)
    
    # Verify Levels
    print("\n[Status Report]")
    print(f"   {colonel['name']} Level: {chain.permission_system.get_user_level(colonel['address'])}")
    print(f"   {major['name']}   Level: {chain.permission_system.get_user_level(major['address'])}")
    print(f"   {private['name']} Level: {chain.permission_system.get_user_level(private['address'])} (Default)")

    # -------------------------------------------------
    # PHASE 2: UNAUTHORIZED ACTIONS (Security Test)
    # -------------------------------------------------
    print_header("PHASE 2: UNAUTHORIZED PROMOTION ATTEMPTS")

    # TEST A: Major (L3) tries to promote Private to Lvl 5 (Higher than self)
    # Expected: FAIL
    print("Test A: Major (L3) tries to promote Private to Lvl 5...")
    send_promotion_tx(chain, major, private['address'], 5)
    
    # TEST B: Hacker (L1) tries to promote self to Lvl 5
    # Expected: FAIL
    print("Test B: Hacker (L1) tries to promote Self to Lvl 5...")
    send_promotion_tx(chain, hacker, hacker['address'], 5)

    # Mine (General processes the bad requests)
    mine_block(chain, general)

    # Verify Logic
    pvt_level = chain.permission_system.get_user_level(private['address'])
    hacker_level = chain.permission_system.get_user_level(hacker['address'])
    
    if pvt_level == 1 and hacker_level == 1:
        print("\n[SUCCESS] Security System blocked unauthorized promotions.")
    else:
        print(f"\n[FAILURE] Private is L{pvt_level}, Hacker is L{hacker_level}")

    # -------------------------------------------------
    # PHASE 3: DATA STORAGE (Classified Intel)
    # -------------------------------------------------
    print_header("PHASE 3: STORING CLASSIFIED INTEL")
    
    # General stores Top Secret (L5)
    send_data_tx(chain, general, "nuke_codes", "LAUNCH-CODE-999", 5)
    
    # Colonel stores Secret (L4)
    send_data_tx(chain, colonel, "spy_list", "Agent 007, Agent 006", 4)
    
    # Major stores Confidential (L3)
    send_data_tx(chain, major, "troop_movements", "Moving to Sector 7", 3)
    
    # Private stores Unclassified (L1)
    send_data_tx(chain, private, "lunch_menu", "Pizza Day", 1)

    # -------------------------------------------------
    # PHASE 4: ACCESS CONTROL (Read Tests)
    # -------------------------------------------------
    print_header("PHASE 4: ACCESS CONTROL TESTS")

    scenarios = [
        # (Actor, DataID, Expected Result)
        (general, "nuke_codes", True),   # L5 reads L5 -> OK
        (colonel, "nuke_codes", False),  # L4 reads L5 -> DENIED
        (major,   "spy_list",   False),  # L3 reads L4 -> DENIED
        (major,   "lunch_menu", True),   # L3 reads L1 -> OK
        (hacker,  "spy_list",   False),  # L1 reads L4 -> DENIED
    ]

    for actor, data_id, expected in scenarios:
        data = chain.access_data(actor['address'], data_id)
        result = bool(data)
        status = "GRANTED" if result else "DENIED"
        color = "\033[92m" if result == expected else "\033[91m" # Green/Red output codes
        reset = "\033[0m"
        
        print(f"   {actor['name']} accessing '{data_id}' -> {color}{status}{reset}", end="")
        
        if result == expected:
            print(f" (Correct)")
        else:
            print(f" (ERROR: Expected {expected})")

    # -------------------------------------------------
    # FINAL AUDIT
    # -------------------------------------------------
    print_header("FINAL SYSTEM AUDIT")
    print("Audit Log (Last 5 Actions):")
    logs = chain.permission_system.get_audit_log(limit=5)
    for log in logs:
        print(f"   [{log['action'].upper()}] Actor: {log['actor'][:8]}... Details: {log['details']}")

    print("\nTEST COMPLETE.")

if __name__ == "__main__":
    run_full_test()