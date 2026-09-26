# Parameters: Blockchain-Anchored Evidence Integrity Ledger

| Parameter | Default | Description |
| --- | --- | --- |
| LEDGER_REDIS_CHANNEL | ibvap:events | Channel(s) the ledger worker subscribes to. Should match whatever AlertEngine already consumes. |
| LEDGER_DB_PATH | ./ledger/ledger.db | Local SQLite path for the append-only hash chain. |
| ANCHOR_INTERVAL_SECONDS | 30 | How often the chain tip is anchored on-chain, time-based. |
| ANCHOR_INTERVAL_EVENTS | 20 | Alternative/complementary trigger — anchor after N new events, whichever comes first. |
| CHAIN_NODE_URL | http://127.0.0.1:8545 | RPC endpoint for the local Ganache/Hardhat node. |
| CONTRACT_ADDRESS | (set after deploy) | Deployed EvidenceAnchor contract address. |
| ANCHOR_RETRY_BACKOFF_SECONDS | 5, 15, 60 | Backoff schedule if an anchor transaction fails (e.g. node briefly unreachable). |
| HASH_ALGORITHM | sha256 | Hash function used for event and chain hashing. |
| SCHEMA_VERSION | 1 | Version tag included in canonical JSON so future field changes don't break old verifications. |
| VERIFY_API_PORT | 8090 | Port for the read-only verification endpoint. |
