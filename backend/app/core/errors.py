ERROR_CATALOG = {
    "PartyNotVerified": {
        "code": "TR_ERR_001",
        "title": "Identity Not Verified",
        "message": "Both the landlord and tenant must complete government identity verification before a tenancy vault can be created."
    },
    "SelfTenancyNotAllowed": {
        "code": "TR_ERR_002",
        "title": "Invalid Parties",
        "message": "Landlord and tenant cannot be the same account."
    },
    "ExceedsDeductionCap": {
        "code": "TR_ERR_003",
        "title": "Claim Exceeds Deduction Cap",
        "message": "The deduction amount exceeds the maximum allowable cap agreed in the signed lease."
    },
    "ClaimWindowPassed": {
        "code": "TR_ERR_004",
        "title": "Claim Window Elapsed",
        "message": "The move-out inspection and claim window has expired. Damage claims can no longer be submitted."
    },
    "ClaimWindowNotPassed": {
        "code": "TR_ERR_005",
        "title": "Claim Window Still Active",
        "message": "The landlord's claim window has not yet concluded. The autonomous deposit refund unlocks once the deadline passes."
    },
    "InvalidSettlementSplit": {
        "code": "TR_ERR_006",
        "title": "Invalid Payout Sum",
        "message": "The combined settlement amounts for landlord and tenant must exactly equal the total deposited amount."
    },
    "NotApprovedArbitrator": {
        "code": "TR_ERR_007",
        "title": "Unapproved Arbitrator",
        "message": "The designated arbitrator is not recognized or approved in the Arbitrator Registry."
    },
    "ArbitratorInactivityTimeoutNotPassed": {
        "code": "TR_ERR_008",
        "title": "Arbitration Active",
        "message": "Dispute resolution is actively assigned to an arbitrator. Inactivity fallback refund unlocks after 30 days without a decision."
    },
    "Unauthorized": {
        "code": "TR_ERR_009",
        "title": "Access Denied",
        "message": "Your account does not possess permission to execute this operation on this tenancy vault."
    },
    "InvalidState": {
        "code": "TR_ERR_010",
        "title": "Invalid Tenancy State",
        "message": "This action cannot be performed in the current state of the tenancy lifecycle."
    },
    "AlreadyInitialized": {
        "code": "TR_ERR_011",
        "title": "Already Initialized",
        "message": "This tenancy vault contract is already permanently configured."
    }
}
def resolve_error_message(error_name: str) -> dict:
    return ERROR_CATALOG.get(error_name, {
        "code": "TR_ERR_UNKNOWN",
        "title": "Execution Reverted",
        "message": f"An unmapped transaction error occurred: {error_name}"
    })
