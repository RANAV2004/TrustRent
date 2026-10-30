TrustRent

12-Week Implementation Plan

Smart contracts and backend track, with frontend hand-offs



1. Purpose, roles and how to use this plan

This plan turns the approved SRS into 12 weeks of work. It follows the course timeline (UML first, then implementation, CI/CD, testing and deployment) but lets coding start in Week 1, so that diagrams are checked against working code. The diagrams are worth 30% of the grade and must match the final code.

Track | Who and what

Track

Who and what

Blockchain and backend(your track) | Solidity contracts (factory, vault, registries, mock token), Hardhat tests and deployment to Polygon Amoy, the FastAPI (Python) API, PostgreSQL, hashing, encrypted storage, mock identity service, keeper job, account-abstraction integration, subgraph (indexer), and the CI pipeline for these parts.

Blockchain and backend

(your track)

Solidity contracts (factory, vault, registries, mock token), Hardhat tests and deployment to Polygon Amoy, the FastAPI (Python) API, PostgreSQL, hashing, encrypted storage, mock identity service, keeper job, account-abstraction integration, subgraph (indexer), and the CI pipeline for these parts.

Frontend team | React dashboards for tenant, landlord and arbitrator, social-login screens, calling the API, the indexer and the account-abstraction SDK. They depend on your hand-offs in Section 6.

Frontend team

React dashboards for tenant, landlord and arbitrator, social-login screens, calling the API, the indexer and the account-abstraction SDK. They depend on your hand-offs in Section 6.

Shared | Jira, Git workflow, UML diagrams, weekly progress reports, README, test chapter, the implementation paper, demo.

Shared

Jira, Git workflow, UML diagrams, weekly progress reports, README, test chapter, the implementation paper, demo.

Stack note. This plan follows the SRS and synopsis, updated to a FastAPI backend: Python with FastAPI, PostgreSQL and Pytest.

Calendar note. Week 1 is the first sprint week; dates are left to you. If your final submission is earlier than 12 weeks away, use the priority order in Section 11 to decide what to cut.

2. Architecture

Figure 1. TrustRent system architecture and ownership.

2.1 What lives where

Concern | Design

Concern

Design

Source of truth | The chain holds funds, tenancy state, lease and evidence hashes, claims and decisions. The indexer and API only read it. PostgreSQL stores users, metadata and file references.

Source of truth

The chain holds funds, tenancy state, lease and evidence hashes, claims and decisions. The indexer and API only read it. PostgreSQL stores users, metadata and file references.

Off-chain files | Lease and evidence files are encrypted by the backend (AES-256-GCM, a random key per file wrapped with a master key from environment configuration), stored behind a StorageProvider interface (IPFS pinning or local encrypted), and referenced by CID. Only hashes go on-chain.

Off-chain files

Lease and evidence files are encrypted by the backend (AES-256-GCM, a random key per file wrapped with a master key from environment configuration), stored behind a StorageProvider interface (IPFS pinning or local encrypted), and referenced by CID. Only hashes go on-chain.

Hashing | keccak256, which is native to Solidity and also available in web3.py (backend) and ethers (frontend). A lease hash is the hash of the lease file. Evidence uses a manifest (a JSON list of file hashes, types and timestamps) whose hash is recorded on-chain, so one transaction anchors many files.

Hashing

keccak256, which is native to Solidity and also available in web3.py (backend) and ethers (frontend). A lease hash is the hash of the lease file. Evidence uses a manifest (a JSON list of file hashes, types and timestamps) whose hash is recorded on-chain, so one transaction anchors many files.

Identity | Mock verification in the backend. On success, the backend signer (attester role) writes a hash or flag to IdentityRegistry for the user's smart-account address. No personal data on-chain.

Identity

Mock verification in the backend. On success, the backend signer (attester role) writes a hash or flag to IdentityRegistry for the user's smart-account address. No personal data on-chain.

Gasless use | Social login creates a smart account (ERC-4337). The frontend sends user operations; a bundler and paymaster submit them with gas sponsored. The paymaster policy allows only TrustRent contract calls (FR-7.5).

Gasless use

Social login creates a smart account (ERC-4337). The frontend sends user operations; a bundler and paymaster submit them with gas sponsored. The paymaster policy allows only TrustRent contract calls (FR-7.5).

Automatic refund | A contract cannot run on a timer. The vault exposes finalizeRefund(), callable by anyone once the claim window has passed with no claim. The backend keeper job calls it automatically, and the UI offers it as a fallback, so no landlord action is needed.

Automatic refund

A contract cannot run on a timer. The vault exposes finalizeRefund(), callable by anyone once the claim window has passed with no claim. The backend keeper job calls it automatically, and the UI offers it as a fallback, so no landlord action is needed.

Dashboards | The frontend reads tenancy state from the indexer (GraphQL) and metadata from the API, so the browser never polls the chain.

Dashboards

The frontend reads tenancy state from the indexer (GraphQL) and metadata from the API, so the browser never polls the chain.

2.2 Design patterns and where they appear

Pattern | Contracts | Backend

Pattern

Contracts

Backend

Factory | TenancyFactory creates a vault per tenancy (EIP-1167 minimal proxy clones, for low deployment gas, NFR-P-3) | n/a

Factory

TenancyFactory creates a vault per tenancy (EIP-1167 minimal proxy clones, for low deployment gas, NFR-P-3)

n/a

State | Vault behavior guarded by the tenancy state (Drafted, Signed, Active, MoveOut, Disputed, Refunded); invalid transitions revert | Tenancy status model mirrors the same states

State

Vault behavior guarded by the tenancy state (Drafted, Signed, Active, MoveOut, Disputed, Refunded); invalid transitions revert

Tenancy status model mirrors the same states

Strategy | n/a (cap check is a vault rule) | StorageProvider (IPFS or local encrypted); CapPolicy (hard cap versus soft legal warning)

Strategy

n/a (cap check is a vault rule)

StorageProvider (IPFS or local encrypted); CapPolicy (hard cap versus soft legal warning)

