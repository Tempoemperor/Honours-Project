# blockchain/core/merkle.py

import hashlib
from typing import List, Optional, Tuple


class MerkleNode:
    """Node in a Merkle tree"""
    
    def __init__(self, data: str, left: Optional['MerkleNode'] = None, right: Optional['MerkleNode'] = None):
        self.data = data
        self.left = left
        self.right = right
        self.hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate hash of this node"""
        if self.left and self.right:
            # Internal node: hash of concatenated child hashes
            combined = self.left.hash + self.right.hash
            return hashlib.sha256(combined.encode()).hexdigest()
        else:
            # Leaf node: hash of data
            return hashlib.sha256(self.data.encode()).hexdigest()
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node"""
        return self.left is None and self.right is None


class MerkleTree:
    """
    Merkle Tree implementation for efficient verification
    
    Features:
    - Build tree from list of data
    - Generate Merkle root
    - Create and verify Merkle proofs
    - Efficient verification of data inclusion
    """
    
    def __init__(self, data_list: List[str]):
        """
        Initialize Merkle tree from list of data items
        
        Args:
            data_list: List of data items (transaction hashes, etc.)
        """
        if not data_list:
            raise ValueError("Cannot create Merkle tree from empty list")
        
        self.leaves = data_list
        self.root = self._build_tree(data_list)
    
    def _build_tree(self, data_list: List[str]) -> MerkleNode:
        """
        Build Merkle tree from data list
        
        Args:
            data_list: List of data items
            
        Returns:
            Root node of the Merkle tree
        """
        # Create leaf nodes
        nodes = [MerkleNode(data) for data in data_list]
        
        # Build tree bottom-up
        while len(nodes) > 1:
            next_level = []
            
            # Process pairs of nodes
            for i in range(0, len(nodes), 2):
                left = nodes[i]
                
                # If odd number of nodes, duplicate the last one
                if i + 1 < len(nodes):
                    right = nodes[i + 1]
                else:
                    right = nodes[i]
                
                # Create parent node
                parent = MerkleNode(
                    data="",  # Internal nodes don't need data
                    left=left,
                    right=right
                )
                next_level.append(parent)
            
            nodes = next_level
        
        return nodes[0]
    
    def get_root(self) -> str:
        """Get Merkle root hash"""
        return self.root.hash
    
    def get_proof(self, index: int) -> List[Tuple[str, str]]:
        """
        Generate Merkle proof for data at given index
        
        Args:
            index: Index of the data item in the original list
            
        Returns:
            List of (hash, position) tuples representing the proof path
            position is either 'left' or 'right'
        """
        if index < 0 or index >= len(self.leaves):
            raise IndexError(f"Index {index} out of range")
        
        proof = []
        
        # Build proof by traversing from leaf to root
        current_index = index
        level_size = len(self.leaves)
        nodes = [MerkleNode(data) for data in self.leaves]
        
        while level_size > 1:
            next_level = []
            
            for i in range(0, level_size, 2):
                left = nodes[i]
                right = nodes[i + 1] if i + 1 < level_size else nodes[i]
                
                # If current index is in this pair, add sibling to proof
                if i == current_index or i + 1 == current_index:
                    if current_index == i:
                        # Current node is left, add right sibling
                        proof.append((right.hash, 'right'))
                    else:
                        # Current node is right, add left sibling
                        proof.append((left.hash, 'left'))
                    
                    # Update current index for next level
                    current_index = i // 2
                
                parent = MerkleNode("", left, right)
                next_level.append(parent)
            
            nodes = next_level
            level_size = len(nodes)
        
        return proof
    
    @staticmethod
    def verify_proof(
        data: str,
        proof: List[Tuple[str, str]],
        root_hash: str
    ) -> bool:
        """
        Verify Merkle proof
        
        Args:
            data: The data item to verify
            proof: Merkle proof path
            root_hash: Expected root hash
            
        Returns:
            True if proof is valid, False otherwise
        """
        # Start with hash of the data
        current_hash = hashlib.sha256(data.encode()).hexdigest()
        
        # Apply proof path
        for sibling_hash, position in proof:
            if position == 'left':
                # Sibling is on the left
                combined = sibling_hash + current_hash
            else:
                # Sibling is on the right
                combined = current_hash + sibling_hash
            
            current_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        # Check if we arrived at the expected root
        return current_hash == root_hash
    
    def get_tree_visualization(self, node: Optional[MerkleNode] = None, prefix: str = "", is_tail: bool = True) -> str:
        """
        Get ASCII visualization of the Merkle tree
        
        Args:
            node: Current node (uses root if None)
            prefix: Prefix for the current line
            is_tail: Whether this is the last child
            
        Returns:
            String representation of the tree
        """
        if node is None:
            node = self.root
        
        result = prefix
        result += "└── " if is_tail else "├── "
        result += node.hash[:8] + "...\n"
        
        if not node.is_leaf():
            children = []
            if node.left:
                children.append(node.left)
            if node.right and node.right != node.left:
                children.append(node.right)
            
            for i, child in enumerate(children):
                extension = "    " if is_tail else "│   "
                result += self.get_tree_visualization(
                    child,
                    prefix + extension,
                    i == len(children) - 1
                )
        
        return result
    
    def __repr__(self) -> str:
        return f"MerkleTree(leaves={len(self.leaves)}, root={self.root.hash[:16]}...)"


