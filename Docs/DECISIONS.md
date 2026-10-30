# TrustRent: Architecture Decisions & Working Defaults

**Document Version:** 1.0  
**Date:** October 27, 2026  
**Context:** Course BTCS706N Major Project, SVIIT, SVVV Indore  
**Precedence Order:** SRS v1.0 (requirements) -> Plan_FastAPI (design & stack) -> Synopsis (context).

---

## 1. Stack & Baseline Decisions

### 1.1 Backend Stack (Supersedes Stale References)
- **Status:** Adopted (as per Plan_FastAPI Section 1 & Section 3).
- **Decision:** The backend is built with **Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic + PostgreSQL + web3.py + Pytest + Ruff**.
- **Rationale:** Supersedes earlier mentions of Node.js/Express/Jest in SRS/Synopsis. Provides robust type validation, asynchronous API performance, native integration with data science/web3 tooling, and enterprise-grade migrations.

### 1.2 Smart Contracts Stack
- **Status:** Adopted.
- **Decision:** **Solidity 0.8.24+** with **OpenZeppelin Contracts (v5.x)**, **Hardhat** (TypeScript), **TypeChain**, **hardhat-gas-reporter**, **solidity-coverage**.
- **Network:** Polygon Amoy testnet for staging/demo, with a local Hardhat node for all daily development and automated tests.

---

## 2. Working Decisions on SRS Open Items (TBD-1 to TBD-11)

These decisions adopt the proposed defaults from Section 8 of `Plan_FastAPI.md` as final working specifications.

| Item | Topic | Decision & Implementation Rule |
|---|---|---|
| **TBD-1** | **Claim Window Duration** | **7 days** default (`7 * 86400` seconds). The lease configuration allows setting a claim window between **3 days and 30 days** inclusive. |
| **TBD-2** | **Deduction Cap Enforcement** | Contract enforces a strict invariant: `deductionCap <= depositAmount`. The backend `CapPolicy` issues a soft warning if deposit or deduction exceeds 2 months' rent (aligned with India Model Tenancy Act, 2021 guidelines). |
| **TBD-3** | **Tenant Claim Acceptance** | **Enabled.** In `Disputed` state, `DepositVault` exposes `acceptClaim()` allowing the tenant to accept the landlord's claim directly, releasing funds immediately (claim amount to landlord, remainder to tenant) without waiting for arbitration. |
| **TBD-4** | **Arbitrator Assignment** | In the v1.0 prototype, the registry admin assigns an approved arbitrator from `ArbitratorRegistry` to a disputed vault (`assignArbitrator(address)`). Random/algorithmic assignment is documented as future work. |
| **TBD-5** | **Arbitrator Fees** | **Zero fees** in prototype v1.0. Incentivization / fee splitting mechanisms are documented as future work. |
| **TBD-6** | **Mock Identity Verification** | Identity fields collected: `fullName`, `phoneNumber`, `idType` (Aadhaar/PAN/VoterID), `idNumber`. Mock service executes a deterministic verification check after simulated async delay. On success, backend attester key signs and records an on-chain attestation in `IdentityRegistry` (`keccak256(userId, timestamp)`). |
| **TBD-7** | **Hashing & Evidence Manifest** | All on-chain hashes use `keccak256`. Multi-file evidence is packaged into a canonical JSON manifest (containing file names, MIME types, individual file keccak256 hashes, timestamps, uploaders). The manifest's keccak256 hash is anchored on-chain. Max file size: 10 MB per file (PNG, JPG, PDF). |
| **TBD-8** | **JWT Lifetime & Paymaster Policy** | JWT access token lifetime is **1 hour**, paired with refresh tokens. ERC-4337 Paymaster sponsorship policy strictly allowlists TrustRent contract addresses and specific function selectors (`sign`, `lockDeposit`, `recordEvidence`, `startMoveOut`, `raiseClaim`, `decide`, `finalizeRefund`), with a daily per-user operation limit. |
| **TBD-9** | **Quantitative Quality Targets** | Contract test coverage **>= 90%**; Backend test coverage **>= 70%**; API response latency P95 **<= 3.0 seconds**; Event-to-dashboard indexing latency **<= 30 seconds**. |
| **TBD-10** | **Data Minimization & Encryption** | Strict zero PII on-chain (only attestations and cryptographic hashes). Off-chain evidence and lease files are encrypted using **AES-256-GCM** (random per-file DEK wrapped by backend master KEK) before storage in `StorageProvider`. |
| **TBD-11** | **Arbitrator Inaction & Inactivity Fallback** | If a tenancy remains in `Disputed` without an arbitrator decision for **30 days** past dispute entry, an inactivity fallback unlocks allowing `finalizeRefund()` to return the remaining deposit to the tenant. Early termination and lease extensions are explicitly out of scope for v1.0. |