Observer | Events emitted on every transition | Indexer and keeper subscribe to events

Observer

Events emitted on every transition

Indexer and keeper subscribe to events

Inheritance | Vault extends OpenZeppelin base contracts | User base class with Tenant, Landlord, Arbitrator subclasses; private fields with getters

Inheritance

Vault extends OpenZeppelin base contracts

User base class with Tenant, Landlord, Arbitrator subclasses; private fields with getters

3. Tech stack

Layer | Choice | Owner | Notes

Layer

Choice

Owner

Notes

Contracts | Solidity 0.8.x, OpenZeppelin (Ownable/AccessControl, ReentrancyGuard, SafeERC20, Clones) | You | Custom errors, checks-effects-interactions, no admin withdraw

Contracts

Solidity 0.8.x, OpenZeppelin (Ownable/AccessControl, ReentrancyGuard, SafeERC20, Clones)

You

Custom errors, checks-effects-interactions, no admin withdraw

Contract tooling | Hardhat with TypeScript, Chai, hardhat-gas-reporter, solidity-coverage, TypeChain | You | TypeChain gives the frontend typed ABIs

Contract tooling

Hardhat with TypeScript, Chai, hardhat-gas-reporter, solidity-coverage, TypeChain

You

TypeChain gives the frontend typed ABIs

Static analysis | Solhint, Slither | You | Run in CI from Week 4, deeper pass in Week 9

Static analysis

Solhint, Slither

You

Run in CI from Week 4, deeper pass in Week 9

Network | Polygon Amoy (EVM test network) | You | Faucet tokens only; verify contracts on the block explorer

Network

Polygon Amoy (EVM test network)

You

Faucet tokens only; verify contracts on the block explorer

Backend | Python 3.12, FastAPI, Pydantic validation, structlog logging | You | OpenAPI spec generated and served

Backend

Python 3.12, FastAPI, Pydantic validation, structlog logging

You

OpenAPI spec generated and served

Database | PostgreSQL with SQLAlchemy 2.0 and Alembic (migrations) | You | Docker Compose locally, free-tier cloud for staging

Database

PostgreSQL with SQLAlchemy 2.0 and Alembic (migrations)

You

Docker Compose locally, free-tier cloud for staging

Chain access | web3.py (backend), viem or ethers (frontend) | You / FE | RPC provider with free tier

Chain access

web3.py (backend), viem or ethers (frontend)

You / FE

RPC provider with free tier

Account abstraction | ERC-4337 bundler and paymaster, with a social-login and smart-account SDK | You + FE | Choose in the Week 2 spike (see Section 10)

Account abstraction

ERC-4337 bundler and paymaster, with a social-login and smart-account SDK

You + FE

Choose in the Week 2 spike (see Section 10)

Indexer | The Graph subgraph (Subgraph Studio). Fallback: Python event listener into PostgreSQL | You | The Polygon docs list Amoy as supported by The Graph

Indexer

The Graph subgraph (Subgraph Studio). Fallback: Python event listener into PostgreSQL

You

The Polygon docs list Amoy as supported by The Graph

Off-chain storage | IPFS pinning service (for example Pinata) behind StorageProvider; local encrypted provider for tests | You | Encrypt before upload

Off-chain storage

IPFS pinning service (for example Pinata) behind StorageProvider; local encrypted provider for tests

You

Encrypt before upload

Backend tests | Pytest, FastAPI TestClient (httpx), local Hardhat node for integration tests | You | Target set in Section 8

Backend tests

Pytest, FastAPI TestClient (httpx), local Hardhat node for integration tests

You

Target set in Section 8

Frontend | React with Vite and TypeScript, GraphQL client, AA SDK | FE | Uses your published ABIs, OpenAPI and subgraph schema

Frontend

React with Vite and TypeScript, GraphQL client, AA SDK

FE

Uses your published ABIs, OpenAPI and subgraph schema

CI/CD | GitHub Actions: lint, tests, coverage, gas report, deploy to staging | You + FE | Branch protection on develop and main

CI/CD

GitHub Actions: lint, tests, coverage, gas report, deploy to staging

You + FE

Branch protection on develop and main

Hosting | Render (API and keeper), Vercel (frontend), Subgraph Studio, free-tier PostgreSQL | Shared | Free-tier limits are a constraint (SRS 2.5)

Hosting

Render (API and keeper), Vercel (frontend), Subgraph Studio, free-tier PostgreSQL

Shared

Free-tier limits are a constraint (SRS 2.5)

Project management | Jira (6 two-week sprints), Git feature branches, pull requests with review | Shared | Every commit message carries a Jira ID

Project management

Jira (6 two-week sprints), Git feature branches, pull requests with review

Shared

Every commit message carries a Jira ID

4. Smart contract design

4.1 Contracts

Contract | Responsibility

Contract

Responsibility

MockINR | ERC-20 test token standing in for rupees; capped faucet mint so test users can fund deposits.

MockINR

ERC-20 test token standing in for rupees; capped faucet mint so test users can fund deposits.

IdentityRegistry | attest(user, attestationHash) by the attester role (backend signer); revoke; isVerified(user). No personal data.

IdentityRegistry

attest(user, attestationHash) by the attester role (backend signer); revoke; isVerified(user). No personal data.

ArbitratorRegistry | Owner approves or removes arbitrators; isApproved(address).

ArbitratorRegistry

Owner approves or removes arbitrators; isApproved(address).

TenancyFactory | createTenancy(...) checks that both parties are verified, cap is at most the deposit and the claim window is in range, then clones and initializes a vault; emits TenancyCreated.

TenancyFactory

createTenancy(...) checks that both parties are verified, cap is at most the deposit and the claim window is in range, then clones and initializes a vault; emits TenancyCreated.

DepositVault | One per tenancy. Holds the deposit, enforces the state machine, cap, claim window, refund and arbitrator decision (details below).

DepositVault

One per tenancy. Holds the deposit, enforces the state machine, cap, claim window, refund and arbitrator decision (details below).

