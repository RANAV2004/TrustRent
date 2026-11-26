// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "@openzeppelin/contracts/access/Ownable.sol";

contract DepositRegistry is Ownable { // deposit receipts
    struct Receipt {
        uint256 amount;
        bytes32 dataHash;
        uint256 recordedAt;
        bool settled;
        uint256 deducted;
        uint256 refunded;
        bytes32 settlementHash;
        uint256 settledAt;
    }
    mapping(bytes32 => Receipt) private _receipts;
    uint256 public totalDeposits;
    event DepositRecorded(bytes32 indexed depositId, uint256 amount, bytes32 dataHash);
    event DepositSettled(bytes32 indexed depositId, uint256 deducted, uint256 refunded, bytes32 settlementHash);
    error AlreadyRecorded(bytes32 depositId);
    error UnknownDeposit(bytes32 depositId);
    error AlreadySettled(bytes32 depositId);
    error InvalidSplit(uint256 deducted, uint256 refunded, uint256 amount);
    error InvalidAmount();
    constructor(address initialOwner) Ownable(initialOwner) {}
    function recordDeposit(bytes32 depositId, uint256 amount, bytes32 dataHash) external onlyOwner {
        if (amount == 0 || dataHash == bytes32(0)) revert InvalidAmount();
        if (_receipts[depositId].recordedAt != 0) revert AlreadyRecorded(depositId);
        _receipts[depositId] = Receipt(amount, dataHash, block.timestamp, false, 0, 0, bytes32(0), 0);
        totalDeposits += 1;
        emit DepositRecorded(depositId, amount, dataHash);
    }
    function settleDeposit(bytes32 depositId, uint256 deducted, uint256 refunded, bytes32 settlementHash) external onlyOwner {
        Receipt storage r = _receipts[depositId];
        if (r.recordedAt == 0) revert UnknownDeposit(depositId);
        if (r.settled) revert AlreadySettled(depositId);
        if (deducted + refunded != r.amount) revert InvalidSplit(deducted, refunded, r.amount);
        r.settled = true;
        r.deducted = deducted;
        r.refunded = refunded;
        r.settlementHash = settlementHash;
        r.settledAt = block.timestamp;
        emit DepositSettled(depositId, deducted, refunded, settlementHash);
    }
    function getDeposit(bytes32 depositId) external view returns (
        uint256 amount, bytes32 dataHash, uint256 recordedAt, bool settled,
        uint256 deducted, uint256 refunded, bytes32 settlementHash, uint256 settledAt
    ) {
        Receipt storage r = _receipts[depositId];
        return (r.amount, r.dataHash, r.recordedAt, r.settled, r.deducted, r.refunded, r.settlementHash, r.settledAt);
    }
}
