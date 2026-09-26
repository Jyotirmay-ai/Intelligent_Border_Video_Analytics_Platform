"""
Append-only SQLite storage for the evidence integrity ledger.

Design rules (from rules.md §2):
  • Only INSERT is allowed at the application layer.
  • No UPDATE / DELETE code path exists for chain records.
"""

import sqlite3
import os
from datetime import datetime, timezone
from . import config


def _connect() -> sqlite3.Connection:
    """Open (or create) the ledger database and ensure the schema exists."""
    os.makedirs(os.path.dirname(os.path.abspath(config.LEDGER_DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(config.LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_entries (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    raw_event       TEXT    NOT NULL,
    event_hash      TEXT    NOT NULL,
    prev_chain_hash TEXT    NOT NULL,
    chain_hash      TEXT    NOT NULL,
    schema_version  INTEGER NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS anchor_batches (
    batch_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    root_chain_hash TEXT    NOT NULL,
    first_seq       INTEGER NOT NULL,
    last_seq        INTEGER NOT NULL,
    tx_hash         TEXT,
    block_number    INTEGER,
    anchored_at     TEXT
);
"""


# ── Singleton connection ──────────────────────────────────────────────────────
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


# ── Ledger entries ────────────────────────────────────────────────────────────

def append_entry(
    event_id: str,
    raw_event: str,
    event_hash: str,
    prev_chain_hash: str,
    chain_hash_val: str,
    schema_version: int,
) -> int:
    """Insert a new ledger entry and return its sequence number."""
    conn = get_conn()
    cursor = conn.execute(
        """
        INSERT INTO ledger_entries
            (event_id, raw_event, event_hash, prev_chain_hash, chain_hash, schema_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            raw_event,
            event_hash,
            prev_chain_hash,
            chain_hash_val,
            schema_version,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def get_latest_chain_hash() -> str | None:
    """Return the most recent chain_hash, or None if the ledger is empty."""
    row = get_conn().execute(
        "SELECT chain_hash FROM ledger_entries ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    return row["chain_hash"] if row else None


def get_latest_seq() -> int:
    """Return the highest seq, or 0 if the ledger is empty."""
    row = get_conn().execute(
        "SELECT COALESCE(MAX(seq), 0) AS m FROM ledger_entries"
    ).fetchone()
    return row["m"]


def get_entry_by_event_id(event_id: str) -> dict | None:
    """Look up a single ledger entry by its event_id."""
    row = get_conn().execute(
        "SELECT * FROM ledger_entries WHERE event_id = ?", (event_id,)
    ).fetchone()
    return dict(row) if row else None


def get_entries_range(first_seq: int, last_seq: int) -> list[dict]:
    """Return all ledger entries in [first_seq, last_seq] inclusive."""
    rows = get_conn().execute(
        "SELECT * FROM ledger_entries WHERE seq BETWEEN ? AND ? ORDER BY seq",
        (first_seq, last_seq),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Anchor batches ────────────────────────────────────────────────────────────

def get_last_anchored_seq() -> int:
    """Return the last_seq of the most recent anchor batch, or 0."""
    row = get_conn().execute(
        "SELECT COALESCE(MAX(last_seq), 0) AS m FROM anchor_batches"
    ).fetchone()
    return row["m"]


def insert_anchor_batch(
    root_chain_hash: str,
    first_seq: int,
    last_seq: int,
    tx_hash: str | None = None,
    block_number: int | None = None,
) -> int:
    """Record a new anchor batch and return its batch_id."""
    conn = get_conn()
    cursor = conn.execute(
        """
        INSERT INTO anchor_batches
            (root_chain_hash, first_seq, last_seq, tx_hash, block_number, anchored_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            root_chain_hash,
            first_seq,
            last_seq,
            tx_hash,
            block_number,
            datetime.now(timezone.utc).isoformat() if tx_hash else None,
        ),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def get_anchor_for_seq(seq: int) -> dict | None:
    """Return the anchor batch that covers the given sequence number."""
    row = get_conn().execute(
        "SELECT * FROM anchor_batches WHERE first_seq <= ? AND last_seq >= ? AND tx_hash IS NOT NULL ORDER BY batch_id LIMIT 1",
        (seq, seq),
    ).fetchone()
    return dict(row) if row else None


def get_stats() -> dict:
    """Aggregate stats for the /ledger/stats endpoint."""
    conn = get_conn()
    total_events = conn.execute("SELECT COUNT(*) AS c FROM ledger_entries").fetchone()["c"]
    total_anchors = conn.execute("SELECT COUNT(*) AS c FROM anchor_batches WHERE tx_hash IS NOT NULL").fetchone()["c"]
    last = conn.execute(
        "SELECT block_number, anchored_at FROM anchor_batches WHERE tx_hash IS NOT NULL ORDER BY batch_id DESC LIMIT 1"
    ).fetchone()
    return {
        "total_events": total_events,
        "total_anchors": total_anchors,
        "last_anchor_block": last["block_number"] if last else None,
        "last_anchor_at": last["anchored_at"] if last else None,
    }