4.2 Vault interface (first draft for the frontend)

Function | Caller | From state | Effect

Function

Caller

From state

Effect

sign() | Landlord, tenant | Drafted | Records each signature; when both have signed, state becomes Signed

sign()

Landlord, tenant

Drafted

Records each signature; when both have signed, state becomes Signed

lockDeposit() | Tenant | Signed | Pulls the exact deposit in MockINR; once only

lockDeposit()

Tenant

Signed

Pulls the exact deposit in MockINR; once only

recordEvidence(type, hash) | Landlord, tenant | Signed (move-in), Active/MoveOut (move-out) | Stores hash, submitter and timestamp; immutable. Signed becomes Active when the deposit is locked and a move-in hash exists

recordEvidence(type, hash)

Landlord, tenant

Signed (move-in), Active/MoveOut (move-out)

Stores hash, submitter and timestamp; immutable. Signed becomes Active when the deposit is locked and a move-in hash exists

startMoveOut(hash) | Landlord, tenant | Active, after lease end | Records move-out evidence; state MoveOut; claim deadline = now + window

startMoveOut(hash)

Landlord, tenant

Active, after lease end

Records move-out evidence; state MoveOut; claim deadline = now + window

raiseClaim(amount, evidenceRefs) | Landlord | MoveOut, within window | Reverts if amount is above cap or evidence is missing; state Disputed; funds stay locked

raiseClaim(amount, evidenceRefs)

Landlord

MoveOut, within window

Reverts if amount is above cap or evidence is missing; state Disputed; funds stay locked

finalizeRefund() | Anyone | MoveOut, window passed, no claim | Returns the full deposit to the tenant; state Refunded

finalizeRefund()

Anyone

MoveOut, window passed, no claim

Returns the full deposit to the tenant; state Refunded

assignArbitrator(addr) | Registry admin | Disputed | Assigns an approved arbitrator (method: see decisions, Section 8)

assignArbitrator(addr)

Registry admin

Disputed

Assigns an approved arbitrator (method: see decisions, Section 8)

decide(landlordAmt, tenantAmt) | Assigned arbitrator | Disputed | Reverts unless amounts sum to the deposit and landlord amount is within cap; pays both; state Refunded

decide(landlordAmt, tenantAmt)

Assigned arbitrator

Disputed

Reverts unless amounts sum to the deposit and landlord amount is within cap; pays both; state Refunded

Events (the frontend and indexer depend on these): TenancyCreated, LeaseSigned, DepositLocked, EvidenceRecorded(type, hash, by, timestamp), MoveOutStarted(deadline), ClaimRaised(amount), ArbitratorAssigned, DecisionMade(arbitrator, landlordAmount, tenantAmount), Refunded(to, amount), StateChanged(from, to).

Invariants to test (NFR-S-1 to S-4, BR-1 to BR-8): payouts always sum to the deposit; no state with funds lacks a path to Refunded; only legal transitions succeed; lease terms and recorded hashes never change after signing; no function lets one party withdraw the deposit alone.

Security checklist: reentrancy guard on every payout, SafeERC20, role checks on every function, custom errors for clear messages, timestamps used only for windows (not randomness), no upgradeable or admin-withdraw paths, secrets never committed.

5. Backend design

5.1 Modules and classes

Domain classes: User (base) with Tenant, Landlord, Arbitrator; private attributes exposed through properties, with validation.

Services: AuthService, IdentityService (mock), TenancyService, EvidenceService, HashService, KeeperService, ChainClient (web3.py wrapper).

Interfaces: StorageProvider (IPFS, local encrypted), CapPolicy, IdentityProvider (mock now, real provider later).

Layers: routers, services, repositories (SQLAlchemy), chain, storage. Routers contain no business logic.

5.2 REST API (first draft)

Endpoint | Role | Purpose

Endpoint

Role

Purpose

POST /auth/login | Any | Exchange the social-login token for a session JWT; create the user and record the smart-account address

POST /auth/login

Any

Exchange the social-login token for a session JWT; create the user and record the smart-account address

GET /me | Any | Profile, role, verification status

GET /me

Any

Profile, role, verification status

POST /identity/verify | User | Mock verification; on success the backend attests on-chain

POST /identity/verify

User

Mock verification; on success the backend attests on-chain

POST /tenancies/draft | Landlord | Upload lease and terms; returns leaseHash, CID and the parameters for the on-chain createTenancy

POST /tenancies/draft

Landlord

Upload lease and terms; returns leaseHash, CID and the parameters for the on-chain createTenancy

GET /tenancies, GET /tenancies/:id | Parties | Metadata merged with indexer state

GET /tenancies, GET /tenancies/:id

Parties

Metadata merged with indexer state

POST /tenancies/:id/evidence | Parties | Upload files; returns the manifest hash to record on-chain

POST /tenancies/:id/evidence

Parties

Upload files; returns the manifest hash to record on-chain

GET /evidence/:id/verify | Parties, arbitrator | Recompute the hash and compare with the on-chain value (match or mismatch)

GET /evidence/:id/verify

Parties, arbitrator

Recompute the hash and compare with the on-chain value (match or mismatch)

GET /evidence/:id/file | Parties, assigned arbitrator | Access-controlled decrypted download

GET /evidence/:id/file

Parties, assigned arbitrator

Access-controlled decrypted download

GET /arbitrator/disputes (and /:id) | Arbitrator | Assigned disputes with claim, terms and evidence status

GET /arbitrator/disputes (and /:id)

Arbitrator

Assigned disputes with claim, terms and evidence status

POST /faucet | User (testnet only) | Mint MockINR for demos

POST /faucet

User (testnet only)

Mint MockINR for demos

Keeper job: runs on a schedule, finds tenancies whose claim window has passed with no claim, and submits a sponsored finalizeRefund(). It is idempotent and logs every attempt.

Data entities (SRS B.4): User, Tenancy, Evidence, Claim, Decision, and the attestation and arbitrator registry entries. Chain and indexer remain the source of truth for state and funds.

