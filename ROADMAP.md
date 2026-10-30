# TrustRent: 12-Week Sprint Roadmap


---

## 🏃 Sprint Overview (6 Two-Week Sprints)

| Sprint | Weeks | Primary Focus | Key Milestone |
|---|---|---|---|
| **Sprint 1** | Week 1 - 2 | Initiation, Foundations, Functional Modeling & Account Abstraction | Contracts on Amoy; Gasless Tx demo; Mock Identity attestations |
| **Sprint 2** | Week 3 - 4 | Tenancy Creation, Lease Anchoring, Deposit Vault & Evidence | Tenancy reaches `Active` on Amoy; Full CI/CD active |
| **Sprint 3** | Week 5 - 6 | Move-Out, Claims, Auto-Refund & Arbitrator Resolution | Happy path & Disputed path both pass end-to-end |
| **Sprint 4** | Week 7 - 8 | Subgraph Indexer, Interface Freeze & Full UI Integration | Teammates run complete journeys through React UI |
| **Sprint 5** | Week 9 - 10 | Security Hardening, Slither Analysis & Scenario Testing | All scenarios pass on Staging environment |
| **Sprint 6** | Week 11 - 12 | Performance Evaluation, Documentation, Final Review & Demo | Final thesis defense & live demo deployment |

---

## Detailed Sprint Milestones & Weekly Deliverables

### 🔹 Sprint 1 (Weeks 1 – 2): Foundations & Identity
- [x] **Week 1: Initiation and Foundations** *(In Progress)*
  - [x] Git repository initialization and branching model (`main`, `develop`, feature branches).
  - [x] Root configuration: `.gitignore`, `docker-compose.yml`, `.env.example`.
  - [x] Contracts workspace: Hardhat TypeScript project, OpenZeppelin, `MockINR`, `DepositVault` skeleton.
  - [x] Backend workspace: FastAPI skeleton, Pydantic settings, SQLAlchemy models, Alembic migrations, Pytest setup.
  - [x] Frontend workspace: React + Vite + TypeScript dashboard shell.
  - [ ] Deploy initial contracts to local node & Polygon Amoy testnet.
  - [ ] Resolve Open Items TBD-1 to TBD-4.
- [ ] **Week 2: Functional Modeling & Account Abstraction**
  - [ ] `IdentityRegistry` and `ArbitratorRegistry` contracts.
  - [ ] Mock identity verification backend service (`/identity/verify`) with on-chain attestation.
  - [ ] ERC-4337 Account Abstraction spike (social login, smart account, gasless transaction).
  - [ ] Hand-off: Draft OpenAPI spec & mock API server for frontend team.

### 🔹 Sprint 2 (Weeks 3 – 4): Tenancy Lifecycle & Deposit Escrow
- [ ] **Week 3: Tenancy Creation & Lease Anchoring**
  - [ ] `TenancyFactory` contract with EIP-1167 minimal proxies (`Clones`).
  - [ ] Dual-party `sign()` mechanism and transition to `Signed`.
  - [ ] Backend `StorageProvider` (AES-256-GCM encrypted local / IPFS).
  - [ ] Backend `POST /tenancies/draft` and lease hash verification.
  - [ ] Hand-off: Contracts package v0.1 (ABIs & TypeChain types).
- [ ] **Week 4: Deposit Locking, Evidence Anchoring & CI**
  - [ ] `lockDeposit()` with `SafeERC20` transfers and allowance checks.
  - [ ] Move-in evidence recording (`keccak256` manifest hash anchoring).
  - [ ] Vault state transition guard: `Signed` → `Active`.
  - [ ] GitHub Actions CI workflow (lint, test, Slither static analysis).

### 🔹 Sprint 3 (Weeks 5 – 6): Claims, Auto-Refund & Arbitration
- [ ] **Week 5: Move-Out, Claims & Autonomous Refund**
  - [ ] Move-out evidence submission and `startMoveOut()` trigger.
  - [ ] Landlord `raiseClaim()` enforcing `deductionCap <= depositAmount`.
  - [ ] Background Keeper service running cron to trigger `finalizeRefund()` once claim window lapses.
  - [ ] Hand-off: Error-code catalog.
- [ ] **Week 6: Dispute Arbitration**
  - [ ] Arbitrator role enforcement in `DepositVault`.
  - [ ] Arbitrator review UI & backend `/arbitrator/disputes` endpoints.
  - [ ] `decide(landlordAmt, tenantAmt)` settlement execution and fund release.

### 🔹 Sprint 4 (Weeks 7 – 8): Indexer & Full Integration
- [ ] **Week 7: The Graph Subgraph & Interface Freeze**
  - [ ] Amoy Subgraph mapping on-chain events (`TenancyCreated`, `LeaseSigned`, `DepositLocked`, etc.).
  - [ ] Interface freeze v1.0 (ABIs, GraphQL schema, OpenAPI specs).
- [ ] **Week 8: Full Stack Integration**
  - [ ] Connect React dashboards with FastAPI backend and Subgraph queries.
  - [ ] Complete end-to-end user testing across all 3 roles (Tenant, Landlord, Arbitrator).

### 🔹 Sprint 5 (Weeks 9 – 10): Security Hardening & Edge Cases
- [ ] **Week 9: Security Auditing**
  - [ ] Slither and Solhint static analysis.
  - [ ] Reentrancy and access control verification.
  - [ ] Gas optimization reporting.
- [ ] **Week 10: Scenario Testing & Feature Freeze**
  - [ ] Full simulation of 5 core tenancy scenarios (Happy path, No claim refund, Disputed claim split, Arbitrator inaction, Tenant direct claim acceptance).

### 🔹 Sprint 6 (Weeks 11 – 12): Evaluation & Live Deployment
- [ ] **Week 11: Performance & Evaluation**
  - [ ] Latency benchmarks and gas consumption metrics.
  - [ ] Test coverage reports (Target: >=90% contracts, >=70% backend).
- [ ] **Week 12: Production Staging & Final Defense**
  - [ ] Cloud deployment (Render API & keeper, Vercel frontend, Polygon Amoy contracts).
  - [ ] Project documentation, UML diagrams, and viva demonstration.
