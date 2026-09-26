# PRD: Blockchain-Anchored Evidence Integrity Ledger

## 1. Problem
IBVAP is a border-surveillance platform whose events, alerts, and evidence live in Redis/PostgreSQL. Nothing currently prevents an alert record, snapshot reference, or audit-log entry from being silently edited or deleted after the fact. For a border-security system, that is a real liability — evidence must be provably untampered if it's ever used operationally or reviewed later. This gap also means the project doesn't currently demonstrate its stated theme (Blockchain & Cybersecurity) anywhere in the running system.

## 2. Goal
Give every IBVAP event and evidence pack a tamper-evident fingerprint, chain those fingerprints together, and periodically anchor the chain to an actual blockchain, so any later modification is mathematically detectable — without touching or slowing down any existing analytics module.

## 3. Non-goals (for this hackathon scope)
- Not building a public/production blockchain network — a local Ganache/Hardhat chain is sufficient for the demo.
- Not encrypting evidence content itself (a separate, later hardening item).
- Not replacing PostgreSQL as the system of record — the ledger only proves the integrity of what's already stored there.

## 4. Users
- **Operator** — sees a small integrity badge on alerts/evidence; no direct interaction with the ledger needed.
- **Commander** — can run a "Verify" action on any alert/evidence pack and gets a clear Verified/Tampered result.
- **Judges/Reviewers** — this is the feature that visibly proves the Blockchain & Cybersecurity theme during the demo.

## 5. Success criteria
- Every alert/evidence event generates a hash within under 1 second of being published.
- The hash chain detects any single-field modification to a past event (test by manually editing a stored record, then re-verifying).
- A chain root is anchored on-chain at a configurable interval, visible via a simple CLI/dashboard call.
- If Redis/DB is under load or the blockchain node is briefly unreachable, no existing analytics module slows down or fails — the ledger worker queues and retries independently.

## 6. Key user story (for demo)
"As a commander, I open an evidence pack from a fence-intrusion alert, click Verify, and see 'Integrity Verified — anchored on-chain at block #482, 14:02:11' — proving the record hasn't been altered since capture."

## 7. Constraints / assumptions
- Assumes the existing AlertEngine already publishes a JSON event per alert to Redis (per PROJECT_COMPLETION_STATUS.md). The ledger worker subscribes to the same channel(s); it does not modify AlertEngine.
- Assumes a local Ethereum-compatible dev chain (Ganache/Hardhat) is acceptable for the demo. Anchoring to a public testnet (e.g. Sepolia) is a stretch goal if venue internet is reliable.
