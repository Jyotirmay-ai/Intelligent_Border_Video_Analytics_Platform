"""
Tamper Test — Demo-day proof that the ledger detects modifications.

Usage:
    python modules/blockchain-evidence-ledger/demo/tamper_test.py

What it does:
    1. Connects to the ledger SQLite DB.
    2. Picks the most recent entry.
    3. Verifies it via the verify API → expects VERIFIED or NOT_YET_ANCHORED.
    4. Tampers with the stored raw_event (changes the severity field).
    5. Re-verifies → expects TAMPERED.
    6. Restores the original record.
    7. Prints a clear before/after summary.
"""

import json
import os
import sqlite3
import sys
import time

import requests

# Resolve paths relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.join(SCRIPT_DIR, "..")
DEFAULT_DB = os.path.join(MODULE_DIR, "ledger.db")
VERIFY_URL = os.getenv("VERIFY_URL", "http://localhost:8090")

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"


def main():
    db_path = os.getenv("LEDGER_DB_PATH", DEFAULT_DB)

    print(f"\n{BOLD}═══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}  IBVAP Evidence Integrity — Tamper Demonstration{RESET}")
    print(f"{BOLD}═══════════════════════════════════════════════════════{RESET}\n")

    # ── Step 1: Connect to DB ────────────────────────────────────────────────
    if not os.path.isfile(db_path):
        print(f"{RED}✗ Ledger DB not found at: {db_path}{RESET}")
        print("  Run the ledger worker first to collect some events.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM ledger_entries ORDER BY seq DESC LIMIT 1"
    ).fetchone()

    if row is None:
        print(f"{RED}✗ Ledger is empty — no events to test.{RESET}")
        sys.exit(1)

    event_id = row["event_id"]
    original_raw = row["raw_event"]
    original_hash = row["event_hash"]
    seq = row["seq"]

    print(f"  Target entry   : seq #{seq}")
    print(f"  Event ID       : {event_id}")
    print(f"  Original hash  : {original_hash[:32]}…\n")

    # ── Step 2: Verify (should be VERIFIED or NOT_YET_ANCHORED) ──────────────
    print(f"{DIM}Step 1: Verifying original record…{RESET}")
    try:
        res1 = requests.get(f"{VERIFY_URL}/verify/{requests.utils.quote(event_id, safe='')}")
        result1 = res1.json()
        status1 = result1.get("status", "?")
        color1 = GREEN if status1 in ("VERIFIED", "NOT_YET_ANCHORED") else RED
        print(f"  Status: {color1}{status1}{RESET}")
        if status1 == "VERIFIED":
            print(f"  Anchored at block #{result1.get('anchored_block')}")
    except requests.ConnectionError:
        print(f"  {YELLOW}⚠ Verify API not reachable — skipping API check.{RESET}")
        print(f"  {DIM}(You can still see the DB-level tamper below.){RESET}")
        status1 = "SKIPPED"

    # ── Step 3: Tamper with the record ───────────────────────────────────────
    print(f"\n{DIM}Step 2: Tampering with stored event…{RESET}")
    tampered_event = json.loads(original_raw)
    original_severity = tampered_event.get("severity", "info")
    tampered_event["severity"] = "critical" if original_severity != "critical" else "info"
    tampered_raw = json.dumps(tampered_event)

    conn.execute(
        "UPDATE ledger_entries SET raw_event = ? WHERE seq = ?",
        (tampered_raw, seq),
    )
    conn.commit()

    print(f"  Changed severity: {YELLOW}{original_severity}{RESET} → {RED}{tampered_event['severity']}{RESET}")

    # ── Step 4: Re-verify (should be TAMPERED) ──────────────────────────────
    print(f"\n{DIM}Step 3: Re-verifying tampered record…{RESET}")
    try:
        res2 = requests.get(f"{VERIFY_URL}/verify/{requests.utils.quote(event_id, safe='')}")
        result2 = res2.json()
        status2 = result2.get("status", "?")
        color2 = GREEN if status2 == "TAMPERED" else RED
        print(f"  Status: {color2}{status2}{RESET}")
        if status2 == "TAMPERED":
            print(f"  {GREEN}✓ Tampering successfully detected!{RESET}")
        else:
            print(f"  {RED}✗ Expected TAMPERED but got {status2}{RESET}")
    except requests.ConnectionError:
        print(f"  {YELLOW}⚠ Verify API not reachable.{RESET}")
        status2 = "SKIPPED"

    # ── Step 5: Restore original ────────────────────────────────────────────
    print(f"\n{DIM}Step 4: Restoring original record…{RESET}")
    conn.execute(
        "UPDATE ledger_entries SET raw_event = ? WHERE seq = ?",
        (original_raw, seq),
    )
    conn.commit()
    conn.close()
    print(f"  {GREEN}✓ Record restored to original state.{RESET}")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{BOLD}─── Summary ───────────────────────────────────────────{RESET}")
    print(f"  Before tamper : {GREEN}{status1}{RESET}")
    print(f"  After tamper  : {RED if status2 == 'TAMPERED' else YELLOW}{status2}{RESET}")
    print(f"  Record        : {GREEN}Restored{RESET}")
    print()
    print(f"  {BOLD}\"Even we, as developers with direct database access,")
    print(f"   cannot silently alter a past alert without the")
    print(f"   system knowing.\"{RESET}\n")


if __name__ == "__main__":
    main()
