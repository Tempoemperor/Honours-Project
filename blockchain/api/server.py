# blockchain/api/server.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from blockchain.core.blockchain import Blockchain
from blockchain.core.transaction import Transaction, TransactionType, TransactionInput, TransactionOutput
from blockchain.consensus.poa import ProofOfAuthority
from blockchain.crypto.keys import generate_validator_keys, KeyPair

# ── Pydantic Models ────────────────────────────────────────────────────────────

class SetupRequest(BaseModel):
    chain_id: str
    consensus: str          # default: "poa"
    permission_levels: int  # 2–10
    level_names: Optional[list] = None
    max_transactions_per_block: int = 100        
    allow_file_storage: bool = False    

class TransactionRequest(BaseModel):
    sender: str
    recipient: str
    amount: float
    private_key: str

class PermissionRequest(BaseModel):
    sender: str
    target: str
    level: int
    private_key: str

class DataStoreRequest(BaseModel):
    sender: str
    data_id: str
    content: str
    security_level: int
    private_key: str

# ── App + CORS ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Permissioned Blockchain API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config helpers ─────────────────────────────────────────────────────────────

CONFIG_PATH = "data/chain_config.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return None

def save_config(cfg: dict):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def build_consensus(name: str):
    if name == "tendermint":
        from blockchain.consensus.tendermint import TendermintBFT
        return TendermintBFT()
    elif name == "raft":
        from blockchain.consensus.raft import Raft
        return Raft()
    elif name == "pos":
        from blockchain.consensus.pos import ProofOfStake
        return ProofOfStake()
    elif name == "pbft":
        from blockchain.consensus.pbft import PBFT
        return PBFT()
    elif name == "round_robin":
        from blockchain.consensus.round_robin import RoundRobin
        return RoundRobin()
    else:
        return ProofOfAuthority()  # default: poa


def build_blockchain(cfg: dict):
    kp = KeyPair(cfg["admin_private_key"])
    validator = {
        "address": cfg["admin_address"],
        "pub_key": kp.get_public_key_hex(),
        "private_key": cfg["admin_private_key"],
        "power": 10,
        "name": "validator_0",
    }
    consensus = build_consensus(cfg["consensus"])
    consensus.config['authorities'] = [cfg["admin_address"]]
    consensus.authorities = [cfg["admin_address"]]
    chain = Blockchain(
        chain_id=cfg["chain_id"],
        consensus_mechanism=consensus,
        genesis_validators=[validator],
        permission_levels=cfg["permission_levels"],
        creator_address=cfg["admin_address"],
        level_names=cfg.get("level_names"),
    )
    return chain

# ── Startup: load existing config or wait for setup ───────────────────────────

cfg = load_config()

if cfg:
    print(f"Loaded existing admin keys: {cfg['admin_address'][:16]}...")
    blockchain = build_blockchain(cfg)
    admin_key = {"address": cfg["admin_address"], "private_key": cfg["admin_private_key"]}

    # Grant admin permissions
    blockchain.state.grant_permission(admin_key['address'], 'can_transfer')
    blockchain.state.grant_permission(admin_key['address'], 'can_grant_permissions')
    blockchain.state.grant_permission(admin_key['address'], 'can_revoke_permissions')
    blockchain.state.grant_permission(admin_key['address'], 'can_update_validators')
    print(f"Granted admin permissions to {admin_key['address'][:16]}...")

    # Starting balance only on fresh chain
    admin_account = blockchain.state.get_account(admin_key['address'])
    if admin_account.balance == 0:
        admin_account.balance = 10000
        print(f"Granted admin permissions and 10000 balance to {admin_key['address'][:16]}...")

    # Seed demo transactions only on fresh chain
    if blockchain.get_height() == 0:
        demo_txs = [
            {"recipient": "0xDemoUser1aaaaaaaaaaaaaaaaaaaaaaaaaaaa", "amount": 50.0, "nonce": 1},
            {"recipient": "0xDemoUser2bbbbbbbbbbbbbbbbbbbbbbbbbbbb", "amount": 25.0, "nonce": 2},
            {"recipient": "0xDemoUser3cccccccccccccccccccccccccccc", "amount": 75.0, "nonce": 3},
        ]
        for tx_data in demo_txs:
            tx = Transaction(
                tx_type=TransactionType.TRANSFER,
                sender=admin_key['address'],
                inputs=[TransactionInput(from_address=admin_key['address'], amount=tx_data["amount"])],
                outputs=[TransactionOutput(to_address=tx_data["recipient"], amount=tx_data["amount"])],
                nonce=tx_data["nonce"],
            )
            tx.sign(admin_key['private_key'])
            blockchain.pending_transactions.append(tx)
        print(f"Seeded 3 demo transactions into pending pool")
