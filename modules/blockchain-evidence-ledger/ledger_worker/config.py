"""
Configuration for the Blockchain Evidence Ledger module.

All parameters from parameters.md with environment variable overrides.
"""

import os

# ── Redis ──────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("LEDGER_REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("LEDGER_REDIS_PORT", "6379"))
REDIS_CHANNEL = os.getenv("LEDGER_REDIS_CHANNEL", "ibvap_alerts")

# ── Local ledger DB ────────────────────────────────────────────────────────────
LEDGER_DB_PATH = os.getenv(
    "LEDGER_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "ledger.db"),
)

# ── Hashing ────────────────────────────────────────────────────────────────────
HASH_ALGORITHM = os.getenv("HASH_ALGORITHM", "sha256")
SCHEMA_VERSION = int(os.getenv("SCHEMA_VERSION", "1"))

# ── Anchor schedule ───────────────────────────────────────────────────────────
ANCHOR_INTERVAL_SECONDS = int(os.getenv("ANCHOR_INTERVAL_SECONDS", "30"))
ANCHOR_INTERVAL_EVENTS = int(os.getenv("ANCHOR_INTERVAL_EVENTS", "20"))
ANCHOR_RETRY_BACKOFF = [
    int(s) for s in os.getenv("ANCHOR_RETRY_BACKOFF_SECONDS", "5,15,60").split(",")
]

# ── Blockchain node ───────────────────────────────────────────────────────────
CHAIN_NODE_URL = os.getenv("CHAIN_NODE_URL", "http://127.0.0.1:8545")

# Contract address — read from file (written by deploy.js) or env var
_CONTRACT_FILE = os.path.join(os.path.dirname(__file__), "..", "contract_address.txt")


def get_contract_address() -> str | None:
    """Return the deployed contract address, or None if not yet deployed."""
    addr = os.getenv("CONTRACT_ADDRESS")
    if addr:
        return addr
    if os.path.isfile(_CONTRACT_FILE):
        return open(_CONTRACT_FILE, "r").read().strip()
    return None


# ── Verify API ────────────────────────────────────────────────────────────────
VERIFY_API_PORT = int(os.getenv("VERIFY_API_PORT", "8090"))
