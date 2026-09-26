"""
Verification API — read-only FastAPI service.

Endpoints:
    GET /verify/{event_id}  →  VERIFIED | TAMPERED | NOT_YET_ANCHORED
    GET /ledger/stats       →  aggregate statistics

Design rules (from rules.md):
    §6 — Graceful degradation: NOT_YET_ANCHORED ≠ TAMPERED.
    §7 — Human-in-the-loop: the API only reports — it never blocks,
          deletes, or auto-corrects data.
"""

import json
import logging
import sys
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Make the ledger_worker package importable from here
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ledger_worker import config
from ledger_worker import db
from ledger_worker.hasher import canonical_json, hash_event, chain_hash

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ledger.verify")

app = FastAPI(
    title="IBVAP Evidence Integrity Verifier",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/verify/{event_id}")
def verify_event(event_id: str):
    """Verify the integrity of a single ledger entry.

    1. Look up the entry by event_id.
    2. Recompute the event hash from the stored raw_event.
    3. Recompute the chain hash from prev_chain_hash + event_hash.
    4. If both match, check whether the entry is covered by an anchored batch.
    5. Return VERIFIED / TAMPERED / NOT_YET_ANCHORED.
    """
    entry = db.get_entry_by_event_id(event_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="event_id not found in ledger")

    # Recompute hashes
    raw_event = json.loads(entry["raw_event"])
    recomputed_canonical = canonical_json(raw_event)
    recomputed_event_hash = hash_event(recomputed_canonical)
    recomputed_chain_hash = chain_hash(entry["prev_chain_hash"], recomputed_event_hash)

    # Compare
    if recomputed_event_hash != entry["event_hash"] or recomputed_chain_hash != entry["chain_hash"]:
        return {
            "event_id": event_id,
            "status": "TAMPERED",
            "chain_seq": entry["seq"],
            "detail": "Recomputed hash does not match stored hash — record has been modified.",
            "anchored_block": None,
            "anchored_at": None,
        }

    # Check if an on-chain anchor covers this entry
    anchor = db.get_anchor_for_seq(entry["seq"])
    if anchor is None:
        return {
            "event_id": event_id,
            "status": "NOT_YET_ANCHORED",
            "chain_seq": entry["seq"],
            "detail": "Hash chain is intact but this entry has not yet been anchored on-chain.",
            "anchored_block": None,
            "anchored_at": None,
        }

    return {
        "event_id": event_id,
        "status": "VERIFIED",
        "chain_seq": entry["seq"],
        "anchored_block": anchor["block_number"],
        "anchored_at": anchor["anchored_at"],
        "tx_hash": anchor["tx_hash"],
    }


@app.get("/ledger/stats")
def ledger_stats():
    """Aggregate stats for the ledger overview."""
    return db.get_stats()


if __name__ == "__main__":
    import uvicorn

    log.info("Starting verify API on port %d", config.VERIFY_API_PORT)
    uvicorn.run(app, host="0.0.0.0", port=config.VERIFY_API_PORT, log_level="info")
