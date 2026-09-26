# Architecture: Blockchain-Anchored Evidence Integrity Ledger

## 1. Where it sits
This is a new, independent consumer of the existing Redis event bus — it follows the same isolation pattern as the CAM-01..05 workers described in PROJECT_COMPLETION_STATUS.md. It never calls another module directly and never blocks the publish path.

```
                    (existing, unchanged)
Analytics Modules --> Redis Pub/Sub --> AlertEngine --> PostgreSQL
                            |
                            | (new subscriber, read-only)
                            v
                     ledger-worker
                            |
              +-------------+--------------+
              v                             v
      local hash-chain store        periodic anchor tx
      (SQLite: ledger.db)          (Ganache / Hardhat node)
                            |
                            v
              verify-api (small FastAPI endpoint)
                            |
                            v
              Dashboard "Integrity" badge + Verify action
```

## 2. Components

### 2.1 ledger-worker (new process)
- Subscribes to the same Redis channel(s) AlertEngine already consumes (e.g. `ibvap:events`).
- For each event: builds a canonical JSON string (sorted keys, fixed field set), computes a SHA-256 hash.
- Appends to a local hash chain: `chain[n] = SHA256(chain[n-1] + eventHash[n])`.
- Persists `{event_id, event_hash, chain_hash, prev_chain_hash, seq}` to a local, append-only SQLite ledger DB.

### 2.2 anchor-scheduler (thread inside ledger-worker, or a small separate process)
- Every N seconds or M events (see parameters.md), takes the current chain_hash as the batch root.
- Sends it to a smart contract (`EvidenceAnchor.sol`) deployed on a local chain via web3.py/ethers.js.
- Stores the returned transaction hash + block number alongside the batch record.

### 2.3 EvidenceAnchor smart contract
- Minimal contract: one function to store `(bytes32 root, uint256 eventCount, uint256 timestamp)`, one view function to read anchored roots back by index.
- No business logic on-chain — purely a tamper-evident timestamping bulletin board.

### 2.4 verify-api
- Small read-only HTTP service (FastAPI) with one endpoint: `GET /verify/{event_id}`.
- Recomputes the event's hash from stored data, walks the local chain, confirms the relevant batch root matches what's on-chain.
- Returns `VERIFIED`, `TAMPERED`, or `NOT_YET_ANCHORED`.

### 2.5 Dashboard integration
- A small badge on each alert card / Evidence Pack that calls verify-api on demand (not on every render, to avoid load).

## 3. Data flow (happy path)
1. Existing analytics module publishes an alert to Redis.
2. ledger-worker receives it (in parallel with AlertEngine — both are independent subscribers).
3. Hash computed, appended to local chain, stored in ledger.db.
4. Every N seconds, anchor-scheduler anchors the current chain tip on-chain.
5. Operator/commander clicks Verify -> verify-api confirms integrity -> dashboard shows the result.

## 4. Failure isolation
- If the blockchain node is down: ledger-worker keeps hashing/chaining locally; anchoring retries with backoff; nothing upstream (analytics, AlertEngine, dashboard alert delivery) is affected.
- If ledger-worker itself crashes: alerts still flow to AlertEngine/dashboard exactly as today; only integrity-proofing pauses until it's restarted, and it resumes from the last persisted chain tip.