6. Frontend hand-offs (what you publish, and when)

Week | Artifact for the frontend team

Week

Artifact for the frontend team

2 | OpenAPI draft and a mock API server (so screens can be built before the backend exists)

2

OpenAPI draft and a mock API server (so screens can be built before the backend exists)

3 | Contracts package v0.1: TypeChain types, ABIs and addresses.json for Amoy

3

Contracts package v0.1: TypeChain types, ABIs and addresses.json for Amoy

5 | Error-code catalog (contract errors and API errors mapped to plain-language messages)

5

Error-code catalog (contract errors and API errors mapped to plain-language messages)

6 | State and action matrix (below) confirmed; arbitrator endpoints

6

State and action matrix (below) confirmed; arbitrator endpoints

7 | Interface freeze v1.0: ABIs, OpenAPI, subgraph GraphQL schema and endpoint, error catalog

7

Interface freeze v1.0: ABIs, OpenAPI, subgraph GraphQL schema and endpoint, error catalog

8 on | Breaking changes only through a pull request that updates the interface docs, announced to the team

8 on

Breaking changes only through a pull request that updates the interface docs, announced to the team

State and action matrix (each screen shows the current state and the actions available to the current user):

State | Tenant | Landlord | Arbitrator

State

Tenant

Landlord

Arbitrator

Drafted | Review lease, sign | Create, upload lease, sign | None

Drafted

Review lease, sign

Create, upload lease, sign

None

Signed | Lock deposit, add move-in evidence | Add move-in evidence | None

Signed

Lock deposit, add move-in evidence

Add move-in evidence

None

Active | View, add evidence | View, add evidence | None

Active

View, add evidence

View, add evidence

None

MoveOut | Add evidence, view claim window; trigger refund after window | Add evidence, raise capped claim within window | None

MoveOut

Add evidence, view claim window; trigger refund after window

Add evidence, raise capped claim within window

None

Disputed | View claim and evidence | View claim and evidence | Review evidence, decide split

Disputed

View claim and evidence

View claim and evidence

Review evidence, decide split

Refunded | View history | View history | View decision

Refunded

View history

View history

View decision

7. The 12-week plan

Course timeline phases are shown with each week. Sprints are two weeks each (Sprint 1 is Weeks 1 and 2, and so on). Every week ends with a weekly progress report and a short demo to the team. Commit messages carry Jira IDs and every change goes through a reviewed pull request.

Weeks | Focus | Milestone

Weeks

Focus

Milestone

1-2 | Setup, functional modeling, identity, account-abstraction spike | Contract deployed on Amoy; gasless transaction demo (or fallback decided)

1-2

Setup, functional modeling, identity, account-abstraction spike

Contract deployed on Amoy; gasless transaction demo (or fallback decided)

3-4 | Object-oriented analysis, tenancy creation, deposit, evidence, full CI | Tenancy reaches Active on Amoy; CI blocks failing pull requests

3-4

Object-oriented analysis, tenancy creation, deposit, evidence, full CI

Tenancy reaches Active on Amoy; CI blocks failing pull requests

5-6 | Interaction modeling, move-out, claims, refund, arbitration, class design | Happy path and disputed path both work end to end

5-6

Interaction modeling, move-out, claims, refund, arbitration, class design

Happy path and disputed path both work end to end

7-8 | System architecture, indexer, interface freeze, integration | Teammate runs both paths through the UI

7-8

System architecture, indexer, interface freeze, integration

Teammate runs both paths through the UI

9-10 | Security, CI/CD hardening, scenario testing, feature freeze | All scenarios pass on staging

9-10

Security, CI/CD hardening, scenario testing, feature freeze

All scenarios pass on staging

11-12 | Evaluation, deployment, report, demo | Live demo URL; evaluation numbers frozen

11-12

Evaluation, deployment, report, demo

Live demo URL; evaluation numbers frozen

Week 1: Initiation and foundations   (Sprint 1; course Phase 1)

Week 1: Initiation and foundations   (Sprint 1; course Phase 1)

Contracts | Hardhat TypeScript project; OpenZeppelin; MockINR with capped faucet; TenancyState enum and vault skeleton with state guards; first tests for valid and invalid transitions; deploy script to local node and Amoy; wallet and key hygiene (.env, never commit).

Contracts

Hardhat TypeScript project; OpenZeppelin; MockINR with capped faucet; TenancyState enum and vault skeleton with state guards; first tests for valid and invalid transitions; deploy script to local node and Amoy; wallet and key hygiene (.env, never commit).

Backend | FastAPI skeleton with a virtual environment and locked dependencies; PostgreSQL in Docker Compose; SQLAlchemy models and first Alembic migration (users, tenancies); config loader (Pydantic settings); health endpoint; Ruff linting and formatting; Pytest set up.

Backend

FastAPI skeleton with a virtual environment and locked dependencies; PostgreSQL in Docker Compose; SQLAlchemy models and first Alembic migration (users, tenancies); config loader (Pydantic settings); health endpoint; Ruff linting and formatting; Pytest set up.

Frontend and shared | Jira with six sprints and epics; GitHub repository with main and develop, branch protection, pull request template, commit format (TR-12: message); frontend scaffold (React, Vite); agree the API-first workflow.

Frontend and shared

Jira with six sprints and epics; GitHub repository with main and develop, branch protection, pull request template, commit format (TR-12: message); frontend scaffold (React, Vite); agree the API-first workflow.

Docs | Vision document and product backlog (from synopsis and SRS); weekly report 1; decision meeting on the open items in Section 8.

Docs

Vision document and product backlog (from synopsis and SRS); weekly report 1; decision meeting on the open items in Section 8.

Exit criteria | Contract address on Amoy; backend and contracts each have one passing test; open items TBD-1 to TBD-4 decided.

Exit criteria

Contract address on Amoy; backend and contracts each have one passing test; open items TBD-1 to TBD-4 decided.

Week 2: Functional modeling, identity and account abstraction   (Sprint 1; course Phase 1)

