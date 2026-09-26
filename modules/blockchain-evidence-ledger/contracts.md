# Contracts: Blockchain-Anchored Evidence Integrity Ledger

## 1. Redis event contract (consumed, not owned by this feature)
Assumed shape of events already published by existing analytics modules — align field names with the actual code before implementation:

```json
{
  "event_id": "uuid-string",
  "camera_id": "CAM-05",
  "module": "fence-intrusion",
  "type": "intrusion",
  "severity": "high",
  "timestamp": "2026-09-15T10:22:31Z",
  "evidence": {
    "snapshot_path": "dashboard/public/processed/cam_05.jpg",
    "confidence": 0.91
  }
}
```
This feature only reads this contract — it does not add or require new fields from existing modules.

## 2. Ledger DB schema (owned by this feature)
```sql
CREATE TABLE ledger_entries (
  seq             INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id        TEXT NOT NULL UNIQUE,
  event_hash      TEXT NOT NULL,
  prev_chain_hash TEXT NOT NULL,
  chain_hash      TEXT NOT NULL,
  schema_version  INTEGER NOT NULL,
  created_at      TEXT NOT NULL
);

CREATE TABLE anchor_batches (
  batch_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  root_chain_hash TEXT NOT NULL,
  first_seq       INTEGER NOT NULL,
  last_seq        INTEGER NOT NULL,
  tx_hash         TEXT,
  block_number    INTEGER,
  anchored_at     TEXT
);
```

## 3. Smart contract interface — EvidenceAnchor.sol
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract EvidenceAnchor {
    struct Anchor {
        bytes32 root;
        uint256 eventCount;
        uint256 timestamp;
    }

    Anchor[] public anchors;

    event RootAnchored(uint256 indexed index, bytes32 root, uint256 eventCount, uint256 timestamp);

    function anchorRoot(bytes32 root, uint256 eventCount) external {
        anchors.push(Anchor(root, eventCount, block.timestamp));
        emit RootAnchored(anchors.length - 1, root, eventCount, block.timestamp);
    }

    function getAnchor(uint256 index) external view returns (bytes32, uint256, uint256) {
        Anchor memory a = anchors[index];
        return (a.root, a.eventCount, a.timestamp);
    }

    function anchorCount() external view returns (uint256) {
        return anchors.length;
    }
}
```

## 4. verify-api HTTP contract
```
GET /verify/{event_id}

200 OK
{
  "event_id": "uuid-string",
  "status": "VERIFIED" | "TAMPERED" | "NOT_YET_ANCHORED",
  "chain_seq": 142,
  "anchored_block": 482,
  "anchored_at": "2026-09-15T10:23:00Z"
}

404 Not Found  -> event_id not present in ledger
```
