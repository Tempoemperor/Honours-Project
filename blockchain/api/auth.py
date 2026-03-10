# blockchain/api/auth.py

import json
import os
import time
import uuid
import hashlib
from typing import Optional
from fastapi import HTTPException, Header
from blockchain.crypto.keys import generate_validator_keys

USERS_DIR = "data/users"

# In-memory sessions: {token: username}
_sessions: dict = {}


# ── Helpers ────────────────────────────────────────────────────────────────────

def user_path(username: str) -> str:
    return os.path.join(USERS_DIR, username, "profile.json")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_user(username: str) -> Optional[dict]:
    path = user_path(username)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def save_user(username: str, profile: dict):
    os.makedirs(os.path.join(USERS_DIR, username), exist_ok=True)
    with open(user_path(username), "w") as f:
        json.dump(profile, f, indent=2)

def list_users() -> list:
    if not os.path.exists(USERS_DIR):
        return []
    return [d for d in os.listdir(USERS_DIR)
            if os.path.isfile(user_path(d))]


# ── Auth operations ────────────────────────────────────────────────────────────

def register_user(username: str, password: str) -> dict:
    if not username.strip():
        raise HTTPException(400, "Username cannot be empty")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if load_user(username):
        raise HTTPException(409, f"Username '{username}' already taken")

    keys = generate_validator_keys(1)[0]
    profile = {
        "username":     username,
        "password_hash": hash_password(password),
        "address":      keys["address"],
        "private_key":  keys["private_key"],
        "created_at":   time.time(),
    }
    save_user(username, profile)
    return profile


def login_user(username: str, password: str) -> str:
    profile = load_user(username)
    if not profile:
        raise HTTPException(401, "Invalid username or password")
    if profile["password_hash"] != hash_password(password):
        raise HTTPException(401, "Invalid username or password")
    token = str(uuid.uuid4())
    _sessions[token] = username
    return token


def logout_user(token: str):
    _sessions.pop(token, None)


def delete_user(username: str, token: str):
    _sessions.pop(token, None)
    path = user_path(username)
    if os.path.exists(path):
        os.remove(path)
    # Remove user directory if empty
    user_dir = os.path.join(USERS_DIR, username)
    if os.path.isdir(user_dir):
        try:
            os.rmdir(user_dir)
        except OSError:
            pass


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency — resolves Bearer token to user profile."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated. Please login.")
    token = authorization.split(" ", 1)[1]
    username = _sessions.get(token)
    if not username:
        raise HTTPException(401, "Session expired or invalid. Please login again.")
    profile = load_user(username)
    if not profile:
        raise HTTPException(401, "User account not found.")
    profile["_token"] = token
    return profile
