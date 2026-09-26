"""
Ledger Worker — main entry point.

Subscribes to the ibvap_alerts Redis channel, hashes each event,
appends to an append-only hash chain in SQLite, and periodically
anchors the chain tip on-chain via the AnchorScheduler.

Usage:
    python -m ledger_worker.main
    # or
    python modules/blockchain-evidence-ledger/ledger_worker/main.py
"""

import json
import logging
import signal
import sys
import time
import uuid

import redis

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ledger_worker import config
from ledger_worker import db
from ledger_worker.hasher import canonical_json, hash_event, chain_hash, GENESIS_HASH
from ledger_worker.anchor import AnchorScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ledger.worker")


def _ensure_event_id(event: dict) -> str:
    """Return a stable event_id.

    Most IBVAP alert payloads don't carry a UUID-style event_id — they have
    module + object_id + timestamp.  We synthesise a deterministic composite
    key from those fields so the same raw event always maps to the same
    ledger entry.  If the event does carry ``event_id``, we use it as-is.
    """
    if "event_id" in event:
        return str(event["event_id"])

    # Build a composite key from the fields every module includes
    parts = [
        event.get("module", ""),
        event.get("camera_id", ""),
        event.get("event_type", ""),
        event.get("object_id", ""),
        str(event.get("timestamp", "")),
    ]
    return "|".join(parts)


def run():
    """Main blocking loop."""
    log.info("═══════════════════════════════════════════════════════════")
    log.info("  IBVAP Blockchain Evidence Ledger — Worker starting")
    log.info("  Redis channel : %s", config.REDIS_CHANNEL)
    log.info("  Ledger DB     : %s", config.LEDGER_DB_PATH)
    log.info("  Chain node    : %s", config.CHAIN_NODE_URL)
    log.info("═══════════════════════════════════════════════════════════")

    # ── Initialise DB ─────────────────────────────────────────────────────
    db.get_conn()
    prev_hash = db.get_latest_chain_hash() or GENESIS_HASH
    seq = db.get_latest_seq()
    log.info("Resuming from chain tip: seq=%d  hash=%.16s…", seq, prev_hash)

    # ── Start anchor scheduler ────────────────────────────────────────────
    anchor = AnchorScheduler()
    anchor.start()

    # ── Connect to Redis ──────────────────────────────────────────────────
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT)
    pubsub = r.pubsub()
    pubsub.subscribe(config.REDIS_CHANNEL)
    log.info("Subscribed to Redis channel '%s'", config.REDIS_CHANNEL)

    # ── Graceful shutdown ─────────────────────────────────────────────────
    shutdown = False

    def _sig_handler(signum, frame):
        nonlocal shutdown
        shutdown = True
        log.info("Shutdown signal received.")

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # ── Event loop ────────────────────────────────────────────────────────
    processed = 0
    for message in pubsub.listen():
        if shutdown:
            break

        if message["type"] != "message":
            continue

        try:
            raw = message["data"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            event = json.loads(raw)
            event_id = _ensure_event_id(event)

            # Check for duplicate (e.g. worker restarted mid-batch)
            if db.get_entry_by_event_id(event_id):
                log.debug("Duplicate event_id=%s — skipping", event_id)
                continue

            # Hash
            canonical = canonical_json(event)
            ev_hash = hash_event(canonical)
            new_chain_hash = chain_hash(prev_hash, ev_hash)

            # Persist
            seq = db.append_entry(
                event_id=event_id,
                raw_event=raw,
                event_hash=ev_hash,
                prev_chain_hash=prev_hash,
                chain_hash_val=new_chain_hash,
                schema_version=config.SCHEMA_VERSION,
            )

            prev_hash = new_chain_hash
            processed += 1
            anchor.notify_new_event()

            log.info(
                "Chained #%d  id=%-40s  hash=%.16s…  chain=%.16s…",
                seq, event_id, ev_hash, new_chain_hash,
            )

        except json.JSONDecodeError:
            log.warning("Non-JSON message on %s — skipping", config.REDIS_CHANNEL)
        except Exception:
            log.exception("Error processing event")

    # ── Cleanup ───────────────────────────────────────────────────────────
    anchor.stop()
    pubsub.close()
    r.close()
    log.info("Ledger worker stopped after processing %d events.", processed)


if __name__ == "__main__":
    run()
