# blockchain/consensus/poa.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class ProofOfAuthority(BaseConsensus):
    """
    Proof of Authority Consensus

    Pre-approved authorities take turns in round-robin.
    Block time is enforced as a minimum interval.
    Authority list is auto-seeded from genesis validators so the
    round-robin always resolves in single-node mode.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time':    2,
            'max_block_size': 2000,
            'authorities':   [],
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)

        self.authorities:            List[str] = list(self.config.get('authorities', []))
        self.current_proposer_index: int       = 0

    def initialize(self, blockchain: 'Blockchain') -> None:
        super().initialize(blockchain)
        if not self.authorities:
            validators     = blockchain.state.get_active_validators()
            self.authorities = [v.address for v in validators]
        print(f"PoA initialized with {len(self.authorities)} authorities")

    def _ensure_authority(self, address: str) -> None:
        if address not in self.authorities:
            self.authorities.append(address)
            print(f"PoA: auto-registered authority {address[:16]}...")

    def select_transactions(self, pending_transactions: List[Transaction],
                            proposer_address: str) -> List[Transaction]:
        max_size   = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: (tx.timestamp, tx.nonce))
        return sorted_txs[:max_size]

    def prepare_consensus_data(self, proposer_address: str,
                               previous_block: Block) -> Dict[str, Any]:
        self._ensure_authority(proposer_address)
        return {
            'consensus':        'poa',
            'authority':        proposer_address,
            'authority_index':  self.current_proposer_index,
            'total_authorities': len(self.authorities),
        }

    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        # Auto-register if missing — handles cache rebuild
        self._ensure_authority(block.validator_address)

        # Enforce round-robin turn
        expected = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected:
            print(f"PoA: wrong authority turn. Expected {str(expected)[:8]}, got {block.validator_address[:8]}")
            return False

        # Enforce minimum block time
        prev_block = self.blockchain.get_block(block.height - 1)
        if prev_block:
            time_diff = block.timestamp - prev_block.timestamp
            if time_diff < self.config['block_time'] * 0.5:
                print(f"PoA: block produced too quickly ({time_diff:.2f}s)")
                return False

        return True

    def select_proposer(self, height: int,
                        validators: List[ValidatorState]) -> Optional[str]:
        if not self.authorities:
            return None
        index                        = height % len(self.authorities)
        self.current_proposer_index  = index
        return self.authorities[index]

    def add_authority(self, address: str) -> bool:
        if address not in self.authorities:
            self.authorities.append(address)
            print(f"PoA: added authority {address[:8]}")
            return True
        return False

    def remove_authority(self, address: str) -> bool:
        if address in self.authorities:
            self.authorities.remove(address)
            print(f"PoA: removed authority {address[:8]}")
            return True
        return False

    def is_authority(self, address: str) -> bool:
        return address in self.authorities

    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        if self.authorities:
            self.current_proposer_index = (self.current_proposer_index + 1) % len(self.authorities)
