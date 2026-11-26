# TrustRent Error Catalog for Frontend UI Mapping

| Error Code | Revert Name | User-Facing Plain Title | Plain Language Message |
|---|---|---|---|
| `TR_ERR_001` | `PartyNotVerified` | **Identity Not Verified** | Both the landlord and tenant must complete government identity verification before a tenancy vault can be created. |
| `TR_ERR_002` | `SelfTenancyNotAllowed` | **Invalid Parties** | Landlord and tenant cannot be the same account. |
| `TR_ERR_003` | `ExceedsDeductionCap` | **Claim Exceeds Deduction Cap** | The deduction amount exceeds the maximum allowable cap agreed in the signed lease. |
| `TR_ERR_004` | `ClaimWindowPassed` | **Claim Window Elapsed** | The move-out inspection and claim window has expired. Damage claims can no longer be submitted. |
| `TR_ERR_005` | `ClaimWindowNotPassed` | **Claim Window Still Active** | The landlord's claim window has not yet concluded. The autonomous deposit refund unlocks once the deadline passes. |
| `TR_ERR_006` | `InvalidSettlementSplit` | **Invalid Payout Sum** | The combined settlement amounts for landlord and tenant must exactly equal the total deposited amount. |
| `TR_ERR_007` | `NotApprovedArbitrator` | **Unapproved Arbitrator** | The designated arbitrator is not recognized or approved in the Arbitrator Registry. |
| `TR_ERR_008` | `ArbitratorInactivityTimeoutNotPassed` | **Arbitration Active** | Dispute resolution is actively assigned to an arbitrator. Inactivity fallback refund unlocks after 30 days without a decision. |
| `TR_ERR_009` | `Unauthorized` | **Access Denied** | Your account does not possess permission to execute this operation on this tenancy vault. |
| `TR_ERR_010` | `InvalidState` | **Invalid Tenancy State** | This action cannot be performed in the current state of the tenancy lifecycle. |
| `TR_ERR_011` | `AlreadyInitialized` | **Already Initialized** | This tenancy vault contract is already permanently configured. |