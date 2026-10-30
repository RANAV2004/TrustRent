// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";

contract IdentityRegistry is AccessControl { // identity
    bytes32 public constant ATTESTER_ROLE = keccak256("ATTESTER_ROLE");

    struct Attestation {
        bytes32 attestationHash;
        uint256 timestamp;
        bool active;
    }

    mapping(address => Attestation) private _attestations;

    event UserAttested(address indexed user, bytes32 indexed attestationHash, address indexed attester);
    event UserRevoked(address indexed user, address indexed revoker);

    error AlreadyVerified(address user);
    error NotVerified(address user);
    error ZeroAddress();

    constructor(address initialAdmin, address initialAttester) {
        if (initialAdmin == address(0) || initialAttester == address(0)) revert ZeroAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, initialAdmin);
        _grantRole(ATTESTER_ROLE, initialAttester);
    }

    function attest(address user, bytes32 attestationHash) external onlyRole(ATTESTER_ROLE) {
        if (user == address(0)) revert ZeroAddress();
        _attestations[user] = Attestation({
            attestationHash: attestationHash,
            timestamp: block.timestamp,
            active: true
        });
        emit UserAttested(user, attestationHash, msg.sender);
    }

    function revoke(address user) external onlyRole(ATTESTER_ROLE) {
        if (!_attestations[user].active) revert NotVerified(user);
        _attestations[user].active = false;
        emit UserRevoked(user, msg.sender);
    }

    function isVerified(address user) external view returns (bool) {
        return _attestations[user].active;
    }

    function getAttestation(address user) external view returns (bytes32, uint256, bool) {
        Attestation memory a = _attestations[user];
        return (a.attestationHash, a.timestamp, a.active);
    }
}
