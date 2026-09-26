"""
Deterministic hashing for the evidence integrity ledger.

Rules (from rules.md §5 — Deterministic hashing):
  • Canonical JSON uses sorted keys and a fixed field set.
  • A schema_version tag is included so future field changes don't
    break verification of older events.
  • Only SHA-256 is used (configurable via HASH_ALGORITHM, but the
    default and only tested path is sha256).
"""

import hashlib
import json
from . import config


# ── Canonical field set ────────────────────────────────────────────────────────
# These are the fields we expect on every ibvap_alerts event.  Unknown fields
# are preserved (sorted in) so we don't silently drop data, but the canonical
# form is reproducible because json.dumps with sort_keys=True is deterministic.

def canonical_json(event: dict) -> str:
    """Return a deterministic JSON string for *event*.

    The output is fully reproducible: keys are sorted, no extra whitespace,
    ASCII-safe, and a ``__schema_version`` sentinel is injected so the same
    raw event hashed under two different schema versions will produce
    different digests (allowing safe migration later).
    """
    # Shallow copy so we don't mutate the caller's dict
    obj = dict(event)
    obj["__schema_version"] = config.SCHEMA_VERSION
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def hash_event(canonical: str) -> str:
    """SHA-256 hex digest of a canonical JSON string."""
    return hashlib.new(config.HASH_ALGORITHM, canonical.encode("utf-8")).hexdigest()


def chain_hash(prev_chain_hash: str, event_hash: str) -> str:
    """Compute the next link in the hash chain.

    chain[n] = SHA-256( chain[n-1] || event_hash[n] )
    """
    combined = (prev_chain_hash + event_hash).encode("utf-8")
    return hashlib.new(config.HASH_ALGORITHM, combined).hexdigest()


# ── Genesis constant ──────────────────────────────────────────────────────────
# The chain starts from a well-known zero hash (64 hex zeros for SHA-256).
GENESIS_HASH = "0" * 64
