# blockchain/network/peer.py

import time
from typing import Dict, List, Optional, Set
from enum import Enum


class PeerStatus(Enum):
    """Peer connection status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    BANNED = "banned"


class Peer:
    """Network peer representation"""
    
    def __init__(
        self,
        peer_id: str,
        address: str,
        port: int,
        is_validator: bool = False
    ):
        self.peer_id = peer_id
        self.address = address
        self.port = port
        self.is_validator = is_validator
        
        self.status = PeerStatus.DISCONNECTED
        self.last_seen = time.time()
        self.connected_at: Optional[float] = None
        
        # Stats
        self.messages_sent = 0
        self.messages_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        
        # Reputation
        self.reputation_score = 100
        self.misbehavior_count = 0
    
    def connect(self) -> None:
        """Mark peer as connected"""
        self.status = PeerStatus.CONNECTED
        self.connected_at = time.time()
        self.last_seen = time.time()
    
    def disconnect(self) -> None:
        """Mark peer as disconnected"""
        self.status = PeerStatus.DISCONNECTED
        self.connected_at = None
    
    def ban(self, reason: str = "") -> None:
        """Ban this peer"""
        self.status = PeerStatus.BANNED
        print(f"Peer {self.peer_id[:8]} banned: {reason}")
    
    def update_last_seen(self) -> None:
        """Update last seen timestamp"""
        self.last_seen = time.time()
    
    def record_message_sent(self, size: int) -> None:
        """Record sent message"""
        self.messages_sent += 1
        self.bytes_sent += size
    
    def record_message_received(self, size: int) -> None:
        """Record received message"""
        self.messages_received += 1
        self.bytes_received += size
        self.update_last_seen()
    
    def report_misbehavior(self) -> None:
        """Report peer misbehavior"""
        self.misbehavior_count += 1
        self.reputation_score = max(0, self.reputation_score - 10)
        
        if self.reputation_score < 20:
            self.ban("Low reputation score")
    
    def get_endpoint(self) -> str:
        """Get peer endpoint"""
        return f"{self.address}:{self.port}"
    
    def to_dict(self) -> dict:
        return {
            'peer_id': self.peer_id,
            'address': self.address,
            'port': self.port,
            'is_validator': self.is_validator,
            'status': self.status.value,
            'last_seen': self.last_seen,
            'reputation_score': self.reputation_score,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received
        }


class PeerManager:
    """Manages network peers"""
    
    def __init__(self, max_peers: int = 50):
        self.max_peers = max_peers
        self.peers: Dict[str, Peer] = {}
        self.validator_peers: Set[str] = set()
    
    def add_peer(self, peer: Peer) -> bool:
        """Add a new peer"""
        if len(self.peers) >= self.max_peers:
            return False
        
        if peer.peer_id in self.peers:
            return False
        
        self.peers[peer.peer_id] = peer
        
        if peer.is_validator:
            self.validator_peers.add(peer.peer_id)
        
        return True
    
    def remove_peer(self, peer_id: str) -> bool:
        """Remove a peer"""
        if peer_id not in self.peers:
            return False
        
        peer = self.peers[peer_id]
        if peer.is_validator:
            self.validator_peers.discard(peer_id)
        
        del self.peers[peer_id]
        return True
    
    def get_peer(self, peer_id: str) -> Optional[Peer]:
        """Get peer by ID"""
        return self.peers.get(peer_id)
    
    def get_connected_peers(self) -> List[Peer]:
        """Get all connected peers"""
        return [
            peer for peer in self.peers.values()
            if peer.status == PeerStatus.CONNECTED
        ]
    
    def get_validator_peers(self) -> List[Peer]:
        """Get all validator peers"""
        return [
            peer for peer_id, peer in self.peers.items()
            if peer_id in self.validator_peers
        ]
    
    def broadcast_message(self, message: dict) -> int:
        """Broadcast message to all connected peers"""
        count = 0
        for peer in self.get_connected_peers():
            # Simulate sending message
            peer.record_message_sent(len(str(message)))
            count += 1
        return count
    
    def get_peer_count(self) -> dict:
        """Get peer count by status"""
        counts = {status: 0 for status in PeerStatus}
        for peer in self.peers.values():
            counts[peer.status] += 1
        return {status.value: count for status, count in counts.items()}