Week 2: Functional modeling, identity and account abstraction   (Sprint 1; course Phase 1)

Contracts | IdentityRegistry (attester role, attest, revoke, isVerified) and ArbitratorRegistry (approve, remove, isApproved) with tests. Account-abstraction spike (1 to 2 days): compare bundler and paymaster providers for Amoy support, free testnet sponsorship and social login; build "hello gasless": social login, smart account, sponsored call.

Contracts

IdentityRegistry (attester role, attest, revoke, isVerified) and ArbitratorRegistry (approve, remove, isApproved) with tests. Account-abstraction spike (1 to 2 days): compare bundler and paymaster providers for Amoy support, free testnet sponsorship and social login; build "hello gasless": social login, smart account, sponsored call.

Backend | Auth module (verify social-login token, issue session JWT), /me; mock IdentityService and /identity/verify that attests on-chain through the backend signer; minimal GitHub Actions (lint and tests on pull requests to develop).

Backend

Auth module (verify social-login token, issue session JWT), /me; mock IdentityService and /identity/verify that attests on-chain through the backend signer; minimal GitHub Actions (lint and tests on pull requests to develop).

Frontend and shared | Wireframes for three dashboards; login screen with the chosen SDK; mock API server from your OpenAPI draft.

Frontend and shared

Wireframes for three dashboards; login screen with the chosen SDK; mock API server from your OpenAPI draft.

Docs | Use case diagram and descriptions (UC-1 to UC-8, SRS B.2); map use cases to Jira stories; weekly report 2.

Docs

Use case diagram and descriptions (UC-1 to UC-8, SRS B.2); map use cases to Jira stories; weekly report 2.

Exit criteria | Sponsored transaction works on Amoy, or the fallback (plain signing first) is documented and agreed; a verified user can be attested.

Exit criteria

Sponsored transaction works on Amoy, or the fallback (plain signing first) is documented and agreed; a verified user can be attested.

Week 3: Static analysis; tenancy creation and lease anchoring   (Sprint 2; course Phase 2)

Week 3: Static analysis; tenancy creation and lease anchoring   (Sprint 2; course Phase 2)

Contracts | TenancyFactory with EIP-1167 clones and vault initialize(); createTenancy in Drafted with checks (both verified, cap at most deposit, window in range); sign() by each party, then Signed; immutability after signing; events and custom errors; negative tests (unverified, wrong caller, double sign).

Contracts

TenancyFactory with EIP-1167 clones and vault initialize(); createTenancy in Drafted with checks (both verified, cap at most deposit, window in range); sign() by each party, then Signed; immutability after signing; events and custom errors; negative tests (unverified, wrong caller, double sign).

Backend | StorageProvider interface with LocalEncrypted (AES-256-GCM) and IPFS providers; HashService (keccak256); POST /tenancies/draft (upload, hash, encrypt, store, return parameters); GET /tenancies; lease verification endpoint (FR-2.6).

Backend

StorageProvider interface with LocalEncrypted (AES-256-GCM) and IPFS providers; HashService (keccak256); POST /tenancies/draft (upload, hash, encrypt, store, return parameters); GET /tenancies; lease verification endpoint (FR-2.6).

Frontend and shared | Create-tenancy form and lease review screen against the mock API; publish contracts package v0.1.

Frontend and shared

Create-tenancy form and lease review screen against the mock API; publish contracts package v0.1.

Docs | Object diagram and domain class diagram (SRS B.4 entities); weekly report 3; implementation paper: introduction and methodology outline.

Docs

Object diagram and domain class diagram (SRS B.4 entities); weekly report 3; implementation paper: introduction and methodology outline.

Exit criteria | Drafted to Signed works end to end on Amoy through the API.

Exit criteria

Drafted to Signed works end to end on Amoy through the API.

Week 4: Dynamic analysis; deposit, move-in evidence, full CI   (Sprint 2; course Phase 2)

Week 4: Dynamic analysis; deposit, move-in evidence, full CI   (Sprint 2; course Phase 2)

Contracts | lockDeposit (SafeERC20, tenant only, exact amount, once); recordEvidence for move-in; Signed to Active guard (deposit locked and move-in hash present); batching approve and lock in one user operation if the provider supports it; gas reporter on.

Contracts

lockDeposit (SafeERC20, tenant only, exact amount, once); recordEvidence for move-in; Signed to Active guard (deposit locked and move-in hash present); batching approve and lock in one user operation if the provider supports it; gas reporter on.

Backend | Evidence upload (per-file hash, manifest, manifest hash, encrypted storage, database rows); GET /evidence/:id/verify; access-control middleware (parties only).

Backend

Evidence upload (per-file hash, manifest, manifest hash, encrypted storage, database rows); GET /evidence/:id/verify; access-control middleware (parties only).

CI and shared | Full pipeline: contract tests with coverage and gas report, backend tests, lint, Solhint; required status check on develop; frontend wiring for deposit and evidence upload; weekly report 4.

CI and shared

Full pipeline: contract tests with coverage and gas report, backend tests, lint, Solhint; required status check on develop; frontend wiring for deposit and evidence upload; weekly report 4.

Docs | Activity diagram with swimlanes (tenant, landlord, arbitrator, system) and the state-machine diagram (SRS B.1).

Docs

Activity diagram with swimlanes (tenant, landlord, arbitrator, system) and the state-machine diagram (SRS B.1).

Exit criteria | Tenancy reaches Active on Amoy; a deliberately failing pull request is blocked by CI (keep the screenshot as rubric evidence).

Exit criteria

Tenancy reaches Active on Amoy; a deliberately failing pull request is blocked by CI (keep the screenshot as rubric evidence).

Week 5: Interaction modeling; move-out, claims, automatic refund   (Sprint 3; course Phase 3)

Week 5: Interaction modeling; move-out, claims, automatic refund   (Sprint 3; course Phase 3)

