# blockchain/consensus/round_robin.py

import time
from typing import List, Dict, Any, Optional
from .base import BaseConsensus
from ..core.block import Block
from ..core.transaction import Transaction
from ..core.state import BlockchainState, ValidatorState


class RoundRobin(BaseConsensus):
    """
    Round Robin Consensus

    Validators take strictly ordered turns.
    Validator list is auto-seeded so the rotation always resolves
    even after cache rebuild.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            'block_time':               2,
            'max_block_size':           1000,
            'skip_inactive_validators': True,
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)

        self.validator_list: List[str] = []
        self.current_index:  int       = 0

    def initialize(self, blockchain: 'Blockchain') -> None:
        super().initialize(blockchain)
        validators         = blockchain.state.get_active_validators()
        self.validator_list = [v.address for v in validators]
        print(f"Round Robin initialized with {len(self.validator_list)} validators")

    def _ensure_in_rotation(self, address: str) -> None:
        if address not in self.validator_list:
            self.validator_list.append(address)
            print(f"Round Robin: auto-added {address[:16]}... to rotation")

    def select_transactions(self, pending_transactions: List[Transaction],
                            proposer_address: str) -> List[Transaction]:
        max_size   = self.config['max_block_size']
        sorted_txs = sorted(pending_transactions, key=lambda tx: (tx.nonce, tx.timestamp))
        return sorted_txs[:max_size]

    def prepare_consensus_data(self, proposer_address: str,
                               previous_block: Block) -> Dict[str, Any]:
        self._ensure_in_rotation(proposer_address)
        return {
            'consensus':         'round_robin',
            'proposer_index':    self.current_index,
            'total_validators':  len(self.validator_list),
            'rotation_position': self.current_index,
        }

    def validate_block(self, block: Block, state: BlockchainState) -> bool:
        self._ensure_in_rotation(block.validator_address)

        expected = self.select_proposer(block.height, state.get_active_validators())
        if block.validator_address != expected:
            print(f"Round Robin: wrong turn. Expected {str(expected)[:8]}, got {block.validator_address[:8]}")
            return False

        return True

    def select_proposer(self, height: int,
                        validators: List[ValidatorState]) -> Optional[str]:
        if not self.validator_list:
            return None
        index               = height % len(self.validator_list)
        self.current_index  = index
        proposer            = self.validator_list[index]

        if self.config['skip_inactive_validators']:
            v = next((v for v in validators if v.address == proposer), None)
            if v and not v.active:
                return self.select_proposer(height + 1, validators)

        return proposer

    def add_validator(self, validator_address: str) -> None:
        if validator_address not in self.validator_list:
            self.validator_list.append(validator_address)
            print(f"Round Robin: added {validator_address[:8]}...")

    def remove_validator(self, validator_address: str) -> None:
        if validator_address in self.validator_list:
            self.validator_list.remove(validator_address)
            print(f"Round Robin: removed {validator_address[:8]}...")

    def reorder_validators(self, new_order: List[str]) -> bool:
        if set(new_order) != set(self.validator_list):
            return False
        self.validator_list = new_order
        return True

    def on_block_committed(self, block: Block, state: BlockchainState) -> None:
        if self.validator_list:
            self.current_index = (self.current_index + 1) % len(self.validator_list)
