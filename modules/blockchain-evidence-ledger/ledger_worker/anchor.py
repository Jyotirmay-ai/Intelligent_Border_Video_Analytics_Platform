"""
On-chain anchoring scheduler for the evidence integrity ledger.

Design rules (from rules.md):
  §3 — Non-blocking: anchoring happens on a background thread, never in
        the alert path.
  §4 — No PII on-chain: only the batch root hash + event count are sent.
  §6 — Graceful degradation: if the node is unreachable, we queue and
        retry with exponential backoff.
"""

import json
import logging
import threading
import time

from web3 import Web3

from . import config
from . import db

log = logging.getLogger("ledger.anchor")

# ── ABI (only the functions we call) ──────────────────────────────────────────
EVIDENCE_ANCHOR_ABI = json.loads("""[
  {
    "inputs": [
      {"internalType": "bytes32", "name": "root", "type": "bytes32"},
      {"internalType": "uint256", "name": "eventCount", "type": "uint256"}
    ],
    "name": "anchorRoot",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{"internalType": "uint256", "name": "index", "type": "uint256"}],
    "name": "getAnchor",
    "outputs": [
      {"internalType": "bytes32", "name": "", "type": "bytes32"},
      {"internalType": "uint256", "name": "", "type": "uint256"},
      {"internalType": "uint256", "name": "", "type": "uint256"}
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "anchorCount",
    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
    "stateMutability": "view",
    "type": "function"
  }
]""")


class AnchorScheduler:
    """Background thread that periodically anchors the chain tip on-chain."""

    def __init__(self):
        self._lock = threading.Lock()
        self._events_since_last_anchor = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def notify_new_event(self):
        """Called by the main worker whenever a new event is chained."""
        with self._lock:
            self._events_since_last_anchor += 1

    def start(self):
        """Start the background anchor loop."""
        self._thread = threading.Thread(target=self._loop, daemon=True, name="anchor-scheduler")
        self._thread.start()
        log.info("Anchor scheduler started (interval=%ds, event_threshold=%d)",
                 config.ANCHOR_INTERVAL_SECONDS, config.ANCHOR_INTERVAL_EVENTS)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    # ── Background loop ──────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.is_set():
            self._stop.wait(timeout=config.ANCHOR_INTERVAL_SECONDS)
            if self._stop.is_set():
                break
            self._maybe_anchor()

    def _maybe_anchor(self):
        """Anchor if enough time has passed OR enough events have accumulated."""
        with self._lock:
            pending = self._events_since_last_anchor

        if pending == 0:
            return

        last_anchored_seq = db.get_last_anchored_seq()
        current_seq = db.get_latest_seq()

        if current_seq <= last_anchored_seq:
            return

        chain_tip = db.get_latest_chain_hash()
        if chain_tip is None:
            return

        first_seq = last_anchored_seq + 1
        event_count = current_seq - last_anchored_seq

        # Try to anchor on-chain
        tx_hash, block_number = self._send_anchor(chain_tip, event_count)

        # Record the batch (even if tx failed — tx_hash will be None)
        db.insert_anchor_batch(
            root_chain_hash=chain_tip,
            first_seq=first_seq,
            last_seq=current_seq,
            tx_hash=tx_hash,
            block_number=block_number,
        )

        if tx_hash:
            with self._lock:
                self._events_since_last_anchor = 0
            log.info(
                "✓ Anchored chain tip on-chain: seq %d→%d, block #%s, tx %s",
                first_seq, current_seq, block_number, tx_hash,
            )
        else:
            log.warning(
                "Anchor failed (chain tip seq %d→%d stored locally, will retry)",
                first_seq, current_seq,
            )

    def _send_anchor(self, chain_tip_hex: str, event_count: int) -> tuple[str | None, int | None]:
        """Attempt to send an anchor transaction with retry/backoff."""
        contract_address = config.get_contract_address()
        if not contract_address:
            log.warning("No CONTRACT_ADDRESS configured — skipping on-chain anchor.")
            return None, None

        backoff_schedule = config.ANCHOR_RETRY_BACKOFF

        for attempt, delay in enumerate(backoff_schedule):
            try:
                w3 = Web3(Web3.HTTPProvider(config.CHAIN_NODE_URL))
                if not w3.is_connected():
                    raise ConnectionError("Cannot connect to blockchain node")

                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=EVIDENCE_ANCHOR_ABI,
                )

                # Use the first available account (Hardhat/Ganache default)
                account = w3.eth.accounts[0]

                # Convert hex hash string to bytes32
                root_bytes = bytes.fromhex(chain_tip_hex)

                tx_hash = contract.functions.anchorRoot(
                    root_bytes, event_count
                ).transact({"from": account})

                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
                return receipt.transactionHash.hex(), receipt.blockNumber

            except Exception as e:
                log.warning(
                    "Anchor attempt %d/%d failed: %s — retrying in %ds",
                    attempt + 1, len(backoff_schedule), e, delay,
                )
                if self._stop.wait(timeout=delay):
                    break  # shutting down

        return None, None