Contracts | startMoveOut (after lease end, with move-out hash) opens the claim window; raiseClaim (landlord, within window, at most cap, evidence present) moves to Disputed; finalizeRefund() for anyone after the window with no claim. Hardhat time-travel tests on every boundary (start, last second, exact deadline).

Contracts

startMoveOut (after lease end, with move-out hash) opens the claim window; raiseClaim (landlord, within window, at most cap, evidence present) moves to Disputed; finalizeRefund() for anyone after the window with no claim. Hardhat time-travel tests on every boundary (start, last second, exact deadline).

Backend | KeeperService scans for elapsed windows and submits sponsored finalizeRefund(), idempotent and logged; claim read endpoints; error-code catalog mapping contract errors to plain messages (FR-7.4).

Backend

KeeperService scans for elapsed windows and submits sponsored finalizeRefund(), idempotent and logged; claim read endpoints; error-code catalog mapping contract errors to plain messages (FR-7.4).

Frontend and shared | Move-out, claim and claim-response screens; status timeline with claim-window countdown (FR-8.5).

Frontend and shared

Move-out, claim and claim-response screens; status timeline with claim-window countdown (FR-8.5).

Docs | Sequence diagrams from real method calls: create and sign; lock deposit and evidence; claim and automatic refund; weekly report 5.

Docs

Sequence diagrams from real method calls: create and sign; lock deposit and evidence; claim and automatic refund; weekly report 5.

Exit criteria | Full happy path (no dispute) passes in tests and on Amoy, including a keeper-triggered refund.

Exit criteria

Full happy path (no dispute) passes in tests and on Amoy, including a keeper-triggered refund.

Week 6: Detailed class design; arbitration   (Sprint 3; course Phase 3)

Week 6: Detailed class design; arbitration   (Sprint 3; course Phase 3)

Contracts | Arbitrator assignment (prototype: registry admin assigns an approved arbitrator); decide() with all validations; payouts with checks-effects-interactions and ReentrancyGuard; optional acceptClaim() for the tenant; design of an arbitrator-inactivity fallback (decision in Section 8); complete negative tests (unauthorized, double decision, wrong sums, over cap).

Contracts

Arbitrator assignment (prototype: registry admin assigns an approved arbitrator); decide() with all validations; payouts with checks-effects-interactions and ReentrancyGuard; optional acceptClaim() for the tenant; design of an arbitrator-inactivity fallback (decision in Section 8); complete negative tests (unauthorized, double decision, wrong sums, over cap).

Backend | Arbitrator endpoints and evidence access for the assigned arbitrator only; hash re-verification in the arbitrator view; admin script to approve arbitrators; refactor to the OO design (User hierarchy, services, CapPolicy strategy).

Backend

Arbitrator endpoints and evidence access for the assigned arbitrator only; hash re-verification in the arbitrator view; admin script to approve arbitrators; refactor to the OO design (User hierarchy, services, CapPolicy strategy).

Frontend and shared | Arbitrator dashboard and decision form.

Frontend and shared

Arbitrator dashboard and decision form.

Docs | Detailed class diagram (contracts and backend) and package diagram (matches the folder structure); weekly report 6; implementation paper: methodology sections.

Docs

Detailed class diagram (contracts and backend) and package diagram (matches the folder structure); weekly report 6; implementation paper: methodology sections.

Exit criteria | Disputed path works end to end locally and on Amoy; a table mapping each pattern (Factory, State, Strategy, Observer) to its code location.

Exit criteria

Disputed path works end to end locally and on Amoy; a table mapping each pattern (Factory, State, Strategy, Observer) to its code location.

Week 7: System architecture; indexer; interface freeze   (Sprint 4; course Phase 3)

Week 7: System architecture; indexer; interface freeze   (Sprint 4; course Phase 3)

Contracts | Verify contracts on the Amoy explorer; finalize events; first gas optimization pass (storage packing, custom errors, clones); paymaster policy allowing only TrustRent contracts and selectors, with per-user limits (FR-7.5).

Contracts

Verify contracts on the Amoy explorer; finalize events; first gas optimization pass (storage packing, custom errors, clones); paymaster policy allowing only TrustRent contracts and selectors, with per-user limits (FR-7.5).

Backend and indexer | Subgraph schema (Tenancy, Evidence, Claim, Decision, Transition), mappings, deploy to Subgraph Studio on Amoy; fallback listener ready if indexing is unreliable; publish interface v1.0 (ABIs, OpenAPI, GraphQL schema, error catalog, state and action matrix).

Backend and indexer

Subgraph schema (Tenancy, Evidence, Claim, Decision, Transition), mappings, deploy to Subgraph Studio on Amoy; fallback listener ready if indexing is unreliable; publish interface v1.0 (ABIs, OpenAPI, GraphQL schema, error catalog, state and action matrix).

Frontend and shared | Dashboards read from indexer and API on staging; remove the mock server.

Frontend and shared

Dashboards read from indexer and API on staging; remove the mock server.

Docs | Component diagram and planned deployment diagram; architecture section of the report; weekly report 7.

Docs

Component diagram and planned deployment diagram; architecture section of the report; weekly report 7.

Exit criteria | Dashboard shows a new on-chain event within about 30 seconds (NFR-P-2).

Exit criteria

Dashboard shows a new on-chain event within about 30 seconds (NFR-P-2).

Week 8: Integration sprint   (Sprint 4; course Phase 4)

Week 8: Integration sprint   (Sprint 4; course Phase 4)

Contracts | Fix integration findings; reproducible deploy script (deploy:amoy writes addresses.json); close review comments.

Contracts

Fix integration findings; reproducible deploy script (deploy:amoy writes addresses.json); close review comments.

Backend | Pydantic validation on every route, rate limiting, security headers, role checks on every route (NFR-SEC-1), audit log, secrets only in environment, migrations; raise Pytest coverage; serve OpenAPI docs.

Backend

Pydantic validation on every route, rate limiting, security headers, role checks on every route (NFR-SEC-1), audit log, secrets only in environment, migrations; raise Pytest coverage; serve OpenAPI docs.

