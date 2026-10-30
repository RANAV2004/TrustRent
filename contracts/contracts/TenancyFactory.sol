// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/proxy/Clones.sol";
import "./IdentityRegistry.sol";
import "./ArbitratorRegistry.sol";
import "./DepositVault.sol";

contract TenancyFactory is Ownable { // tenancy factory
    using Clones for address;

    address public immutable vaultImplementation;
    IdentityRegistry public immutable identityRegistry;
    ArbitratorRegistry public immutable arbitratorRegistry;

    address[] public allTenancies;
    mapping(address => address[]) private _userTenancies;

    event TenancyCreated(
        address indexed vaultAddress,
        address indexed landlord,
        address indexed tenant,
        address depositToken,
        uint256 depositAmount,
        uint256 deductionCap,
        uint256 claimWindow,
        bytes32 leaseHash
    );

    error PartyNotVerified(address party);
    error InvalidParameters();
    error SelfTenancyNotAllowed();

    constructor(
        address _vaultImplementation,
        address _identityRegistry,
        address _arbitratorRegistry
    ) Ownable(msg.sender) {
        if (_vaultImplementation == address(0) || _identityRegistry == address(0) || _arbitratorRegistry == address(0)) {
            revert InvalidParameters();
        }
        vaultImplementation = _vaultImplementation;
        identityRegistry = IdentityRegistry(_identityRegistry);
        arbitratorRegistry = ArbitratorRegistry(_arbitratorRegistry);
    }

    function createTenancy(
        address landlord,
        address tenant,
        address token,
        uint256 depositAmount,
        uint256 deductionCap,
        uint256 claimWindow,
        bytes32 leaseHash
    ) external returns (address vaultAddress) {
        if (landlord == address(0) || tenant == address(0) || token == address(0)) revert InvalidParameters();
        if (landlord == tenant) revert SelfTenancyNotAllowed();
        if (depositAmount == 0 || deductionCap > depositAmount) revert InvalidParameters();
        if (claimWindow < 3 days || claimWindow > 30 days) revert InvalidParameters();
        if (leaseHash == bytes32(0)) revert InvalidParameters();

        if (!identityRegistry.isVerified(landlord)) revert PartyNotVerified(landlord);
        if (!identityRegistry.isVerified(tenant)) revert PartyNotVerified(tenant);

        vaultAddress = vaultImplementation.clone();

        DepositVault(vaultAddress).initialize(
            landlord,
            tenant,
            token,
            depositAmount,
            deductionCap,
            claimWindow,
            leaseHash,
            address(identityRegistry),
            address(arbitratorRegistry),
            owner()
        );

        allTenancies.push(vaultAddress);
        _userTenancies[landlord].push(vaultAddress);
        _userTenancies[tenant].push(vaultAddress);

        emit TenancyCreated(
            vaultAddress,
            landlord,
            tenant,
            token,
            depositAmount,
            deductionCap,
            claimWindow,
            leaseHash
        );
    }

    function totalTenancies() external view returns (uint256) {
        return allTenancies.length;
    }

    function getTenanciesForUser(address user) external view returns (address[] memory) {
        return _userTenancies[user];
    }
}
