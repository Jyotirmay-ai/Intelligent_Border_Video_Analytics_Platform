# Workflow: Blockchain-Anchored Evidence Integrity Ledger

## Developer workflow (build/run locally)
1. `docker compose up` — bring up Redis + PostgreSQL as today.
2. `npx ganache --deterministic` — start the local chain in a separate terminal.
3. `npx hardhat run scripts/deploy.js --network localhost` — deploy EvidenceAnchor.sol, note the contract address into `.env`.
4. `python ledger_worker/main.py` — start the ledger worker; it begins subscribing and hashing immediately.
5. `python verify_api/main.py` — start the verification endpoint on its own port.
6. Run the existing `start_all.ps1` as normal — the ledger worker is additive and does not need to be listed inside it (or add it as one more line, matching the existing launcher pattern).

## Runtime event workflow
1. Analytics module detects something -> publishes JSON event to Redis (unchanged).
2. ledger-worker receives event -> computes hash -> appends to chain -> persists.
3. Scheduler anchors the chain tip on-chain every N seconds/events.
4. Operator/Commander views an alert -> optionally clicks Verify -> dashboard calls verify-api -> badge updates.

## Demo-day workflow (what to actually show)
1. Trigger a real alert (e.g. fence intrusion on CAM-05).
2. Click Verify — show it comes back Verified, with the anchored block number.
3. Open a terminal/DB tool, manually edit that event's stored timestamp or severity.
4. Click Verify again — show it now returns Tampered, and explain why: the recomputed hash no longer matches the anchored root.
5. One sentence for judges: "Even we, as developers with direct database access, cannot silently alter a past alert without the system knowing."

## Testing workflow
- Unit test: hash of the same event object is always identical (determinism).
- Unit test: chain verification fails when any single stored field is changed.
- Integration test: kill the blockchain node mid-run, confirm ledger-worker keeps chaining locally and recovers anchoring once the node returns.
