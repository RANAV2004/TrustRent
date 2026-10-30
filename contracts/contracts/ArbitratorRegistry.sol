// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

contract ArbitratorRegistry is Ownable { // arbitrators
    mapping(address => bool) private _approvedArbitrators;

    event ArbitratorAdded(address indexed arbitrator);
    event ArbitratorRemoved(address indexed arbitrator);

    error ArbitratorAlreadyApproved(address arbitrator);
    error ArbitratorNotApproved(address arbitrator);
    error ZeroAddress();

    constructor(address initialOwner) Ownable(initialOwner) {
        if (initialOwner == address(0)) revert ZeroAddress();
    }

    function addArbitrator(address arbitrator) external onlyOwner {
        if (arbitrator == address(0)) revert ZeroAddress();
        if (_approvedArbitrators[arbitrator]) revert ArbitratorAlreadyApproved(arbitrator);
        _approvedArbitrators[arbitrator] = true;
        emit ArbitratorAdded(arbitrator);
    }

    function removeArbitrator(address arbitrator) external onlyOwner {
        if (!_approvedArbitrators[arbitrator]) revert ArbitratorNotApproved(arbitrator);
        _approvedArbitrators[arbitrator] = false;
        emit ArbitratorRemoved(arbitrator);
    }

    function isApproved(address arbitrator) external view returns (bool) {
        return _approvedArbitrators[arbitrator];
    }
}
