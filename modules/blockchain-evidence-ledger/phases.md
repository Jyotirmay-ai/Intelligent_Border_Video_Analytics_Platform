# Phases: Blockchain-Anchored Evidence Integrity Ledger

## Phase 0 — Setup (30-45 min)
- Stand up a local Ganache instance (`npx ganache`) or Hardhat node.
- Scaffold `ledger-worker/` alongside the existing CAM-0X workers, following the same process-per-module pattern.
- Confirm you can subscribe to the existing Redis alert channel read-only without affecting AlertEngine.

## Phase 1 — Local hash chain (MVP, no blockchain yet)
- Implement canonical JSON hashing + chain append logic.
- Persist to local SQLite ledger.db.
- Write a standalone script that tampers with a stored event and proves the chain breaks. This alone is demoable even before the on-chain part exists.

## Phase 2 — On-chain anchoring
- Write and deploy EvidenceAnchor.sol to the local chain.
- Implement anchor-scheduler to push batch roots on an interval.
- Confirm anchored roots are queryable back from the contract.

## Phase 3 — Verification + dashboard badge
- Build verify-api (`GET /verify/{event_id}`).
- Add an "Integrity: Verified / Tampered" badge and a Verify button to the alert card / evidence pack UI.

## Phase 4 — Demo polish (stretch, if time remains)
- Add a simple "Ledger" admin view showing recent chain entries + the last anchored block, for a visual during Q&A.
- Optional: point at a public testnet instead of local Ganache if venue internet is reliable, for extra credibility.

## Suggested cutoff if time is short
Phases 0-2 are enough to genuinely claim "blockchain-backed integrity" in your pitch. Phase 3's badge is what makes it visible in the demo — prioritize it over Phase 4.