else:
    print("No config found. Waiting for setup via POST /setup/init")
    blockchain = None
    admin_key = None

# ── Guard ──────────────────────────────────────────────────────────────────────

def require_configured():
    if blockchain is None:
        raise HTTPException(status_code=503, detail="Blockchain not configured. POST /setup/init first.")

# ── Setup endpoints ────────────────────────────────────────────────────────────

@app.get("/setup/status")
def setup_status():
    return {"configured": load_config() is not None}

@app.post("/setup/init")
def setup_init(req: SetupRequest):
    global blockchain, admin_key, cfg

    if load_config():
        raise HTTPException(status_code=400, detail="Already configured. Delete data/ to reset.")
    if not req.chain_id.strip():
        raise HTTPException(status_code=400, detail="chain_id cannot be empty")
    if req.consensus not in ("poa", "pos", "pbft", "round_robin", "tendermint", "raft"):
        raise HTTPException(status_code=400, detail="consensus must be: poa, tendermint, or raft")
    if not (2 <= req.permission_levels <= 10):
        raise HTTPException(status_code=400, detail="permission_levels must be between 2 and 10")

    # Generate fresh admin keypair
    new_keys = generate_validator_keys(1)[0]
    admin_address = new_keys['address']
    admin_private_key = new_keys['private_key']


    cfg = {
        "chain_id": req.chain_id.strip(),
        "consensus": req.consensus,
        "permission_levels": req.permission_levels,
        "level_names": req.level_names,
        "max_transactions_per_block": req.max_transactions_per_block,
        "allow_file_storage": req.allow_file_storage, 
        "admin_address": admin_address,
        "admin_private_key": admin_private_key,
        "created_at": time.time(),
    }
    save_config(cfg)

    blockchain = build_blockchain(cfg)
    admin_key = {"address": admin_address, "private_key": admin_private_key}

    blockchain.state.grant_permission(admin_address, 'can_transfer')
    blockchain.state.grant_permission(admin_address, 'can_grant_permissions')
    blockchain.state.grant_permission(admin_address, 'can_revoke_permissions')
    blockchain.state.grant_permission(admin_address, 'can_update_validators')
    blockchain.state.get_account(admin_address).balance = 10000

    print(f"New blockchain '{req.chain_id}' created | consensus={req.consensus} | levels={req.permission_levels}")

    return {
        "status": "created",
        "chain_id": req.chain_id,
        "consensus": req.consensus,
        "permission_levels": req.permission_levels,
        "max_transactions_per_block": req.max_transactions_per_block,
        "allow_file_storage": req.allow_file_storage, 
        "admin_address": admin_address,
        "admin_private_key": admin_private_key,
        "warning": "Save your private key! It will not be shown again."
    }

# ── Existing endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "active", "node_id": blockchain.chain_id if blockchain else "unconfigured"}

@app.get("/admin/info")
def get_admin_info():
    require_configured()
    return {
        "address": admin_key['address'],
        "private_key": admin_key['private_key'],
        "consensus": cfg["consensus"],
        "permission_levels": cfg["permission_levels"],
    }

