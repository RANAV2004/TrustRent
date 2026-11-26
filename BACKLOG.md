# TrustRent Product Backlog

This backlog maps the Approved SRS v1.0 Use Cases (UC-1 to UC-8) and System Features into Jira-style Epics and User Stories.

---

## 📌 Epic 1: Identity & Gasless Account Abstraction (Sprint 1)
- **TR-101: User Social Onboarding**
  - *As a* new user (tenant/landlord/arbitrator),
  - *I want to* sign in using Google or social auth and get a smart account counterfactual address,
  - *So that* I do not have to manage seed phrases or purchase native POL tokens for gas.
  - *Acceptance Criteria:* User is provisioned an ERC-4337 smart wallet address; JWT session issued.
- **TR-102: Mock Identity Verification & On-Chain Attestation**
  - *As an* onboarding tenant or landlord,
  - *I want to* verify my identity via a mock national ID (Aadhaar/PAN simulation),
  - *So that* the system records an on-chain attestation in `IdentityRegistry` enabling me to enter tenancy contracts.
  - *Acceptance Criteria:* `IdentityRegistry.isVerified(user)` returns `true` post-verification; no PII stored on-chain.

---

## 📌 Epic 2: Tenancy Creation & Lease Anchoring (Sprint 2)
- **TR-201: Draft Tenancy & Lease Hash Anchoring**
  - *As a* verified landlord,
  - *I want to* upload the rental agreement, configure rent, deposit amount, deduction cap, and claim window,
  - *So that* the backend encrypts the file, computes `keccak256(lease)`, and creates a tenancy clone on-chain.
  - *Acceptance Criteria:* File stored encrypted; `TenancyFactory.createTenancy()` emits `TenancyCreated`.
- **TR-202: Dual-Party Lease Signing**
  - *As a* tenant or landlord,
  - *I want to* inspect the lease terms and call `sign()`,
  - *So that* when both parties submit signatures, the tenancy transitions from `Drafted` to `Signed`.
  - *Acceptance Criteria:* State becomes `Signed`; lease terms are permanently immutable.

---

## 📌 Epic 3: Deposit Vault & Evidence Verification (Sprint 2)
- **TR-301: Deposit Locking in Escrow**
  - *As a* tenant,
  - *I want to* lock the required deposit in MockINR into the tenancy vault,
  - *So that* the funds are safely held in neutral smart contract custody.
  - *Acceptance Criteria:* SafeERC20 transfer succeeds; vault balance equals deposit; `DepositLocked` event emitted.
- **TR-302: Move-In Condition Evidence Submission**
  - *As a* tenant or landlord,
  - *I want to* upload timestamped photos/videos of property fixtures prior to occupancy,
  - *So that* the keccak256 root hash of the evidence manifest is anchored on-chain.
  - *Acceptance Criteria:* Hash stored on vault; tenancy automatically transitions to `Active` once deposit is locked and move-in evidence exists.

---

## 📌 Epic 4: Move-Out, Claims & Autonomous Refund (Sprint 3)
- **TR-401: Initiate Move-Out & Anchoring Exit Evidence**
  - *As a* tenant or landlord,
  - *I want to* submit move-out inspection media and trigger move-out,
  - *So that* the state changes to `MoveOut` and the claim timer countdown begins.
  - *Acceptance Criteria:* State becomes `MoveOut`; `claimDeadline = block.timestamp + claimWindow`.
- **TR-402: Landlord Claim Submission with Deduction Cap**
  - *As a* landlord,
  - *I want to* claim a deduction for legitimate damage with supporting evidence refs,
  - *So that* an arbitrator can evaluate the damage claim.
  - *Acceptance Criteria:* Reverts if `claimAmount > deductionCap` or if claim window has expired; state changes to `Disputed`.
- **TR-403: Autonomous Keeper Automatic Full Refund**
  - *As a* tenant whose landlord made no claim during the window,
  - *I want* my full deposit refunded without landlord intervention,
  - *So that* my money is not arbitrarily withheld.
  - *Acceptance Criteria:* Keeper cron detects expired window and submits sponsored `finalizeRefund()`; full deposit returned to tenant; state becomes `Refunded`.

---

## 📌 Epic 5: Dispute Resolution & Arbitration (Sprint 3)
- **TR-501: Assign Neutral Arbitrator**
  - *As an* administrator or system dispatcher,
  - *I want to* assign an approved arbitrator from `ArbitratorRegistry` to a disputed tenancy.
  - *Acceptance Criteria:* Only approved arbitrator can review; `ArbitratorAssigned` event emitted.
- **TR-502: Arbitrator Dispute Settlement**
  - *As an* assigned arbitrator,
  - *I want to* compare move-in vs move-out evidence, review the lease, and submit a split settlement (`decide(landlordAmt, tenantAmt)`),
  - *So that* funds are disbursed strictly in accordance with evidence and capped damages.
  - *Acceptance Criteria:* Invariant enforced: `landlordAmt + tenantAmt == depositAmount` and `landlordAmt <= deductionCap`; payouts executed; state becomes `Refunded`.
- **TR-503: Tenant Direct Claim Acceptance (TBD-3)**
  - *As a* tenant,
  - *I want to* accept the landlord's deduction if I agree with it,
  - *So that* remaining funds are refunded immediately without waiting for an arbitrator.

---

## 📌 Epic 6: Frontends & Real-Time Dashboards (Sprint 4)
- **TR-601: Tenant Dashboard**
  - View active tenancies, sign lease, lock deposit, upload evidence, monitor claim window, view refund status.
- **TR-602: Landlord Dashboard**
  - Create property tenancy draft, upload lease, sign, upload move-in/out evidence, raise claim.
- **TR-603: Arbitrator Dashboard**
  - View assigned disputes, side-by-side evidence viewer with on-chain cryptographic verification, submit binding ruling.
- **TR-604: Mock Faucet Component**
  - Testnet faucet button allowing users to mint 50,000 MockINR for demo tenancies.