---

## 3. Pattern-to-File Mapping

The system architecture cleanly implements Object-Oriented and GoF design patterns across the smart contracts and backend layers, enabling straightforward generation of UML class diagrams:

| Pattern | Component | File Path | Implementation Details |
|---|---|---|---|
| **Inheritance & Domain Hierarchy** | Backend Domain | `backend/app/domain/user.py` | Abstract `User` base class with `Tenant`, `Landlord`, and `Arbitrator` subclasses; encapsulated attributes, role-specific behaviors. |
| **Factory Pattern** | Smart Contracts | `contracts/contracts/TenancyFactory.sol` | Clones minimal proxy instances (`DepositVault`) using EIP-1167 `Clones.cloneDeterministic` to minimize gas. |
| **State Pattern** | Smart Contracts | `contracts/contracts/DepositVault.sol` | Tenancy lifecycle states (`Drafted`, `Signed`, `Active`, `MoveOut`, `Disputed`, `Refunded`); transition guards, custom errors for invalid state transitions. |
| **State Pattern (Mirror)** | Backend | `backend/app/domain/tenancy_state.py` | State machine handler validating preconditions, permitted triggers, and allowable user actions per role. |
| **Strategy Pattern (Storage)** | Backend | `backend/app/services/storage/base.py`<br>`backend/app/services/storage/local_encrypted.py`<br>`backend/app/services/storage/ipfs.py` | `StorageProvider` abstract base class with swappable implementations (`LocalEncryptedStorageProvider` with AES-256-GCM and `IPFSStorageProvider`). |
| **Strategy Pattern (Cap Policy)** | Backend | `backend/app/services/cap_policy.py` | `CapPolicy` interface with `ContractHardCapPolicy` (enforcing cap <= deposit) and `ModelTenancyActPolicy` (soft warning on > 2 months rent). |
| **Observer Pattern** | Smart Contracts & Backend | `contracts/contracts/DepositVault.sol`<br>`backend/app/services/keeper.py`<br>`subgraph/src/mapping.ts` | On-chain event emission (`TenancyCreated`, `LeaseSigned`, `DepositLocked`, `EvidenceRecorded`, `MoveOutStarted`, `ClaimRaised`, `ArbitratorAssigned`, `DecisionMade`, `Refunded`, `StateChanged`) observed by Keeper service and Subgraph indexer. |

---

## 4. Non-Negotiable Contract Invariants

Every contract method and test suite strictly validates these fundamental invariants:
1. **Solvency & Sum Conservation:** Payouts in all termination paths (`finalizeRefund`, `decide`, `acceptClaim`) strictly equal the locked deposit. No token dust or trapped funds.
2. **Cap Invariant:** Total landlord payout never exceeds `deductionCap`, and `deductionCap <= depositAmount`.
3. **No Unilateral Withdrawal:** Neither landlord nor tenant can withdraw funds unilaterally without state progression and condition fulfillment.
4. **Guaranteed Terminal Path:** Every state holding funds has a deterministic path to `Refunded` (via timeout or decision).
5. **Pre-verification Guard:** Vault creation requires both parties to have active identity attestations in `IdentityRegistry`.
6. **Immutability of Anchors:** Lease terms, deposit parameters, and anchored evidence hashes are immutable once the tenancy transitions to `Signed`.