@app.get("/chain/config")
def get_chain_config():
    config = load_config()
    if not config:
        raise HTTPException(status_code=503, detail="No chain configured")
    # Strip sensitive keys before returning
    return {k: v for k, v in config.items() if k != "admin_private_key"}

@app.get("/chain/info")
def get_chain_info():
    require_configured()
    return blockchain.get_chain_info()

@app.get("/chain/blocks")
def get_blocks(limit: int = 10):
    require_configured()
    return [b.to_dict() for b in blockchain.blocks[-limit:]]

@app.get("/permissions/user/{address}")
def get_user_level(address: str):
    require_configured()
    level = blockchain.get_user_permission_level(address)
    return {"address": address, "level": level}

@app.post("/transaction/transfer")
def send_transfer(tx: TransactionRequest):
    require_configured()
    account = blockchain.state.get_account(tx.sender)
    current_nonce = account.nonce

    new_tx = Transaction(
        tx_type=TransactionType.TRANSFER,
        sender=tx.sender,
        inputs=[TransactionInput(from_address=tx.sender, amount=tx.amount)],
        outputs=[TransactionOutput(to_address=tx.recipient, amount=tx.amount)],
        nonce=current_nonce,
        timestamp=None
    )

    if not tx.private_key:
        raise HTTPException(status_code=400, detail="private_key is required")
    print(f"[SERVER] private_key repr: {repr(tx.private_key[:20])}")

    new_tx.sign(tx.private_key)
    success = blockchain.add_transaction(new_tx)
    if not success:
        raise HTTPException(status_code=400, detail="Transaction rejected (Invalid signature or permissions)")
    return {"status": "submitted", "hash": new_tx.hash()}

@app.post("/permissions/promote")
def promote_user(req: PermissionRequest):
    require_configured()
    from blockchain.core.transaction import PermissionTransaction
    tx = PermissionTransaction(
        sender=req.sender,
        target_address=req.target,
        action="set_level",
        level=req.level
    )
    tx.sign(req.private_key)
    success = blockchain.add_transaction(tx)
    if not success:
        raise HTTPException(status_code=400, detail="Promotion rejected")
    return {"status": "submitted", "hash": tx.hash()}

@app.post("/data/store")
def store_intel(req: DataStoreRequest):
    require_configured()

    # Check file storage flag if content looks like a file (base64 or large payload)
    if not cfg.get("allow_file_storage", False) and len(req.content) > 10_000:
        raise HTTPException(
            status_code=403,
            detail="File storage is disabled for this blockchain. Enable it during setup."
        )

    success = blockchain.store_data(
        data_id=req.data_id,
        content=req.content,
        security_level=req.security_level,
        owner_address=req.sender
    )
    if not success:
        raise HTTPException(status_code=403, detail="Insufficient clearance to store this level of data")
    return {"status": "stored", "id": req.data_id}


@app.get("/data/access/{data_id}")
def read_intel(data_id: str, user_address: str):
    require_configured()
    content = blockchain.access_data(user_address, data_id)
    if content is None:
        raise HTTPException(status_code=403, detail="ACCESS DENIED: Insufficient Security Clearance")
    return {"status": "granted", "content": content}

@app.post("/mine")
def force_mine():
    require_configured()
    max_txs = cfg.get("max_transactions_per_block", 100)

    # Enforce cap — slice pending pool before proposing
    all_pending = blockchain.pending_transactions[:]
    blockchain.pending_transactions = all_pending[:max_txs]

    block = blockchain.propose_block(admin_key['address'], admin_key['private_key'])

    # Restore any transactions that didn't make it into this block
    mined_hashes = {tx.hash() for tx in block.transactions} if block else set()
    blockchain.pending_transactions = [
        tx for tx in all_pending if tx.hash() not in mined_hashes
    ]

    if block:
        success = blockchain.add_block(block)
        if success:
            return {"status": "mined", "block_height": block.height, "tx_count": len(block.transactions)}
    return {"status": "skipped", "reason": "consensus rejected block"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
