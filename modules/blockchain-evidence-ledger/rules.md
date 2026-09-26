# Rules: Blockchain-Anchored Evidence Integrity Ledger

These follow the project's existing non-negotiable design rule (see UNIQUE_FEATURE_ROADMAP.md): every new feature is a separate consumer/producer at the existing integration boundary, and must not import, modify, or block another module.

1. **Read-only on existing data.** ledger-worker only subscribes to Redis and reads from PostgreSQL for hashing. It never writes to another module's tables and never calls another module's code directly.
2. **Append-only ledger.** The local ledger.db table permits INSERT only at the application layer; no UPDATE/DELETE code path may exist for chain records.
3. **Non-blocking anchoring.** On-chain transactions happen on a background schedule, never synchronously in the alert path. A slow or unavailable blockchain node must never delay an alert reaching the dashboard.
4. **No PII on-chain.** Only hashes are anchored on-chain — never face images, plate numbers, or raw event payloads. The chain proves existence and order, it is not a data store.
5. **Deterministic hashing.** The canonical JSON form (key order, field set, timestamp format) used for hashing must be versioned (`schema_version`) so future field additions don't silently break verification of old events.
6. **Graceful degradation.** If the blockchain node is unreachable, the system must clearly report NOT_YET_ANCHORED rather than failing verification outright — a not-yet-anchored event is not the same as a tampered one.
7. **Human-in-the-loop remains intact.** The ledger only detects and reports tampering; it never blocks, deletes, or auto-corrects data, and never triggers any automated response.