class MerkleProof:
    """
    Container for Merkle proof data
    """
    
    def __init__(self, data: str, index: int, proof: List[Tuple[str, str]], root: str):
        self.data = data
        self.index = index
        self.proof = proof
        self.root = root
    
    def verify(self) -> bool:
        """Verify this proof"""
        return MerkleTree.verify_proof(self.data, self.proof, self.root)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'data': self.data,
            'index': self.index,
            'proof': [{'hash': h, 'position': p} for h, p in self.proof],
            'root': self.root
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MerkleProof':
        """Create from dictionary"""
        proof = [(p['hash'], p['position']) for p in data['proof']]
        return cls(
            data=data['data'],
            index=data['index'],
            proof=proof,
            root=data['root']
        )


def build_merkle_tree_from_hashes(hashes: List[str]) -> MerkleTree:
    """
    Convenience function to build Merkle tree from pre-computed hashes
    
    Args:
        hashes: List of hash strings
        
    Returns:
        MerkleTree instance
    """
    if not hashes:
        # Return tree with single empty hash
        hashes = [hashlib.sha256(b"").hexdigest()]
    
    return MerkleTree(hashes)


def verify_transaction_inclusion(
    transaction_hash: str,
    block_merkle_root: str,
    transaction_index: int,
    proof: List[Tuple[str, str]]
) -> bool:
    """
    Verify that a transaction is included in a block
    
    Args:
        transaction_hash: Hash of the transaction
        block_merkle_root: Merkle root from the block header
        transaction_index: Index of transaction in the block
        proof: Merkle proof path
        
    Returns:
        True if transaction is in the block, False otherwise
    """
    return MerkleTree.verify_proof(transaction_hash, proof, block_merkle_root)


# Example usage and testing
if __name__ == "__main__":
    # Example: Build Merkle tree from transaction hashes
    tx_hashes = [
        "tx1_hash_abc123",
        "tx2_hash_def456",
        "tx3_hash_ghi789",
        "tx4_hash_jkl012",
        "tx5_hash_mno345"
    ]
    
    # Build tree
    tree = MerkleTree(tx_hashes)
    print(f"Merkle Root: {tree.get_root()}")
    print("\nTree Structure:")
    print(tree.get_tree_visualization())
    
    # Generate proof for transaction at index 2
    proof = tree.get_proof(2)
    print(f"\nProof for tx at index 2:")
    for hash_val, position in proof:
        print(f"  {position}: {hash_val[:16]}...")
    
    # Verify proof
    is_valid = MerkleTree.verify_proof(tx_hashes[2], proof, tree.get_root())
    print(f"\nProof valid: {is_valid}")
    
    # Try with wrong data
    is_valid_wrong = MerkleTree.verify_proof("wrong_hash", proof, tree.get_root())
    print(f"Proof with wrong data valid: {is_valid_wrong}")