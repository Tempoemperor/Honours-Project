# blockchain/api/server.py

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional, List
import sys, os, json, time, uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from blockchain.core.blockchain import Blockchain
from blockchain.core.transaction import Transaction, TransactionType, TransactionInput, TransactionOutput
from blockchain.consensus.poa import ProofOfAuthority
from blockchain.crypto.keys import generate_validator_keys, KeyPair
from blockchain.api.auth import (
    register_user, login_user, logout_user, delete_user,
    get_current_user, load_user, list_users
)


# ── Pydantic Models ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class SetupRequest(BaseModel):
    chain_id: str
    consensus: str
    permission_levels: int
    level_names: Optional[list] = None
    max_transactions_per_block: int = 100
    allow_file_storage: bool = False
    open_membership: bool = True

class SwitchChainRequest(BaseModel):
    chain_id: str

class JoinChainRequest(BaseModel):
    chain_id: str

class InviteRequest(BaseModel):
    target_address: str
    permission_level: int = 0

class TransactionRequest(BaseModel):
    recipient: str
    amount: float

class PermissionRequest(BaseModel):
    target: str
    level: int

class DataStoreRequest(BaseModel):
    data_id: str
    content: str
    security_level: int = 1   # ← was 0

    @field_validator('security_level')
    @classmethod
    def security_level_non_negative(cls, v):
        if v < 1:
            raise ValueError('security_level must be at least 1')
        return v


# ── Path helpers ───────────────────────────────────────────────────────────────

DATA_ROOT  = "data"
CHAINS_DIR = os.path.join(DATA_ROOT, "chains")
ACTIVE_DIR = os.path.join(DATA_ROOT, "active")

def chain_dir(chain_id: str) -> str:
    return os.path.join(CHAINS_DIR, chain_id)

def chain_config_path(chain_id: str) -> str:
    return os.path.join(chain_dir(chain_id), "chain_config.json")

def members_path(chain_id: str) -> str:
    return os.path.join(chain_dir(chain_id), "members.json")

def active_chain_path(username: str) -> str:
    return os.path.join(ACTIVE_DIR, f"{username}.txt")


# ── Chain config helpers ───────────────────────────────────────────────────────

def list_all_chains() -> List[str]:
    if not os.path.exists(CHAINS_DIR):
        return []
    return [d for d in os.listdir(CHAINS_DIR)
            if os.path.isfile(chain_config_path(d))]