Frontend and shared | Real UI flow with social login and sponsored operations; error and retry states (FR-7.4); code review rotation across the team.

Frontend and shared

Real UI flow with social login and sponsored operations; error and retry states (FR-7.4); code review rotation across the team.

Process | All core-feature stories Done or in final review (guide rule); weekly report 8.

Process

All core-feature stories Done or in final review (guide rule); weekly report 8.

Exit criteria | A teammate (not you) completes one happy tenancy and one disputed tenancy through the UI.

Exit criteria

A teammate (not you) completes one happy tenancy and one disputed tenancy through the UI.

Week 9: Security and CI/CD hardening   (Sprint 5; course Phase 4)

Week 9: Security and CI/CD hardening   (Sprint 5; course Phase 4)

Contracts | Slither pass and fixes; fuzz and invariant tests (payouts sum to deposit, no stuck funds, only legal transitions); checklist review (reentrancy, access control, timestamps, ERC-20 return values); gas optimization pass 2.

Contracts

Slither pass and fixes; fuzz and invariant tests (payouts sum to deposit, no stuck funds, only legal transitions); checklist review (reentrancy, access control, timestamps, ERC-20 return values); gas optimization pass 2.

Backend | FastAPI TestClient integration tests with a local Hardhat node and test database; keeper tests; dependency audit.

Backend

FastAPI TestClient integration tests with a local Hardhat node and test database; keeper tests; dependency audit.

CI/CD | Auto-deploy API to Render and frontend to Vercel from develop (staging); test and coverage reports in the pipeline; build badge in the README; confirm the pipeline blocks merge on failing tests.

CI/CD

Auto-deploy API to Render and frontend to Vercel from develop (staging); test and coverage reports in the pipeline; build badge in the README; confirm the pipeline blocks merge on failing tests.

Docs | README (setup, environment variables, run, test, deploy); weekly report 9; implementation paper: implementation section.

Docs

README (setup, environment variables, run, test, deploy); weekly report 9; implementation paper: implementation section.

Exit criteria | Green pipeline from a clean clone; security checklist completed and recorded.

Exit criteria

Green pipeline from a clean clone; security checklist completed and recorded.

Week 10: Scenario testing; feature freeze   (Sprint 5; course Phase 4)

Week 10: Scenario testing; feature freeze   (Sprint 5; course Phase 4)

Scenarios | S1 happy refund via keeper; S2 claim then arbitrator decision; S3 cap violation; S4 unauthorized caller; S5 claim outside window; S6 tampered evidence shows hash mismatch; S7 unverified user blocked. Scripted so they can be rerun.

Scenarios

S1 happy refund via keeper; S2 claim then arbitrator decision; S3 cap violation; S4 unauthorized caller; S5 claim outside window; S6 tampered evidence shows hash mismatch; S7 unverified user blocked. Scripted so they can be rerun.

Backend and contracts | Fix findings; resolve remaining open items and record them in SRS v1.1 change log; basic concurrency check for a few simultaneous tenancies (NFR-P-4).

Backend and contracts

Fix findings; resolve remaining open items and record them in SRS v1.1 change log; basic concurrency check for a few simultaneous tenancies (NFR-P-4).

Frontend and shared | UX polish, in-app help text, user guide with screenshots.

Frontend and shared

UX polish, in-app help text, user guide with screenshots.

Process | Feature freeze at the end of the week; Jira: every story Done or explicitly deferred; weekly report 10.

Process

Feature freeze at the end of the week; Jira: every story Done or explicitly deferred; weekly report 10.

Exit criteria | All seven scenarios pass on staging Amoy.

Exit criteria

All seven scenarios pass on staging Amoy.

Week 11: Testing and evaluation   (Sprint 6; course Phase 5)

Week 11: Testing and evaluation   (Sprint 6; course Phase 5)

Contracts | Final gas table per function (create, sign, lock, evidence, claim, decide, refund) and clones versus full deployment; coverage report; list of negative tests.

Contracts

Final gas table per function (create, sign, lock, evidence, claim, decide, refund) and clones versus full deployment; coverage report; list of negative tests.

Backend | API latency (median and 95th percentile), event-to-dashboard latency, coverage report; fix-only changes from now on.

Backend

API latency (median and 95th percentile), event-to-dashboard latency, coverage report; fix-only changes from now on.

Docs | Testing chapter; implementation paper: experiments and results with screenshots; weekly report 11.

Docs

Testing chapter; implementation paper: experiments and results with screenshots; weekly report 11.

Exit criteria | Evaluation numbers frozen and reproducible with one command.

Exit criteria

Evaluation numbers frozen and reproducible with one command.

Week 12: Deployment, final review and demo   (Sprint 6; course Phase 5)

Week 12: Deployment, final review and demo   (Sprint 6; course Phase 5)

All | Final deployment to Amoy with verified contracts and production environment; final deployment diagram matches what is live; README final; live demo URL; demo rehearsal including a fallback (pre-seeded tenancy and a recorded video); handover.

All

Final deployment to Amoy with verified contracts and production environment; final deployment diagram matches what is live; README final; live demo URL; demo rehearsal including a fallback (pre-seeded tenancy and a recorded video); handover.

Docs | Final report compiled; final weekly report signed off by the project guide; both papers finalized.

Docs

Final report compiled; final weekly report signed off by the project guide; both papers finalized.

Exit criteria | Full demo from the live URL, from lease signing to refund, including a disputed case.

Exit criteria

Full demo from the live URL, from lease signing to refund, including a disputed case.

8. Open items from the SRS, with proposed defaults

These are proposals for the team and guide to confirm, not decisions. Decide TBD-1 to TBD-4 in Week 1, the rest by Week 6.

Item | Question | Proposed default

Item

Question

Proposed default

TBD-1 | Claim window length | 7 days default; lease may set between 3 and 30 days

TBD-1

Claim window length

7 days default; lease may set between 3 and 30 days

TBD-2 | Cap: hard legal limit or lease parameter? | Contract enforces cap at most the deposit; the backend warns (soft) if deposit exceeds two months' rent

