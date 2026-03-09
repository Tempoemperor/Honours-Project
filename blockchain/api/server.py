# blockchain/api/server.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from blockchain.core.blockchain import Blockchain
from blockchain.core.transaction import Transaction, TransactionType, TransactionInput, TransactionOutput
from blockchain.consensus.poa import ProofOfAuthority
from blockchain.crypto.keys import generate_validator_keys

# --- Pydantic Models ---
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

# --- App Setup ---
app = FastAPI(title="Permissioned Blockchain API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Persist Admin Keys ---
KEYS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'data', 'admin_keys.json'
)

def load_or_create_admin_keys():
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            keys = json.load(f)
            print(f"Loaded existing admin keys: {keys['address'][:16]}...")
            return [keys]
    else:
        new_validators = generate_validator_keys(1)
        with open(KEYS_FILE, 'w') as f:
            json.dump(new_validators[0], f, indent=2)
        print(f"Generated new admin keys: {new_validators[0]['address'][:16]}...")
        return new_validators

# --- Initialize (order matters!) ---
validators = load_or_create_admin_keys()
admin_key = validators[0]

consensus = ProofOfAuthority(config={
    'authorities': [admin_key['address']]
})

blockchain = Blockchain(
    chain_id="api-node-01",
    consensus_mechanism=consensus,
    genesis_validators=validators,
    permission_levels=5,
    creator_address=admin_key['address'],
    level_names=["Unclassified", "Restricted", "Confidential", "Secret", "Top Secret"]
)

# --- Seed Demo Transactions ---
def seed_demo_transactions():
    from blockchain.core.transaction import TransferTransaction
    demo_txs = [
        {"sender": admin_key['address'], "recipient": "0xDemoUser1aaaaaaaaaaaaaaaaaaaaaaaaaaaa", "amount": 50.0, "nonce": 1},
        {"sender": admin_key['address'], "recipient": "0xDemoUser2bbbbbbbbbbbbbbbbbbbbbbbbbbbb", "amount": 25.0, "nonce": 2},
        {"sender": admin_key['address'], "recipient": "0xDemoUser3cccccccccccccccccccccccccccc", "amount": 75.0, "nonce": 3},
    ]
    for tx_data in demo_txs:
        tx = TransferTransaction(
            sender=tx_data['sender'],
            recipient=tx_data['recipient'],
            amount=tx_data['amount'],
            nonce=tx_data['nonce'],
        )
        tx.sign(admin_key['private_key'])
        blockchain.pending_transactions.append(tx)
    print(f"Seeded {len(demo_txs)} demo transactions into pending pool")

if blockchain.get_height() == 0:
    seed_demo_transactions()

# Grant admin all permissions needed for demo
from blockchain.core.state import AccountState
admin_account = blockchain.state.get_account(admin_key['address'])
blockchain.state.grant_permission(admin_key['address'], 'can_transfer')
blockchain.state.grant_permission(admin_key['address'], 'can_grant_permissions')
blockchain.state.grant_permission(admin_key['address'], 'can_revoke_permissions')
blockchain.state.grant_permission(admin_key['address'], 'can_update_validators')
print(f"Granted admin permissions to {admin_key['address'][:16]}...")

# Give admin starting balance for demo transactions
admin_account = blockchain.state.get_account(admin_key['address'])
admin_account.balance = 10000.0
print(f"Granted admin permissions and 10000 balance to {admin_key['address'][:16]}...")


# --- Routes ---
@app.get("/")
def read_root():
    return {"status": "active", "node_id": blockchain.chain_id}

@app.get("/admin/info")
def get_admin_info():
    """Return admin address and private key for demo purposes"""
    return {
        "address": admin_key['address'],
        "private_key": admin_key['private_key']
    }

@app.get("/chain/info")
def get_chain_info():
    return blockchain.get_chain_info()

@app.get("/chain/blocks")
def get_blocks(limit: int = 10):
    return [b.to_dict() for b in blockchain.blocks[-limit:]]

@app.get("/permissions/user/{address}")
def get_user_level(address: str):
    level = blockchain.get_user_permission_level(address)
    return {"address": address, "level": level}

@app.post("/transaction/transfer")
def send_transfer(tx: TransactionRequest):
    account = blockchain.state.get_account(tx.sender)
    current_nonce = account.nonce

    new_tx = Transaction(
        tx_type=TransactionType.TRANSFER,
        sender=tx.sender,
        inputs=[TransactionInput(from_address=tx.sender, amount=tx.amount)],
        outputs=[TransactionOutput(to_address=tx.recipient, amount=tx.amount)],
        nonce=current_nonce,   # ← ADD THIS
        timestamp=None
    )

    if not tx.private_key:
        raise HTTPException(status_code=400, detail=f"private_key missing or empty: {repr(tx.private_key)}")
    print(f"[SERVER] private_key repr: {repr(tx.private_key[:20])}")

    new_tx.sign(tx.private_key)
    success = blockchain.add_transaction(new_tx)
    if not success:
        raise HTTPException(status_code=400, detail="Transaction rejected (Invalid signature or permissions)")
    return {"status": "submitted", "hash": new_tx.hash()}


@app.post("/permissions/promote")
def promote_user(req: PermissionRequest):
    account = blockchain.state.get_account(req.sender)  # ← fix: req.sender not tx.sender
    current_nonce = account.nonce

    from blockchain.core.transaction import PermissionTransaction
    tx = PermissionTransaction(
        sender=req.sender,
        target_address=req.target,
        action="set_level",
        level=req.level,
        nonce=current_nonce   # ← ADD THIS
    )
    tx.sign(req.private_key)
    success = blockchain.add_transaction(tx)
    if not success:
        raise HTTPException(status_code=400, detail="Promotion rejected")
    return {"status": "submitted", "hash": tx.hash(), "message": f"Promoting {req.target} to Level {req.level}"}


@app.post("/data/store")
def store_intel(req: DataStoreRequest):
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
    content = blockchain.access_data(user_address, data_id)
    if content is None:
        raise HTTPException(status_code=403, detail="ACCESS DENIED: Insufficient Security Clearance")
    return {"status": "granted", "content": content}

@app.post("/mine")
def force_mine():
    block = blockchain.propose_block(admin_key['address'], admin_key['private_key'])
    if block:
        success = blockchain.add_block(block)
        if success:
            return {
                "status": "mined",
                "block_height": block.height,
                "tx_count": len(block.transactions)
            }
    return {"status": "skipped", "reason": "consensus rejected block"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
