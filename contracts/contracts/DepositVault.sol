// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./IdentityRegistry.sol";
import "./ArbitratorRegistry.sol";

contract DepositVault is ReentrancyGuard { // deposit vault
    using SafeERC20 for IERC20;

    enum State {
        Drafted,
        Signed,
        Active,
        MoveOut,
        Disputed,
        Refunded
    }

    struct EvidenceItem {
        bytes32 manifestHash;
        address submittedBy;
        uint256 timestamp;
        uint8 evidenceType;
    }

    address public landlord;
    address public tenant;
    address public admin;
    address public assignedArbitrator;
    IERC20 public depositToken;
    uint256 public depositAmount;
    uint256 public deductionCap;
    uint256 public claimWindow;
    bytes32 public leaseHash;

    IdentityRegistry public identityRegistry;
    ArbitratorRegistry public arbitratorRegistry;

    State public state;
    bool public landlordSigned;
    bool public tenantSigned;
    bool public depositLocked;
    bool public moveInEvidenceRecorded;

    uint256 public moveOutStartedAt;
    uint256 public claimDeadline;
    uint256 public claimedAmount;
    uint256 public disputeStartedAt;

    uint256 public constant ARBITRATOR_INACTIVITY_TIMEOUT = 30 days;

    EvidenceItem[] public evidences;
    bool private _initialized;

    event Initialized(address indexed landlord, address indexed tenant, uint256 depositAmount, uint256 deductionCap);
    event LeaseSigned(address indexed signer, State newState);
    event DepositLocked(address indexed tenant, uint256 amount);
    event EvidenceRecorded(uint8 indexed evidenceType, bytes32 indexed manifestHash, address indexed submittedBy);
    event TenancyActivated();
    event MoveOutStarted(uint256 deadline, bytes32 moveOutEvidenceHash);
    event ClaimRaised(uint256 amount, string evidenceRef);
    event ClaimAcceptedByTenant(uint256 landlordAmount, uint256 tenantRefundAmount);
    event ArbitratorAssigned(address indexed arbitrator);
    event DisputeDecided(address indexed arbitrator, uint256 landlordAmount, uint256 tenantRefundAmount);
    event TenancyRefunded(uint256 tenantAmount, uint256 landlordAmount);
    event StateChanged(State indexed fromState, State indexed toState);

    error AlreadyInitialized();
    error Unauthorized();
    error InvalidState(State expected, State actual);
    error InvalidParameters();
    error ClaimWindowNotPassed();
    error ClaimWindowPassed();
    error ExceedsDeductionCap(uint256 requested, uint256 cap);
    error InvalidSettlementSplit();
    error NotApprovedArbitrator();
    error ArbitratorInactivityTimeoutNotPassed();
    error LeaseTermsImmutable();

    modifier onlyLandlord() {
        if (msg.sender != landlord) revert Unauthorized();
        _;
    }

    modifier onlyTenant() {
        if (msg.sender != tenant) revert Unauthorized();
        _;
    }

    modifier onlyParties() {
        if (msg.sender != landlord && msg.sender != tenant) revert Unauthorized();
        _;
    }

    modifier inState(State expected) {
        if (state != expected) revert InvalidState(expected, state);
        _;
    }

    constructor() {
        _initialized = true;
    }

    function initialize(
        address _landlord,
        address _tenant,
        address _token,
        uint256 _depositAmount,
        uint256 _deductionCap,
        uint256 _claimWindow,
        bytes32 _leaseHash,
        address _identityRegistry,
        address _arbitratorRegistry,
        address _admin
    ) external {
        if (_initialized) revert AlreadyInitialized();
        if (_landlord == address(0) || _tenant == address(0) || _token == address(0)) revert InvalidParameters();
        if (_deductionCap > _depositAmount || _depositAmount == 0) revert InvalidParameters();
        if (_claimWindow < 3 days || _claimWindow > 30 days) revert InvalidParameters();

        _initialized = true;
        landlord = _landlord;
        tenant = _tenant;
        admin = _admin;
        depositToken = IERC20(_token);
        depositAmount = _depositAmount;
        deductionCap = _deductionCap;
        claimWindow = _claimWindow;
        leaseHash = _leaseHash;
        identityRegistry = IdentityRegistry(_identityRegistry);
        arbitratorRegistry = ArbitratorRegistry(_arbitratorRegistry);

        state = State.Drafted;
        emit Initialized(_landlord, _tenant, _depositAmount, _deductionCap);
        emit StateChanged(State.Drafted, State.Drafted);
    }

    function sign() external onlyParties inState(State.Drafted) {
        if (msg.sender == landlord) landlordSigned = true;
        if (msg.sender == tenant) tenantSigned = true;

        if (landlordSigned && tenantSigned) {
            state = State.Signed;
            emit StateChanged(State.Drafted, State.Signed);
        }
        emit LeaseSigned(msg.sender, state);
    }

    function lockDeposit() external onlyTenant inState(State.Signed) nonReentrant {
        if (depositLocked) revert InvalidParameters();
        depositLocked = true;

        depositToken.safeTransferFrom(msg.sender, address(this), depositAmount);
        emit DepositLocked(msg.sender, depositAmount);

        _checkActivation();
    }

    function recordMoveInEvidence(bytes32 manifestHash) external onlyParties inState(State.Signed) {
        evidences.push(EvidenceItem({
            manifestHash: manifestHash,
            submittedBy: msg.sender,
            timestamp: block.timestamp,
            evidenceType: 0
        }));
        moveInEvidenceRecorded = true;
        emit EvidenceRecorded(0, manifestHash, msg.sender);

        _checkActivation();
    }

    function _checkActivation() internal {
        if (depositLocked && moveInEvidenceRecorded) {
            state = State.Active;
            emit TenancyActivated();
            emit StateChanged(State.Signed, State.Active);
        }
    }

    function startMoveOut(bytes32 moveOutEvidenceHash) external onlyParties inState(State.Active) {
        evidences.push(EvidenceItem({
            manifestHash: moveOutEvidenceHash,
            submittedBy: msg.sender,
            timestamp: block.timestamp,
            evidenceType: 1
        }));

        state = State.MoveOut;
        moveOutStartedAt = block.timestamp;
        claimDeadline = block.timestamp + claimWindow;

        emit MoveOutStarted(claimDeadline, moveOutEvidenceHash);
        emit StateChanged(State.Active, State.MoveOut);
    }

    function raiseClaim(uint256 amount, string calldata evidenceRef) external onlyLandlord inState(State.MoveOut) {
        if (block.timestamp > claimDeadline) revert ClaimWindowPassed();
        if (amount > deductionCap) revert ExceedsDeductionCap(amount, deductionCap);
        if (amount == 0) revert InvalidParameters();

        claimedAmount = amount;
        disputeStartedAt = block.timestamp;
        state = State.Disputed;

        emit ClaimRaised(amount, evidenceRef);
        emit StateChanged(State.MoveOut, State.Disputed);
    }

    function acceptClaim() external onlyTenant inState(State.Disputed) nonReentrant {
        state = State.Refunded;
        uint256 refundAmount = depositAmount - claimedAmount;

        emit ClaimAcceptedByTenant(claimedAmount, refundAmount);
        emit TenancyRefunded(refundAmount, claimedAmount);
        emit StateChanged(State.Disputed, State.Refunded);

        if (claimedAmount > 0) {
            depositToken.safeTransfer(landlord, claimedAmount);
        }
        if (refundAmount > 0) {
            depositToken.safeTransfer(tenant, refundAmount);
        }
    }

    function finalizeRefund() external nonReentrant {
        if (state == State.MoveOut) {
            if (block.timestamp <= claimDeadline) revert ClaimWindowNotPassed();

            state = State.Refunded;
            emit TenancyRefunded(depositAmount, 0);
            emit StateChanged(State.MoveOut, State.Refunded);

            depositToken.safeTransfer(tenant, depositAmount);
        } else if (state == State.Disputed) {
            if (block.timestamp <= disputeStartedAt + ARBITRATOR_INACTIVITY_TIMEOUT) {
                revert ArbitratorInactivityTimeoutNotPassed();
            }

            state = State.Refunded;
            emit TenancyRefunded(depositAmount, 0);
            emit StateChanged(State.Disputed, State.Refunded);

            depositToken.safeTransfer(tenant, depositAmount);
        } else {
            revert InvalidState(State.MoveOut, state);
        }
    }

    function assignArbitrator(address arbitrator) external inState(State.Disputed) {
        if (msg.sender != admin && msg.sender != landlord && msg.sender != tenant) {
            revert Unauthorized();
        }
        if (!arbitratorRegistry.isApproved(arbitrator)) revert NotApprovedArbitrator();
        assignedArbitrator = arbitrator;
        emit ArbitratorAssigned(arbitrator);
    }

    function decide(uint256 landlordAmount, uint256 tenantAmount) external inState(State.Disputed) nonReentrant {
        if (msg.sender != assignedArbitrator) revert Unauthorized();
        if (landlordAmount + tenantAmount != depositAmount) revert InvalidSettlementSplit();
        if (landlordAmount > deductionCap) revert ExceedsDeductionCap(landlordAmount, deductionCap);

        state = State.Refunded;
        emit DisputeDecided(msg.sender, landlordAmount, tenantAmount);
        emit TenancyRefunded(tenantAmount, landlordAmount);
        emit StateChanged(State.Disputed, State.Refunded);

        if (landlordAmount > 0) {
            depositToken.safeTransfer(landlord, landlordAmount);
        }
        if (tenantAmount > 0) {
            depositToken.safeTransfer(tenant, tenantAmount);
        }
    }

    function getEvidenceCount() external view returns (uint256) {
        return evidences.length;
    }
}
