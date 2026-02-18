# blockchain/api/server.py

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware  # <--- NEW IMPORT
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import sys
import os

# Add parent directory to path so we can import blockchain packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from blockchain.core.blockchain import Blockchain
from blockchain.core.transaction import Transaction, TransactionType, TransactionInput, TransactionOutput
from blockchain.consensus.poa import ProofOfAuthority
from blockchain.crypto.keys import generate_validator_keys

# --- Pydantic Models for API Requests ---
class TransactionRequest(BaseModel):
    sender: str
    recipient: str
    amount: float
    private_key: str  # In real world, we'd send a signed hex, but for demo we sign here

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

# --- NEW: Enable CORS for React Frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow React app
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],
)

# Global Blockchain Instance (The "Node")
# We initialize it with PoA and 1 Validator for the API demo
validators = generate_validator_keys(1)
admin_key = validators[0]
consensus = ProofOfAuthority(config={
    'authorities': [admin_key['address']]
})

# Initialize Chain
blockchain = Blockchain(
    chain_id="api-node-01",
    consensus_mechanism=consensus,
    genesis_validators=validators,
    permission_levels=5,
    creator_address=admin_key['address'],
    level_names=["Unclassified", "Restricted", "Confidential", "Secret", "Top Secret"]
)

@app.get("/")
def read_root():
    return {"status": "active", "node_id": blockchain.chain_id}

@app.get("/chain/info")
def get_chain_info():
    """Get current status of the blockchain"""
    return blockchain.get_chain_info()

@app.get("/chain/blocks")
def get_blocks(limit: int = 10):
    """Get recent blocks"""
    blocks = [b.to_dict() for b in blockchain.blocks[-limit:]]
    return blocks

@app.get("/permissions/user/{address}")
def get_user_level(address: str):
    """Check a user's security clearance"""
    level = blockchain.get_user_permission_level(address)
    return {"address": address, "level": level}

@app.post("/transaction/transfer")
def send_transfer(tx: TransactionRequest):
    """Submit a financial transfer"""
    # Create and sign transaction
    # NOTE: In production, the client signs. Here we do it for the demo.
    new_tx = Transaction(
        tx_type=TransactionType.TRANSFER,
        sender=tx.sender,
        inputs=[TransactionInput(from_address=tx.sender, amount=tx.amount)],
        outputs=[TransactionOutput(to_address=tx.recipient, amount=tx.amount)],
        timestamp=None
    )
    new_tx.sign(tx.private_key)
    
    success = blockchain.add_transaction(new_tx)
    if not success:
        raise HTTPException(status_code=400, detail="Transaction rejected (Invalid signature or permissions)")
    
    return {"status": "submitted", "hash": new_tx.hash()}

@app.post("/permissions/promote")
def promote_user(req: PermissionRequest):
    """Submit a promotion transaction"""
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
    
    return {"status": "submitted", "hash": tx.hash(), "message": f"Promoting {req.target} to Level {req.level}"}

@app.post("/data/store")
def store_intel(req: DataStoreRequest):
    """Store classified data (Demo shortcut: direct store, ideally via TX)"""
    # For the API demo, we wrap the store_data logic
    # Verify sender signature would go here
    
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
    """Attempt to access classified data"""
    content = blockchain.access_data(user_address, data_id)
    if content is None:
        raise HTTPException(status_code=403, detail="ACCESS DENIED: Insufficient Security Clearance")
    
    return {"status": "granted", "content": content}

@app.post("/mine")
def force_mine():
    """Trigger the node to mine a block (for demo purposes)"""
    # In reality, this happens automatically on a timer
    block = blockchain.propose_block(admin_key['address'], admin_key['private_key'])
    if block:
        blockchain.add_block(block)
        return {"status": "mined", "block_height": block.height, "tx_count": len(block.transactions)}
    return {"status": "skipped", "reason": "no transactions or invalid state"}

# To run: uvicorn blockchain.api.server:app --reload
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)