TBD-2

Cap: hard legal limit or lease parameter?

Contract enforces cap at most the deposit; the backend warns (soft) if deposit exceeds two months' rent

TBD-3 | Can the tenant accept a claim directly? | Yes: acceptClaim() in Disputed settles immediately; otherwise the arbitrator decides

TBD-3

Can the tenant accept a claim directly?

Yes: acceptClaim() in Disputed settles immediately; otherwise the arbitrator decides

TBD-4 | How is an arbitrator assigned? | Registry admin assigns from approved arbitrators in the prototype; random or agreed assignment as future work

TBD-4

How is an arbitrator assigned?

Registry admin assigns from approved arbitrators in the prototype; random or agreed assignment as future work

TBD-5 | Arbitrator fees | None in the prototype; list as future work

TBD-5

Arbitrator fees

None in the prototype; list as future work

TBD-6 | Mock identity fields | Name, phone, ID type and a fake ID number; rule-based result with a short delay; attestation is a hash of user id and timestamp

TBD-6

Mock identity fields

Name, phone, ID type and a fake ID number; rule-based result with a short delay; attestation is a hash of user id and timestamp

TBD-7 | Hash and evidence format | keccak256 and a JSON manifest; images and PDF up to 10 MB each

TBD-7

Hash and evidence format

keccak256 and a JSON manifest; images and PDF up to 10 MB each

TBD-8 | Token lifetime, sponsorship limits | 1 hour access token with refresh; paymaster allowlist of TrustRent contracts and a daily per-user limit

TBD-8

Token lifetime, sponsorship limits

1 hour access token with refresh; paymaster allowlist of TrustRent contracts and a daily per-user limit

TBD-9 | Quantitative targets | Contract coverage at least 90%, backend at least 70%; API 95th percentile within 3 s; event latency within 30 s

TBD-9

Quantitative targets

Contract coverage at least 90%, backend at least 70%; API 95th percentile within 3 s; event latency within 30 s

TBD-10 | Data protection | Data minimization, encrypted storage, no personal data on-chain; legal review is out of scope

TBD-10

Data protection

Data minimization, encrypted storage, no personal data on-chain; legal review is out of scope

TBD-11 | Arbitrator inaction, early termination | Fallback after a long timeout (for example 30 days) returns the full deposit to the tenant; early termination and extension out of scope

TBD-11

Arbitrator inaction, early termination

Fallback after a long timeout (for example 30 days) returns the full deposit to the tenant; early termination and extension out of scope

9. Testing and evaluation plan

Contracts (Hardhat): unit tests for every transition and guard, negative tests for NFR-SEC-5, time-travel tests for window boundaries, invariant tests, gas report per function.

Backend (Pytest and FastAPI TestClient): unit tests for services and hashing, integration tests against a local Hardhat node and a test database, keeper tests.

End to end: the seven scripted scenarios in Week 10, run on staging Amoy.

Evaluation results for the implementation paper: gas cost per operation, coverage, API and event latency, and one complete tenancy including a dispute.

10. Risks and fallbacks

Risk | Mitigation

Risk

Mitigation

Account abstraction takes longer than planned | Do the Week 2 spike early. Candidate providers include Pimlico, Alchemy, Particle, ZeroDev and Biconomy. Check each for Amoy support, free testnet sponsorship and a social-login option before choosing; I did not verify these terms. Fallback: build and demo with plain signing, and add sponsorship when ready.

Account abstraction takes longer than planned

Do the Week 2 spike early. Candidate providers include Pimlico, Alchemy, Particle, ZeroDev and Biconomy. Check each for Amoy support, free testnet sponsorship and a social-login option before choosing; I did not verify these terms. Fallback: build and demo with plain signing, and add sponsorship when ready.

Indexer unreliable or delayed on Amoy | The Graph's Polygon documentation lists Amoy as supported, but publishing to the network involves extra steps. Keep the Python event-listener fallback ready in Week 7.

Indexer unreliable or delayed on Amoy

The Graph's Polygon documentation lists Amoy as supported, but publishing to the network involves extra steps. Keep the Python event-listener fallback ready in Week 7.

Free-tier limits (RPC, hosting, pinning) | Cache reads in PostgreSQL, keep a local Hardhat setup for development, and deploy to Amoy only at milestones.

Free-tier limits (RPC, hosting, pinning)

Cache reads in PostgreSQL, keep a local Hardhat setup for development, and deploy to Amoy only at milestones.

Automatic refund needs a transaction | Keeper job plus a user-triggered fallback button; anyone may call finalizeRefund().

Automatic refund needs a transaction

Keeper job plus a user-triggered fallback button; anyone may call finalizeRefund().

Key management | Separate keys for deployer, attester and paymaster; only in environment configuration; rotate if exposed.

Key management

Separate keys for deployer, attester and paymaster; only in environment configuration; rotate if exposed.

Interface drift between teams | Freeze interface in Week 7; changes only through pull requests that update the interface docs.

Interface drift between teams

Freeze interface in Week 7; changes only through pull requests that update the interface docs.

Diagrams drift from code | Review diagrams against code at the end of each sprint; update diagrams in the same pull request as structural changes.

Diagrams drift from code

Review diagrams against code at the end of each sprint; update diagrams in the same pull request as structural changes.

Late discovery of a design flaw | Two end-to-end paths run by Week 6 and integration in Weeks 7 and 8, leaving time to fix before the freeze.

Late discovery of a design flaw

Two end-to-end paths run by Week 6 and integration in Weeks 7 and 8, leaving time to fix before the freeze.

11. If time is short: priority order

Build in this order and cut from the bottom:

1. Vault, state machine and tests (the core of the project).

2. Evidence hashing, claims, automatic refund and arbitrator decision.

3. Backend: authentication, mock identity, hashing and encrypted storage.

4. Indexer for live dashboards (use the Python listener if needed).

5. Gasless, wallet-free onboarding (SRS marks it High, so agree any cut with your guide).