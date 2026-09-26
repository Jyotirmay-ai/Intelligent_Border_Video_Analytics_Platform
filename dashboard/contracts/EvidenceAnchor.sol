// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title EvidenceAnchor
 * @notice Tamper-evident timestamping bulletin board for IBVAP.
 *         Stores only SHA-256 batch roots — never raw event data or PII.
 */
contract EvidenceAnchor {
    struct Anchor {
        bytes32 root;
        uint256 eventCount;
        uint256 timestamp;
    }

    Anchor[] public anchors;

    event RootAnchored(
        uint256 indexed index,
        bytes32 root,
        uint256 eventCount,
        uint256 timestamp
    );

    /**
     * @notice Anchor a new batch root on-chain.
     * @param root       SHA-256 chain-tip hash covering all events in this batch.
     * @param eventCount Number of events covered by this batch.
     */
    function anchorRoot(bytes32 root, uint256 eventCount) external {
        anchors.push(Anchor(root, eventCount, block.timestamp));
        emit RootAnchored(anchors.length - 1, root, eventCount, block.timestamp);
    }

    /**
     * @notice Read back a previously anchored batch.
     * @param index Zero-based index of the anchor.
     * @return root       The batch root hash.
     * @return eventCount Number of events in the batch.
     * @return timestamp  Block timestamp when anchored.
     */
    function getAnchor(uint256 index) external view returns (bytes32, uint256, uint256) {
        Anchor memory a = anchors[index];
        return (a.root, a.eventCount, a.timestamp);
    }

    /**
     * @notice Total number of anchored batches.
     */
    function anchorCount() external view returns (uint256) {
        return anchors.length;
    }
}