def load_chain_config(chain_id: str) -> Optional[dict]:
    path = chain_config_path(chain_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def save_chain_config(chain_id: str, cfg: dict):
    os.makedirs(chain_dir(chain_id), exist_ok=True)
    with open(chain_config_path(chain_id), "w") as f:
        json.dump(cfg, f, indent=2)


# ── Membership helpers ─────────────────────────────────────────────────────────

def load_members(chain_id: str) -> dict:
    path = members_path(chain_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_members(chain_id: str, members: dict):
    with open(members_path(chain_id), "w") as f:
        json.dump(members, f, indent=2)

def add_member(chain_id: str, address: str, level: int):
    members = load_members(chain_id)
    members[address] = level
    save_members(chain_id, members)

def is_member(chain_id: str, address: str) -> bool:
    return address in load_members(chain_id)

def get_user_chains(address: str) -> List[str]:
    return [cid for cid in list_all_chains() if is_member(cid, address)]


# ── Active chain per user ──────────────────────────────────────────────────────

def get_active_chain(username: str) -> Optional[str]:
    path = active_chain_path(username)
    if os.path.exists(path):
        with open(path) as f:
            cid = f.read().strip()
        if cid in list_all_chains():
            return cid
    profile = load_user(username)
    chains = get_user_chains(profile["address"]) if profile else []
    return chains[0] if chains else None

def set_active_chain(username: str, chain_id: str):
    os.makedirs(ACTIVE_DIR, exist_ok=True)
    with open(active_chain_path(username), "w") as f:
        f.write(chain_id)


# ── Blockchain cache ───────────────────────────────────────────────────────────

_chain_cache: dict = {}

def _find_user_by_address(address: str) -> Optional[dict]:
    for username in list_users():
        profile = load_user(username)
        if profile and profile.get("address") == address:
            return profile
    return None

def _build_consensus(name: str):
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
        return ProofOfAuthority()

def _build_blockchain(cfg: dict) -> Blockchain:
    admin_address = cfg["admin_address"]
    admin_profile = _find_user_by_address(admin_address)
    if admin_profile:
        private_key = admin_profile["private_key"]
        pub_key     = KeyPair(private_key).get_public_key_hex()
    else:
        keys        = generate_validator_keys(1)[0]
        private_key = keys["private_key"]
        pub_key     = keys["pub_key"]

    validator = {
        "address":     admin_address,
        "pub_key":     pub_key,
        "private_key": private_key,
        "power":       10,
        "name":        "validator_0",
    }
    consensus = _build_consensus(cfg["consensus"])
    consensus.config['authorities'] = [admin_address]
    consensus.authorities           = [admin_address]

    return Blockchain(
        chain_id=cfg["chain_id"],
        consensus_mechanism=consensus,
        genesis_validators=[validator],
        permission_levels=cfg["permission_levels"],
        creator_address=admin_address,
        level_names=cfg.get("level_names"),
    )

def _bootstrap_all_members(chain: Blockchain, chain_id: str, cfg: dict):
    members       = load_members(chain_id)
    admin_address = cfg["admin_address"]

    from blockchain.core.state import ValidatorState
    if not chain.state.get_validator(admin_address):
        admin_profile = _find_user_by_address(admin_address)
        if admin_profile:
            kp = KeyPair(admin_profile["private_key"])
            validator = ValidatorState(
                address=admin_address,
                pub_key=kp.get_public_key_hex(),
                power=10,
                name="validator_0"
            )
            chain.state.add_validator(validator)
            if hasattr(chain.consensus, 'stakes'):
                chain.consensus.stakes[admin_address] = float(
                    chain.consensus.config.get('min_stake', 100)
                )

    for address, level in members.items():
        chain.state.grant_permission(address, 'can_transfer')
        acct = chain.state.get_account(address)
        if acct.balance == 0:
            acct.balance = 10000 if address == admin_address else 100
        if address == admin_address:
            for perm in ['can_grant_permissions', 'can_revoke_permissions',
                         'can_update_validators']:
                chain.state.grant_permission(address, perm)

def get_blockchain(chain_id: str, user: dict) -> Blockchain:
    if chain_id not in _chain_cache:
        cfg = load_chain_config(chain_id)
        if not cfg:
            raise HTTPException(404, f"Chain '{chain_id}' not found")
        chain = _build_blockchain(cfg)
        _bootstrap_all_members(chain, chain_id, cfg)
        _chain_cache[chain_id] = chain
    return _chain_cache[chain_id]

def _patch_member_into_cache(chain_id: str, address: str, is_admin: bool = False):
    if chain_id not in _chain_cache:
        return
    chain = _chain_cache[chain_id]
    chain.state.grant_permission(address, 'can_transfer')
    acct = chain.state.get_account(address)
    if acct.balance == 0:
        acct.balance = 10000 if is_admin else 100
    if is_admin:
        for perm in ['can_grant_permissions', 'can_revoke_permissions',
                     'can_update_validators']:
            chain.state.grant_permission(address, perm)


# ── Dependency ─────────────────────────────────────────────────────────────────

def require_active_chain(user: dict = Depends(get_current_user)):
    chain_id = get_active_chain(user["username"])
    if not chain_id:
        raise HTTPException(503, "No active chain. Create or join one first.")
    if not is_member(chain_id, user["address"]):
        raise HTTPException(403, "You are not a member of this chain.")
    chain = get_blockchain(chain_id, user)
    return {"user": user, "chain": chain, "chain_id": chain_id}


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="Permissioned Blockchain API", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.post("/auth/register")
def register(req: RegisterRequest):
    profile = register_user(req.username, req.password)
    return {
        "status":   "registered",
        "username": profile["username"],
        "address":  profile["address"],
    }

@app.post("/auth/login")
def login(req: LoginRequest):
    token = login_user(req.username, req.password)
    profile = load_user(req.username)
    return {
        "status":   "ok",
        "token":    token,
        "username": req.username,
        "address":  profile["address"],
    }

@app.post("/auth/logout")
def logout(user: dict = Depends(get_current_user)):
    logout_user(user["_token"])
    return {"status": "logged_out"}

@app.delete("/auth/delete")
def delete_account(user: dict = Depends(get_current_user)):
    delete_user(user["username"], user["_token"])
    return {"status": "deleted"}


# ── User ───────────────────────────────────────────────────────────────────────

@app.get("/user/me")
def get_my_info(user: dict = Depends(get_current_user)):
    chain_id    = get_active_chain(user["username"])
    user_chains = get_user_chains(user["address"])
    info = {
        "username":     user["username"],
        "address":      user["address"],
        "chains":       user_chains,
        "active_chain": chain_id,
    }
    if chain_id:
        chain = get_blockchain(chain_id, user)
        acct  = chain.state.get_account(user["address"])
        level = chain.get_user_permission_level(user["address"])
        cfg   = load_chain_config(chain_id)
        names = cfg.get("level_names", []) if cfg else []
        info.update({
            "balance":          acct.balance,
            "permission_level": level,
            "permission_label": names[level - 1] if names and level is not None and 1 <= level <= len(names) else str(level),
        })
    return info


# ── Chains ─────────────────────────────────────────────────────────────────────

@app.get("/chains")
def get_my_chains(user: dict = Depends(get_current_user)):
    user_chains = get_user_chains(user["address"])
    active      = get_active_chain(user["username"])
    result = []
    for cid in user_chains:
        cfg = load_chain_config(cid)
        if cfg:
            safe = {k: v for k, v in cfg.items() if k != "admin_private_key"}
            safe["is_active"] = (cid == active)
            result.append(safe)
    return {"chains": result, "active": active}

@app.get("/chains/discoverable")
def get_open_chains(user: dict = Depends(get_current_user)):
    user_chains = get_user_chains(user["address"])
    result = []
    for cid in list_all_chains():
        if cid in user_chains:
            continue
        cfg = load_chain_config(cid)
        if cfg and cfg.get("open_membership", True):
            result.append({
                "chain_id":          cfg["chain_id"],
                "consensus":         cfg["consensus"],
                "permission_levels": cfg["permission_levels"],
                "created_at":        cfg["created_at"],
            })
    return {"chains": result}

@app.get("/chains/invites")
def get_my_invites(user: dict = Depends(get_current_user)):
    """Chains where user has been invited but hasn't joined yet."""
    active = get_active_chain(user["username"])
    result = []
    for cid in list_all_chains():
        cfg = load_chain_config(cid)
        if not cfg:
            continue
        # Only invite-only chains
        if cfg.get("open_membership", True):
            continue
        # User must be in members.json (admin added them)
        if not is_member(cid, user["address"]):
            continue
        # Don't show chains they're already actively using
        if cid == active:
            continue
        result.append({
            "chain_id":          cfg["chain_id"],
            "consensus":         cfg["consensus"],
            "permission_levels": cfg["permission_levels"],
            "admin_address":     cfg["admin_address"],
            "created_at":        cfg["created_at"],
        })
    return {"invites": result}

@app.post("/chains/join")
def join_chain(req: JoinChainRequest, user: dict = Depends(get_current_user)):
    cfg = load_chain_config(req.chain_id)
    if not cfg:
        raise HTTPException(404, f"Chain '{req.chain_id}' not found")
    if not cfg.get("open_membership", True):
        raise HTTPException(403, "This chain is invite-only.")
    if is_member(req.chain_id, user["address"]):
        raise HTTPException(400, "Already a member of this chain.")
    add_member(req.chain_id, user["address"], 0)
    set_active_chain(user["username"], req.chain_id)
    _patch_member_into_cache(req.chain_id, user["address"], is_admin=False)
    return {"status": "joined", "chain_id": req.chain_id, "permission_level": 0}

@app.post("/chains/switch")
def switch_chain(req: SwitchChainRequest, user: dict = Depends(get_current_user)):
    if not is_member(req.chain_id, user["address"]):
        raise HTTPException(403, "You are not a member of this chain.")
    set_active_chain(user["username"], req.chain_id)
    return {"status": "switched", "active_chain": req.chain_id}

@app.get("/chains/active")
def get_active(user: dict = Depends(get_current_user)):
    chain_id = get_active_chain(user["username"])
    return {"active_chain": chain_id, "configured": chain_id is not None}

@app.get("/chain/config")
def get_chain_config(ctx: dict = Depends(require_active_chain)):
    cfg = load_chain_config(ctx["chain_id"])
    return {k: v for k, v in cfg.items() if k != "admin_private_key"}


# ── Setup ──────────────────────────────────────────────────────────────────────

@app.get("/setup/status")
def setup_status():
    return {"chains_exist": len(list_all_chains()) > 0}

@app.post("/setup/init")
def setup_init(req: SetupRequest, user: dict = Depends(get_current_user)):
    chain_id = req.chain_id.strip()
    if not chain_id:
        raise HTTPException(400, "chain_id cannot be empty")
    if load_chain_config(chain_id):
        raise HTTPException(400, f"Chain '{chain_id}' already exists.")
    if req.consensus not in ("poa","pos","pbft","round_robin","tendermint","raft"):
        raise HTTPException(400, "Invalid consensus mechanism")
    if not (2 <= req.permission_levels <= 10):
        raise HTTPException(400, "permission_levels must be 2–10")

    cfg = {
        "chain_id":                   chain_id,
        "consensus":                  req.consensus,
        "permission_levels":          req.permission_levels,
        "level_names":                req.level_names,
        "max_transactions_per_block": req.max_transactions_per_block,
        "allow_file_storage":         req.allow_file_storage,
        "open_membership":            req.open_membership,
        "admin_address":              user["address"],
        "created_at":                 time.time(),
    }
    save_chain_config(chain_id, cfg)
    top_level = req.permission_levels - 1
    add_member(chain_id, user["address"], top_level)
    chain = get_blockchain(chain_id, user)
    set_active_chain(user["username"], chain_id)
    return {
        "status":                     "created",
        "chain_id":                   chain_id,
        "consensus":                  req.consensus,
        "permission_levels":          req.permission_levels,
        "max_transactions_per_block": req.max_transactions_per_block,
        "allow_file_storage":         req.allow_file_storage,
        "open_membership":            req.open_membership,
        "admin_address":              user["address"],
    }


# ── Invite / Members ───────────────────────────────────────────────────────────

@app.post("/chains/{chain_id}/invite")
def invite_member(chain_id: str, req: InviteRequest, user: dict = Depends(get_current_user)):
    cfg = load_chain_config(chain_id)
    if not cfg:
        raise HTTPException(404, "Chain not found")
    if cfg["admin_address"] != user["address"]:
        raise HTTPException(403, "Only the chain admin can invite members.")
    if is_member(chain_id, req.target_address):
        raise HTTPException(400, "Address is already a member.")
    add_member(chain_id, req.target_address, req.permission_level)
    _patch_member_into_cache(chain_id, req.target_address, is_admin=False)
    return {"status": "invited", "address": req.target_address, "level": req.permission_level}

@app.get("/chains/{chain_id}/members")
def get_members(chain_id: str, user: dict = Depends(get_current_user)):
    if not is_member(chain_id, user["address"]):
        raise HTTPException(403, "Not a member of this chain.")
    members = load_members(chain_id)
    cfg     = load_chain_config(chain_id)
    names   = cfg.get("level_names", []) if cfg else []
    return {
        "chain_id": chain_id,
        "members": [
            {
                "address": addr,
                "level":   lvl,
                "label": names[lvl - 1] if names and 1 <= lvl <= len(names) else str(lvl)
            }
            for addr, lvl in members.items()
        ]
    }


# ── Chain info ─────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "active", "version": "3.0"}

@app.get("/chain/info")
def get_chain_info(ctx: dict = Depends(require_active_chain)):
    return ctx["chain"].get_chain_info()

@app.get("/chain/blocks")
def get_blocks(limit: int = 10, ctx: dict = Depends(require_active_chain)):
    return [b.to_dict() for b in ctx["chain"].blocks[-limit:]]

@app.get("/chain/consensus-log")
def get_consensus_log(limit: int = 20, ctx: dict = Depends(require_active_chain)):
    chain = ctx["chain"]
    log = []
    for block in ctx["chain"].blocks[-limit:]:
        entry = {
            "block_height":  block.height,
            "proposer":      block.proposer if hasattr(block, 'proposer') else "unknown",
            "consensus":     load_chain_config(ctx["chain_id"])["consensus"],
            "tx_count":      len(block.transactions),
            "timestamp":     block.timestamp,
            "block_hash":    block.hash,
            "signature_valid": chain.consensus.verify_block(block) if hasattr(chain.consensus, 'verify_block') else None,
        }
        log.append(entry)
    return {"consensus": load_chain_config(ctx["chain_id"])["consensus"], "log": log}

@app.get("/chain/consensus-info")
def get_consensus_info(ctx: dict = Depends(require_active_chain)):
    chain  = ctx["chain"]
    cfg    = load_chain_config(ctx["chain_id"])
    cons   = chain.consensus
    name   = cfg["consensus"]

    # Safe validator info — only address (truncated) and power, never private key
    validators = chain.state.get_active_validators()
    safe_validators = [
        {
            "address_short": v.address[:8] + "…" + v.address[-4:],
            "power":         v.power,
            "active":        v.active,
            "blocks_proposed": v.total_blocks_proposed,
        }
        for v in validators
    ]

    # Per-mechanism live state
    mechanism_state = {}
    if name == "poa":
        mechanism_state = {
            "authorities_count": len(cons.authorities),
            "current_proposer_index": cons.current_proposer_index,
            "selection_rule": f"height % {len(cons.authorities)} = slot index",
        }
    elif name == "round_robin":
        mechanism_state = {
            "validators_in_rotation": len(cons.validator_list),
            "current_index": cons.current_index,
            "selection_rule": f"height % {len(cons.validator_list)} = slot index",
        }
    elif name == "pos":
        total_stake = sum(cons.stakes.values()) if cons.stakes else 0
        mechanism_state = {
            "total_stake":   total_stake,
            "min_stake":     cons.config.get("min_stake", 100),
            "current_epoch": cons.current_epoch,
            "epoch_length":  cons.config.get("epoch_length", 100),
            "selection_rule": "stake-weighted VRF using SHA256(height) seed",
            "stakers_count": len(cons.stakes),
        }
    elif name == "raft":
        mechanism_state = {
            "node_state":    cons.state.value,
            "current_term":  cons.current_term,
            "current_leader": (cons.current_leader[:8] + "…" + cons.current_leader[-4:])
                              if cons.current_leader else "none",
            "log_length":    len(cons.log),
            "commit_index":  cons.commit_index,
            "selection_rule": "only elected leader (by term vote) can propose",
        }
    elif name == "tendermint":
        mechanism_state = {
            "current_round":      cons.current_round.round_num if cons.current_round else 0,
            "total_rounds_ever":  len(cons.rounds),
            "timeout_propose":    cons.config.get("timeout_propose"),
            "timeout_prevote":    cons.config.get("timeout_prevote"),
            "timeout_precommit":  cons.config.get("timeout_precommit"),
            "selection_rule":     "weighted round-robin by voting power",
        }
    elif name == "pbft":
        mechanism_state = {
            "selection_rule": "primary rotates each view; 2f+1 prepare+commit messages required",
        }

    # Per-block proof log — NO full addresses, NO signatures, NO tx content
    block_log = []
    for b in chain.blocks:
        cd = b.consensus_data or {}
        entry = {
            "height":           b.height,
            "proposer_short":   (b.validator_address[:8] + "…" + b.validator_address[-4:])
                                if b.validator_address != "genesis" else "genesis",
            "tx_count":         len(b.transactions),
            "merkle_root_short": b.merkle_root[:12] + "…" if b.merkle_root else None,
            "signed":           bool(b.validator_signature and b.validator_signature != "genesis_signature"),
            "consensus_data":   cd,
        }
        block_log.append(entry)

    return {
        "mechanism":       name,
        "mechanism_state": mechanism_state,
        "validators":      safe_validators,
        "block_log":       block_log,
        "chain_height":    chain.get_height(),
    }


# ── Transactions ───────────────────────────────────────────────────────────────

@app.post("/transaction/transfer")
def send_transfer(tx: TransactionRequest, ctx: dict = Depends(require_active_chain)):
    user  = ctx["user"]
    chain = ctx["chain"]
    acct  = chain.state.get_account(user["address"])
    new_tx = Transaction(
        tx_type=TransactionType.TRANSFER,
        sender=user["address"],
        inputs=[TransactionInput(from_address=user["address"], amount=tx.amount)],
        outputs=[TransactionOutput(to_address=tx.recipient, amount=tx.amount)],
        nonce=acct.nonce,
        timestamp=None
    )
    new_tx.sign(user["private_key"])
    if not chain.add_transaction(new_tx):
        raise HTTPException(400, "Transaction rejected")
    return {"status": "submitted", "hash": new_tx.hash()}


# ── Permissions ────────────────────────────────────────────────────────────────

@app.get("/permissions/user/{address}")
def get_user_level(address: str, ctx: dict = Depends(require_active_chain)):
    level = ctx["chain"].get_user_permission_level(address)
    return {"address": address, "level": level}

@app.post("/permissions/promote")
def promote_user(req: PermissionRequest, ctx: dict = Depends(require_active_chain)):
    from blockchain.core.transaction import PermissionTransaction
    user = ctx["user"]
    tx = PermissionTransaction(
        sender=user["address"],
        target_address=req.target,
        action="set_level",
        level=req.level
    )
    tx.sign(user["private_key"])
    if not ctx["chain"].add_transaction(tx):
        raise HTTPException(400, "Promotion rejected")
    return {"status": "submitted", "hash": tx.hash()}


# ── Data / Secret Files ────────────────────────────────────────────────────────

@app.post("/data/store")
def store_intel(req: DataStoreRequest, ctx: dict = Depends(require_active_chain)):
    user  = ctx["user"]
    chain = ctx["chain"]
    cfg   = load_chain_config(ctx["chain_id"])
    num_levels = cfg.get("permission_levels", 2)

    if req.security_level < 1 or req.security_level >= num_levels:
        raise HTTPException(
            400,
            f"Invalid security level {req.security_level}. Must be 1–{num_levels - 1}."
        )

    # Check user's own permission level — cannot store above their level
    user_level = chain.get_user_permission_level(user["address"])
    if user_level is None or req.security_level > user_level:
        raise HTTPException(
            403,
            f"You are Level {user_level}. Cannot store a file at Level {req.security_level}."
        )


    unique_id = f"{req.data_id}-{uuid.uuid4().hex[:8]}"
    success = chain.store_data(
        data_id=unique_id,
        content=req.content,
        security_level=req.security_level,
        owner_address=user["address"],
        metadata={"name": req.data_id}
    )
    if not success:
        raise HTTPException(403, "Failed to store file. Insufficient clearance.")
    return {"status": "stored", "unique_id": unique_id, "name": req.data_id}


@app.get("/data/access/{data_id}")
def read_intel(data_id: str, ctx: dict = Depends(require_active_chain)):
    chain = ctx["chain"]
    content = chain.access_data(ctx["user"]["address"], data_id)
    if content is None:
        raise HTTPException(403, "ACCESS DENIED: Insufficient clearance or file not found.")
    item = chain.permission_system.data_store.get(data_id)
    return {
        "status":         "granted",
        "data_id":        data_id,
        "name":           item.metadata.get("name", data_id) if item and item.metadata else data_id,
        "content":        content,
        "security_level": item.security_level if item else None,
    }


@app.get("/data/list")
def list_all_data(ctx: dict = Depends(require_active_chain)):
    chain = ctx["chain"]
    if not chain.permission_system:
        return {"items": []}
    items = []
    for item in chain.permission_system.data_store.values():
        items.append({
            "data_id":        item.data_id,
            "name":           item.metadata.get("name", item.data_id) if item.metadata else item.data_id,
            "security_level": item.security_level,
            "owner":          item.owner,
            "created_at":     item.created_at,
        })
    return {"items": items}


@app.get("/data/mine")
def list_my_data(ctx: dict = Depends(require_active_chain)):
    chain = ctx["chain"]
    items = chain.get_accessible_data(ctx["user"]["address"])
    return {
        "items": [
            {
                "data_id":        i.data_id,
                "name":           i.metadata.get("name", i.data_id) if i.metadata else i.data_id,
                "security_level": i.security_level,
                "owner":          i.owner,
            }
            for i in items
        ]
    }


# ── Mine ───────────────────────────────────────────────────────────────────────

@app.post("/mine")
def force_mine(ctx: dict = Depends(require_active_chain)):
    chain         = ctx["chain"]
    cfg           = load_chain_config(ctx["chain_id"])
    max_txs       = cfg.get("max_transactions_per_block", 100)
    admin_address = cfg["admin_address"]

    admin_profile = _find_user_by_address(admin_address)
    if not admin_profile:
        raise HTTPException(500, "Chain admin not found on this node. Cannot mine.")

    all_pending                = chain.pending_transactions[:]
    chain.pending_transactions = all_pending[:max_txs]

    block = chain.propose_block(admin_address, admin_profile["private_key"])

    mined_hashes = {tx.hash() for tx in block.transactions} if block else set()
    chain.pending_transactions = [
        tx for tx in all_pending if tx.hash() not in mined_hashes
    ]

    if block and chain.add_block(block):
        return {"status": "mined", "block_height": block.height, "tx_count": len(block.transactions)}
    return {"status": "skipped", "reason": "No pending transactions or consensus rejected."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
