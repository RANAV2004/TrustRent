# TrustRent State & Action Matrix (Frontend Hand-Off)

This matrix defines what information and user action buttons must be rendered on the Tenant, Landlord, and Arbitrator dashboards for each lifecycle state.

| State | Tenant View & Actions | Landlord View & Actions | Arbitrator View & Actions |
|---|---|---|---|
| **Drafted** | Review anchored lease terms; **Sign Lease** button (`sign()`). | View status; **Sign Lease** button (`sign()`). | Read-only view (inactive). |
| **Signed** | **Lock Deposit** button (`lockDeposit()`); **Upload Move-In Evidence** (`recordMoveInEvidence()`). | **Upload Move-In Evidence** (`recordMoveInEvidence()`); awaiting tenant deposit. | Read-only view (inactive). |
| **Active** | View lease details; live countdown to lease end; upload additional condition notes. | View lease details; live countdown to lease end; upload additional condition notes. | Read-only view (inactive). |
| **MoveOut** | Upload move-out evidence; view live countdown timer for landlord claim window; **Trigger Autonomous Refund** button (`finalizeRefund()`) enabled post-deadline. | Upload move-out evidence; **Submit Capped Claim** button (`raiseClaim()`) enabled within window. | Read-only view (inactive). |
| **Disputed** | View landlord claim and proof evidence; **Accept Claim** button (`acceptClaim()`) to settle directly without arbitration. | View dispute status; awaiting arbitrator ruling or tenant direct acceptance. | **Review Evidence Manifests**; verify hash match status; **Submit Binding Decision** split (`decide()`). |
| **Refunded** | View historical transaction log, settlement split, and refunded token receipts. | View historical transaction log, settlement split, and deduction receipts. | View executed split decision record and case closed status. |
