Software Requirements Specification

for

TrustRent

A Blockchain-Based Security Deposit Escrow and Verified Tenancy System for the Indian Rental Market

Version 1.0 approved

Prepared by

Aniket Parmar, Akhil Antony, Sameer Ajay Chauhan, Vansh Rana

Under the guidance of Prof. Jagrati Nagdiya

Department of Computer Science & Engineering

Shri Vaishnav Institute of Information Technology

Shri Vaishnav Vidyapeeth Vishwavidyalaya, Indore

October 21, 2026

Table of Contents

1. Introduction1

1.1 Purpose1

1.2 Document Conventions1

1.3 Intended Audience and Reading Suggestions1

1.4 Product Scope1

1.5 References1

2. Overall Description1

2.1 Product Perspective1

2.2 Product Functions1

2.3 User Classes and Characteristics1

2.4 Operating Environment1

2.5 Design and Implementation Constraints1

2.6 User Documentation1

2.7 Assumptions and Dependencies1

3. External Interface Requirements1

3.1 User Interfaces1

3.2 Hardware Interfaces1

3.3 Software Interfaces1

3.4 Communications Interfaces1

4. System Features1

4.1 User Registration and Identity Verification1

4.2 Tenancy Creation and Lease Anchoring1

4.3 Deposit Vault and Activation1

4.4 Condition Evidence Management1

4.5 Move-Out, Claim and Automatic Refund1

4.6 Dispute Resolution by Arbitrator1

4.7 Wallet-Free, Gasless Onboarding1

4.8 Dashboards and Event Indexing1

5. Other Nonfunctional Requirements1

5.1 Performance Requirements1

5.2 Safety Requirements1

5.3 Security Requirements1

5.4 Software Quality Attributes1

5.5 Business Rules1

6. Other Requirements1

Appendix A: Glossary1

Appendix B: Analysis Models1

Appendix C: To Be Determined List1

Revision History

Name | Date | Reason For Changes | Version

Name

Date

Reason For Changes

Version

TrustRent project team | October 21, 2026 | Initial SRS prepared from the project synopsis, review paper and project overview | 1.0

TrustRent project team

October 21, 2026

Initial SRS prepared from the project synopsis, review paper and project overview

1.0

1. Introduction

1.1 Purpose

This Software Requirements Specification (SRS) describes the requirements of TrustRent, release 1.0 (testnet prototype): a blockchain-based security deposit escrow and verified tenancy system for the Indian residential rental market. It covers the whole prototype: the smart contracts (vault, factory and registry contracts), the Node.js backend, the React web application, the indexer, and the off-chain storage and identity components.

The document is written for the B.Tech major project (Jul–Dec 2026) in the Department of Computer Science & Engineering, SVIIT, SVVV Indore. It defines what the system must do and the constraints it must respect; design and implementation choices beyond those constraints are left to the design documents.

1.2 Document Conventions

Functional requirements are identified as FR-<feature>.<n> (for example FR-5.2). Non-functional requirements use NFR-<area>-<n>, and business rules use BR-<n>.

The words “shall” and “must” mark mandatory requirements; “should” marks desirable ones. Each requirement carries its own priority only where it differs from the priority of its feature.

Feature priorities are High, Medium or Low. High means the feature is required for the end-to-end demonstration of one tenancy from lease signing to refund.

Items that are not yet decided are marked TBD and collected in Appendix C.

Tenancy states are written in capitalised form (Drafted, Signed, Active, MoveOut, Disputed, Refunded).

1.3 Intended Audience and Reading Suggestions

Reader | What to read

Reader

What to read

Project guide and evaluators | Sections 1 and 2 for scope and context, then Section 4 and Appendix B for what will be demonstrated.

Project guide and evaluators

Sections 1 and 2 for scope and context, then Section 4 and Appendix B for what will be demonstrated.

Developers (contract, backend, frontend) | Section 2.5 for constraints, Section 3 for interfaces, Section 4 for detailed requirements, Section 5 for quality targets.

Developers (contract, backend, frontend)

Section 2.5 for constraints, Section 3 for interfaces, Section 4 for detailed requirements, Section 5 for quality targets.

Testers | Section 4 (each FR is written to be verifiable), Section 5 and Appendix B.

Testers

Section 4 (each FR is written to be verifiable), Section 5 and Appendix B.

Documentation writers | Sections 1, 2.3 and 2.6 and Appendix A.

Documentation writers

Sections 1, 2.3 and 2.6 and Appendix A.

Section 2 gives the overall description, Section 3 the external interfaces, Section 4 the system features with detailed functional requirements, Section 5 the non-functional requirements and business rules, and Section 6 other requirements. Appendices contain the glossary, analysis models and the To Be Determined list.

1.4 Product Scope

In the Indian rental market the security deposit, often several months’ rent, is usually held by the landlord alone. There is no neutral custody, no tamper-proof record of the lease or the property’s condition, and no affordable way to contest deductions. TrustRent places the deposit in a smart-contract vault that neither party controls alone and releases it by rules both parties sign at the start of the tenancy.

Objectives of the product:

Hold the deposit in a vault contract with an automatic refund if the landlord raises no claim within an agreed window, capped deductions, and arbitrator resolution of disputed claims.

Implement the tenancy lifecycle (Drafted, Signed, Active, MoveOut, Disputed, Refunded), emitting an event for every transition.

Anchor hashes of the signed lease and of timestamped move-in and move-out evidence on-chain while the files stay off-chain.

Verify landlord and tenant identity before a vault opens, without placing personal data on-chain.

Provide wallet-free, gasless onboarding through social login and ERC-4337 account abstraction.

Provide dashboards for tenants, landlords and arbitrators, kept current by an indexer.

Evaluate the prototype on gas cost, test coverage and an end-to-end tenancy including a dispute.

In scope: deposit escrow, lease anchoring, identity verification, evidence trail, dispute flow and testnet deployment. Out of scope for this phase: property listings and search, monthly rent collection, real-money bank escrow integration, and mobile apps. Possible later extensions are rent collection, regulated bank escrow through UPI and machine-learning comparison of move-in and move-out photos.

1.5 References

[1] TrustRent Major Project Synopsis, Dept. of CSE, SVIIT, SVVV Indore, Jul–Dec 2026.

[2] Security Deposits in Blockchain-Based Rental Systems: A Review, Comparative Analysis, and Research Gap (project review paper), J. Nagdiya, A. Parmar, A. Antony, S. A. Chauhan, V. Rana.

[3] TrustRent: A Blockchain-Based Security Deposit Escrow and Verified Tenancy System for the Indian Rental Market (project overview document), Sep. 18, 2026.

[4] Ministry of Housing and Urban Affairs, Government of India, “The Model Tenancy Act, 2021.” https://prsindia.org/billtrack/the-model-tenancy-act-2021

[5] V. Buterin et al., “ERC-4337: Account abstraction using alt mempool,” Ethereum Improvement Proposals, Sep. 2021. https://eips.ethereum.org/EIPS/eip-4337

[6] Q.-L. Chen, R.-H. Ye and F.-L. Lin, “A blockchain-based housing rental system,” Proc. CTISC, 2019, pp. 184–190.

[7] A. Kibet, M. M. Thiga and S. M. Karume, “Towards a blockchain based smart contracts model design for housing market applications,” Int. J. Adv. Res. Comput. Eng. Technol., vol. 8, no. 8, 2019.

[8] C. Lesaege, F. Ast and W. George, “Kleros short paper v1.0.7,” Sep. 2019. https://kleros.io/assets/whitepaper.pdf

[9] IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications; SRS template of SVIIT.

2. Overall Description

2.1 Product Perspective

TrustRent is a new, self-contained product. It is not a replacement for an existing system, but it addresses a gap left by Indian rental platforms such as listing portals, managed and co-living operators, zero-deposit financing products and rent payment apps, which digitise listings, agreements and rent payments, or finance the deposit, while leaving custody of the money with one party. Academic blockchain rental systems reviewed in the project’s review paper either do not model the deposit lifecycle or do not limit deductions, record condition evidence or target India.

The system has six cooperating components:

Component | Role

Component

Role

Smart contracts (Solidity, Polygon Amoy) | A factory contract creates one vault contract per tenancy; registry contracts hold identity attestations and approved arbitrators. The vault implements the tenancy state machine, deposit custody, cap, auto-refund and arbitration outcome.

Smart contracts (Solidity, Polygon Amoy)

A factory contract creates one vault contract per tenancy; registry contracts hold identity attestations and approved arbitrators. The vault implements the tenancy state machine, deposit custody, cap, auto-refund and arbitration outcome.

Backend (Node.js, Express, PostgreSQL) | Social-login authentication, mock identity verification service, file hashing and storage, and read endpoints.

Backend (Node.js, Express, PostgreSQL)

Social-login authentication, mock identity verification service, file hashing and storage, and read endpoints.

Frontend (React, ethers.js) | Tenant, landlord and arbitrator dashboards.

Frontend (React, ethers.js)

Tenant, landlord and arbitrator dashboards.

Account abstraction layer (ERC-4337) | Smart accounts and sponsored (gasless) transactions so users never handle a wallet or pay gas.

Account abstraction layer (ERC-4337)

Smart accounts and sponsored (gasless) transactions so users never handle a wallet or pay gas.

Indexer (The Graph) | Reads contract events and serves current tenancy status to the dashboards.

Indexer (The Graph)

Reads contract events and serves current tenancy status to the dashboards.

Off-chain storage (IPFS via pinning service, behind a storage interface) | Encrypted lease and evidence files; only hashes are anchored on-chain.

Off-chain storage (IPFS via pinning service, behind a storage interface)

Encrypted lease and evidence files; only hashes are anchored on-chain.

The prototype uses a mock rupee (INR) token on a test network. A production version would hold rupees in regulated bank escrow, with the contract issuing release instructions; this is outside the current scope.

2.2 Product Functions

Register users through social login and verify landlord and tenant identity (attestation recorded on-chain, personal data kept off-chain).

Create a tenancy in the Drafted state, with lease terms including deposit amount, deposit cap and claim window, and anchor the lease hash.

Sign the lease by both verified parties, moving the tenancy to Signed.

Lock the deposit in the vault and hash move-in evidence, moving the tenancy to Active.

Record move-out evidence and open the claim window at lease end (MoveOut).

Refund the full deposit automatically if the landlord raises no claim within the window.

Allow the landlord to raise a capped claim that references the hashed evidence (Disputed).

Let an arbitrator review the on-chain evidence and decide the split (Refunded).

Emit an event for every state transition and display live status on role-specific dashboards.

2.3 User Classes and Characteristics

User class | Characteristics | Main functions used

User class

Characteristics

Main functions used

Tenant (primary) | Students and young professionals who relocate often; no blockchain knowledge; uses a normal web browser. | Verify identity, sign lease, pay deposit, upload move-in evidence, view status, receive refund, respond to a claim.

Tenant (primary)

Students and young professionals who relocate often; no blockchain knowledge; uses a normal web browser.

Verify identity, sign lease, pay deposit, upload move-in evidence, view status, receive refund, respond to a claim.

Landlord (primary) | Property owner; limited technical expertise; wants proof for genuine damage claims. | Verify identity, create tenancy, sign lease, upload evidence, raise a claim within the cap.

Landlord (primary)

Property owner; limited technical expertise; wants proof for genuine damage claims.

Verify identity, create tenancy, sign lease, upload evidence, raise a claim within the cap.

Arbitrator (secondary) | Approved neutral party registered in the arbitrator registry; reviews evidence. | View disputed tenancies and evidence, decide the split.

Arbitrator (secondary)

Approved neutral party registered in the arbitrator registry; reviews evidence.

View disputed tenancies and evidence, decide the split.

Administrator (secondary) | Project team or operator who maintains registries. | Approve arbitrators and maintain registry contents (details TBD).

Administrator (secondary)

Project team or operator who maintains registries.

Approve arbitrators and maintain registry contents (details TBD).

2.4 Operating Environment

Users: any current desktop or mobile web browser; no wallet extension required.

Blockchain: Polygon Amoy test network, EVM-compatible; Solidity 0.8.x contracts using OpenZeppelin libraries.

Backend: Node.js with Express and PostgreSQL, hosted on a free-tier cloud service (Render).

Frontend: React application hosted on Vercel.

Indexing and storage: The Graph for event indexing; IPFS through a pinning service for off-chain files.

Development: computer with at least 8 GB RAM and an internet connection; Hardhat, Jest, Git, Jira and GitHub Actions.

2.5 Design and Implementation Constraints

The prototype runs on a test network with a mock INR token; no real money or cryptocurrency is handled.

Large files and personal data must not be stored on-chain; only hashes or attestations may be recorded.

Files must be stored in encrypted form behind a storage interface so that providers can be swapped.

Users must not be required to hold a wallet or pay gas fees (ERC-4337 account abstraction and social login).

The design shall apply object-oriented principles: a User base class with Tenant, Landlord and Arbitrator subclasses, encapsulated attributes, and the Factory, State, Strategy and Observer patterns.

Development shall follow UML modelling, Jira sprints, Git feature branches with pull requests, and a GitHub Actions pipeline that runs tests on every pull request.

The project relies on free-tier services to keep cost close to zero; their limits constrain throughput and storage.

The Model Tenancy Act, 2021 is a model law that states adopt individually; the cap on deductions is therefore a lease parameter rather than a hard-coded legal rule (see Appendix C).

2.6 User Documentation

UML documentation (use case, class, sequence and state diagrams) and this SRS.

A short user guide for tenants, landlords and arbitrators, with in-app help text on each dashboard.

A README covering setup, deployment and test instructions, and a live demo URL.

A review paper and an implementation paper.

2.7 Assumptions and Dependencies

Polygon Amoy, the ERC-4337 bundler and paymaster services, social-login provider, The Graph hosted or studio service, IPFS pinning service, Vercel and Render remain available during development and demonstration.

Identity verification is provided by a mock service in this phase; a real Indian identity verification provider is assumed for any production version.

Both parties have internet access and a social-login account.

An approved arbitrator is available in the registry for every disputed case.

The tenancy parties agree on the deposit amount, cap and claim window before signing, and the cap does not exceed what applicable law permits (two months’ rent under the Model Tenancy Act, 2021, where adopted).

A production version would depend on a regulated bank escrow via UPI.

3. External Interface Requirements

3.1 User Interfaces

The web application shall provide three role-based dashboards with a common layout and navigation. No wallet or gas prompts shall be displayed.

Common: social login page, profile and identity verification status, tenancy list, notifications, help link and consistent error messages in plain language.

Tenant dashboard: tenancy status timeline, lease review and signing, deposit payment, move-in and move-out evidence upload, claim view and response, refund status.

Landlord dashboard: create tenancy form (lease terms, deposit, cap, claim window), lease signing, evidence upload, claim form referencing the evidence, tenancy status.

Arbitrator dashboard: list of disputed tenancies, evidence viewer with hash verification status, decision form for the split.

Each screen shall show the current tenancy state and the actions available to the current user in that state.

Detailed screen designs will be documented separately in the UI specification.

3.2 Hardware Interfaces

TrustRent has no direct hardware interface. Users access it through standard devices with a browser; evidence photos are uploaded from the device’s file system or camera through the browser’s file-upload facility.

3.3 Software Interfaces

Interface | Purpose | Data exchanged

Interface

Purpose

Data exchanged

Polygon Amoy via ethers.js | Deploy and call the factory, vault and registry contracts | Transactions, contract calls and emitted events

Polygon Amoy via ethers.js

Deploy and call the factory, vault and registry contracts

Transactions, contract calls and emitted events

ERC-4337 bundler / paymaster [5] | Gasless user operations from smart accounts | User operations, sponsorship data

ERC-4337 bundler / paymaster [5]

Gasless user operations from smart accounts

User operations, sponsorship data

Social-login provider | Authentication without a wallet | Identity token, account identifier

Social-login provider

Authentication without a wallet

Identity token, account identifier

Identity verification service (mock) | Verify landlord and tenant identity | Verification request and result; attestation hash

Identity verification service (mock)

Verify landlord and tenant identity

Verification request and result; attestation hash

IPFS pinning service via storage interface | Store encrypted lease and evidence files | Encrypted file, content identifier (CID)

IPFS pinning service via storage interface

Store encrypted lease and evidence files

Encrypted file, content identifier (CID)

The Graph | Index contract events for dashboards | Event logs in, queried tenancy status out

The Graph

Index contract events for dashboards

Event logs in, queried tenancy status out

PostgreSQL | Off-chain data (users, metadata, file references) | Relational records

PostgreSQL

Off-chain data (users, metadata, file references)

Relational records

Backend REST API (Express) | Frontend access to auth, hashing, storage and reads | JSON over HTTPS

Backend REST API (Express)

Frontend access to auth, hashing, storage and reads

JSON over HTTPS

Mock INR token (ERC-20 style) | Stand-in for rupees on testnet | Token balances and transfers

Mock INR token (ERC-20 style)

Stand-in for rupees on testnet

Token balances and transfers

3.4 Communications Interfaces

All browser-to-backend and backend-to-service traffic shall use HTTPS; the API shall exchange JSON.

Blockchain communication shall use JSON-RPC to Polygon Amoy nodes; the frontend shall query the indexer over GraphQL.

Authentication tokens shall be sent in the Authorization header and expire after a configured period (TBD).

The frontend shall refresh tenancy status from the indexer on a regular basis or on event, without requiring chain polling by the browser.

4. System Features

Functional requirements are organised by feature, following the lifecycle of one tenancy.

4.1 User Registration and Identity Verification

4.1.1 Description and Priority

Users sign in with social login and are verified as landlord or tenant before they can take part in a tenancy. Verification results are recorded on-chain only as an attestation, with personal data kept off-chain.

Priority: High

4.1.2 Stimulus/Response Sequences

User signs in with social login → system creates the user account and a smart account without showing a wallet.

User submits identity details → mock identity service verifies → backend records an attestation in the identity registry → dashboard shows “Verified”.

Unverified user tries to join or sign a tenancy → system blocks the action and prompts verification.

4.1.3 Functional Requirements

FR-1.1The system shall authenticate users through social login and assign each user exactly one role per tenancy (Tenant or Landlord); the Arbitrator role is assigned only through the arbitrator registry.

FR-1.2The system shall provide an identity verification flow backed by a mock verification service in this phase.

FR-1.3On successful verification the system shall record an identity attestation (hash or flag, no personal data) in the identity registry contract.

FR-1.4The system shall store personal identity data only off-chain, in encrypted form where stored.

FR-1.5The system shall reject a request to create or sign a tenancy from an account without a valid attestation, and shall display the reason.

FR-1.6The system shall allow only approved arbitrators, listed in the arbitrator registry, to decide disputes.

4.2 Tenancy Creation and Lease Anchoring

4.2.1 Description and Priority

The landlord creates a tenancy with its lease terms. The factory contract creates a vault for the tenancy, and the hash of the lease is anchored on-chain so that the lease cannot be silently altered. The tenancy begins in Drafted and moves to Signed when both verified parties sign.

Priority: High

4.2.2 Stimulus/Response Sequences

Landlord enters tenant, deposit, cap, claim window and lease dates and uploads the lease → system hashes the file, stores it encrypted off-chain, and the factory creates a vault in Drafted.

Tenant reviews the lease → each party signs → when both are verified and have signed the state changes to Signed and an event is emitted.

4.2.3 Functional Requirements

FR-2.1The factory contract shall create one vault contract per tenancy.

FR-2.2A tenancy shall record at least: landlord, tenant, deposit amount, deduction cap, claim window in days, lease start and end dates, and lease hash.

FR-2.3The system shall compute the hash of the lease document and anchor it in the vault; the lease file shall be stored off-chain.

FR-2.4The system shall allow the tenancy to move from Drafted to Signed only after both parties are verified and both have signed.

FR-2.5The system shall make the lease hash and terms immutable once the tenancy is Signed.

FR-2.6The system shall let any party verify a downloaded lease file against the anchored hash.

FR-2.7The system shall emit an event on every state transition.

4.3 Deposit Vault and Activation

4.3.1 Description and Priority

The tenant locks the deposit in the vault, and move-in evidence is hashed. The tenancy then becomes Active. Neither party can withdraw the deposit unilaterally.

Priority: High

4.3.2 Stimulus/Response Sequences

Tenant pays the deposit (mock INR token) → vault locks the amount.

Move-in evidence is submitted and hashed → when both deposit and move-in evidence hash are recorded the state changes to Active.

4.3.3 Functional Requirements

FR-3.1The vault shall accept the deposit only from the tenant of that tenancy and only for the agreed amount.

FR-3.2The vault shall hold the deposit and shall not allow either party to withdraw it directly.

FR-3.3The vault shall move from Signed to Active only after the deposit is locked and the move-in evidence hash is recorded.

FR-3.4The system shall prevent a second deposit payment for the same tenancy.

FR-3.5The system shall show both parties the locked amount and the vault state at all times.

FR-3.6In the prototype the deposit shall be denominated in a mock INR token on the test network.

4.4 Condition Evidence Management

4.4.1 Description and Priority

Timestamped move-in and move-out evidence (photos and notes) is hashed and anchored on-chain, creating a baseline for any later damage claim. Files stay off-chain, encrypted.

Priority: High

4.4.2 Stimulus/Response Sequences

Party uploads evidence files → backend hashes each file (and a manifest), stores them encrypted off-chain → evidence hash and timestamp are recorded on-chain.

Any party or the arbitrator opens evidence → system recomputes the hash and shows whether it matches the anchored value.

4.4.3 Functional Requirements

FR-4.1The system shall allow the landlord and tenant to submit move-in evidence while the tenancy is Signed, and move-out evidence at the end of the lease.

FR-4.2The system shall hash the evidence and record the hash with a timestamp on-chain, tied to the tenancy and the type (move-in or move-out).

FR-4.3The system shall store evidence files encrypted off-chain behind a swappable storage interface, and shall store only references and hashes in the database and on-chain.

FR-4.4The system shall show a “hash match / mismatch” result whenever evidence is viewed.

FR-4.5The system shall not allow recorded evidence hashes to be modified or removed.

FR-4.6The system shall restrict access to evidence files to the parties of the tenancy and, when disputed, the assigned arbitrator.

4.5 Move-Out, Claim and Automatic Refund

4.5.1 Description and Priority

At the end of the lease the move-out evidence is hashed and a claim window opens. If the landlord does not raise a claim in that window, the full deposit returns to the tenant automatically. If the landlord raises a claim, it must reference the evidence and respect the cap.

Priority: High

4.5.2 Stimulus/Response Sequences

Lease ends → move-out evidence is hashed → state changes to MoveOut and the claim window starts.

No claim within N days → vault returns the full deposit to the tenant → state Refunded.

Landlord raises a claim with amount and evidence reference → system validates cap → state Disputed.

4.5.3 Functional Requirements

FR-5.1The system shall move the tenancy from Active to MoveOut only after the lease end date and after the move-out evidence hash is recorded.

FR-5.2The vault shall start a claim window of N days (set in the lease) when the tenancy enters MoveOut.

FR-5.3If no claim is raised within the window, the vault shall allow the full deposit to be returned to the tenant and shall set the state to Refunded, without any action required from the landlord.

FR-5.4Only the landlord of the tenancy may raise a claim, and only during the claim window.

FR-5.5A claim shall state the amount and reference the hashed move-in and move-out evidence.

FR-5.6The vault shall reject any claim amount that exceeds the cap written into the lease and shall return a clear error message.

FR-5.7A valid claim shall move the tenancy to Disputed and shall not release funds until resolved (whether the tenant may accept a claim directly is TBD).

4.6 Dispute Resolution by Arbitrator

4.6.1 Description and Priority

A disputed claim is decided by an approved arbitrator who reviews the on-chain evidence and decides how the deposit is split. This offers an affordable alternative to rent tribunals and civil courts for small deposits.

Priority: High

4.6.2 Stimulus/Response Sequences

Tenancy enters Disputed → arbitrator is assigned → arbitrator opens the claim and evidence.

Arbitrator submits a split (amount to landlord, remainder to tenant) → vault pays out → state Refunded.

4.6.3 Functional Requirements

FR-6.1The system shall assign an arbitrator from the arbitrator registry to each disputed tenancy (assignment method TBD).

FR-6.2The arbitrator shall be able to view the claim, the lease terms, the anchored hashes and the evidence files with hash verification status.

FR-6.3The arbitrator shall submit a decision stating the amount for the landlord and the amount for the tenant, which together shall equal the deposit.

FR-6.4The vault shall reject a decision where the landlord’s amount exceeds the cap or the amounts do not sum to the deposit.

FR-6.5On a valid decision the vault shall pay out both amounts and move the tenancy to Refunded.

FR-6.6Only the assigned arbitrator may submit the decision, and a decision shall be final in the prototype (appeals are out of scope).

FR-6.7The system shall record the decision and the arbitrator’s address in an event.

4.7 Wallet-Free, Gasless Onboarding

4.7.1 Description and Priority

Users interact through a normal web app. Social login and ERC-4337 account abstraction create smart accounts and sponsor gas so users never handle a wallet or pay fees.

Priority: High

4.7.2 Stimulus/Response Sequences

User signs in with social login → system creates (or retrieves) the user’s smart account.

User performs an action (sign, pay, claim, decide) → frontend sends a user operation → bundler and paymaster submit it with gas sponsored.

4.7.3 Functional Requirements

FR-7.1The system shall create a smart account for each user on first login without requiring a wallet installation or seed phrase.

FR-7.2The system shall submit all user actions as ERC-4337 user operations with gas sponsored by the platform paymaster.

FR-7.3The system shall not show gas fees, wallet prompts or blockchain jargon to end users.

FR-7.4The system shall show an understandable message and allow retry if a sponsored transaction fails.

FR-7.5The system shall limit sponsorship to TrustRent contract calls (limits TBD) to prevent misuse.

4.8 Dashboards and Event Indexing

4.8.1 Description and Priority

Role-specific dashboards present live tenancy status. An indexer reads contract events so the dashboards show real-time status without polling the chain directly.

Priority: High

4.8.2 Stimulus/Response Sequences

Contract emits an event → indexer updates its store → dashboard shows the new state and available actions.

User opens the dashboard → frontend queries the indexer and backend → tenancy list and timelines are displayed.

4.8.3 Functional Requirements

FR-8.1The indexer shall subscribe to the events of the factory, vault and registry contracts and store tenancy state, evidence hashes, claims and decisions.

FR-8.2The dashboards shall display, per tenancy, the current state, locked amount, key dates, claim window deadline, cap, evidence status and history of transitions.

FR-8.3The tenant, landlord and arbitrator dashboards shall each show only the data and actions relevant to that role.

FR-8.4The dashboard shall reflect a new on-chain event within the time given in NFR-P-2.

FR-8.5The system shall show the remaining claim window in the MoveOut state.

5. Other Nonfunctional Requirements

5.1 Performance Requirements

Targets below are proposed for the prototype and will be confirmed during evaluation (see Appendix C).

NFR-P-1Typical page loads and read API calls shall complete within 3 seconds under normal load on a free-tier deployment.

NFR-P-2The dashboard shall show a new on-chain event within about 30 seconds of block confirmation on the test network.

NFR-P-3The gas cost of each contract function (create tenancy, sign, lock deposit, record evidence, claim, decide, refund) shall be measured and reported; vault deployment through the factory shall be optimised for low gas.

NFR-P-4The prototype shall support the concurrent use needed for the demonstration (at least a few simultaneous tenancies and users).

5.2 Safety Requirements

NFR-S-1Funds shall never be released except through the rules coded in the vault; no single party and no backend component shall be able to withdraw the deposit arbitrarily.

NFR-S-2No deposit shall be locked permanently: every state with funds shall have a defined path to Refunded (auto-refund or arbitrator decision).

NFR-S-3The prototype shall clearly state that it runs on a test network with mock tokens and shall not accept real money.

NFR-S-4Rounding and arithmetic in payouts shall use checked arithmetic so that the sum of payouts always equals the deposit.

5.3 Security Requirements

NFR-SEC-1Role-based access control shall be enforced both in the contracts (only authorised addresses may call a function in a given state) and in the backend API.

NFR-SEC-2Personal data and evidence files shall be stored off-chain and encrypted; only hashes or attestations shall be placed on-chain.

NFR-SEC-3All network traffic shall use HTTPS; secrets and keys (paymaster, backend signer) shall be kept in environment configuration and never committed to the repository.

NFR-SEC-4Contracts shall use audited OpenZeppelin components where applicable and shall protect against reentrancy and unauthorised state transitions.

NFR-SEC-5Contract code shall be covered by automated tests including negative tests for unauthorised callers, invalid transitions, cap violations and timeouts.

NFR-SEC-6The system shall limit access to evidence to the tenancy parties and the assigned arbitrator, and shall comply with the principle of data minimisation (applicable Indian data protection requirements are TBD).

5.4 Software Quality Attributes

Attribute | Requirement

Attribute

Requirement

Usability | A first-time tenant or landlord shall be able to complete the sign, deposit and evidence steps without understanding blockchain; the UI shall show plain-language status and next actions.

Usability

A first-time tenant or landlord shall be able to complete the sign, deposit and evidence steps without understanding blockchain; the UI shall show plain-language status and next actions.

Reliability / Availability | Contract behaviour shall be deterministic; the web application and indexer shall be available during demonstrations (best-effort on free tiers).

Reliability / Availability

Contract behaviour shall be deterministic; the web application and indexer shall be available during demonstrations (best-effort on free tiers).

Correctness | Every state transition shall follow the state machine in Appendix B; invalid transitions shall revert.

Correctness

Every state transition shall follow the state machine in Appendix B; invalid transitions shall revert.

Auditability | Every transition, claim, evidence hash and decision shall be traceable through emitted events.

Auditability

Every transition, claim, evidence hash and decision shall be traceable through emitted events.

Maintainability | Contracts, backend and frontend shall be modular; the storage provider shall be replaceable through an interface; code shall follow OOP principles and the named design patterns.

Maintainability

Contracts, backend and frontend shall be modular; the storage provider shall be replaceable through an interface; code shall follow OOP principles and the named design patterns.

Testability | Contract tests (Hardhat) and backend tests (Jest) shall run in the CI pipeline on every pull request; test coverage shall be measured and reported (target TBD).

Testability

Contract tests (Hardhat) and backend tests (Jest) shall run in the CI pipeline on every pull request; test coverage shall be measured and reported (target TBD).

Portability | The web application shall run in current major browsers; contracts shall be EVM-compatible.

Portability

The web application shall run in current major browsers; contracts shall be EVM-compatible.

Interoperability | Evidence and lease hashes shall use a documented hash function so they can be independently verified.

Interoperability

Evidence and lease hashes shall use a documented hash function so they can be independently verified.

5.5 Business Rules

BR-1The deposit is held in the vault; neither the landlord nor the tenant can control it alone.

BR-2A vault opens only after both landlord and tenant are identity-verified.

BR-3A tenancy becomes Signed only when both parties sign the anchored lease, and Active only after the deposit is locked and move-in evidence is hashed.

BR-4Only the landlord may raise a claim, only during the claim window, and the claim may not exceed the cap written into the lease.

BR-5If no claim is raised within the window, the full deposit returns to the tenant automatically.

BR-6A claim must reference the hashed move-in and move-out evidence.

BR-7Only an approved arbitrator assigned to the tenancy may decide a dispute, and the payouts must sum to the deposit.

BR-8Lease terms and anchored hashes cannot change after signing.

6. Other Requirements

Database: PostgreSQL shall store users, tenancy metadata, file references and verification status; the on-chain data and indexer remain the source of truth for state and funds.

Legal: the Model Tenancy Act, 2021 recommends a two-month cap on residential deposits and digital tenancy records; the system shall allow the cap to be set per lease and recommend the legal limit (see Appendix C). Legal status of on-chain agreements and electronic signatures in India is outside this prototype’s scope.

Internationalisation: the prototype shall use English and amounts in Indian rupees; additional languages are future work.

Reuse: components shall be reusable for variants such as paying guest and hostel stays and commercial leases with different caps.

Deliverables: testnet prototype, deployed and tested contracts, dashboards, CI/CD pipeline, UML documentation, live demo URL, review paper and implementation paper.

Evaluation: gas cost per operation, test coverage, and one end-to-end tenancy from signing to refund including a disputed case.

Appendix A: Glossary

Term | Definition

Term

Definition

Blockchain | Distributed ledger that records transactions in a tamper-evident chain of blocks.

Blockchain

Distributed ledger that records transactions in a tamper-evident chain of blocks.

Smart contract | Program on a blockchain that executes agreed terms automatically when conditions are met.

Smart contract

Program on a blockchain that executes agreed terms automatically when conditions are met.

Vault | The per-tenancy smart contract that holds the security deposit.

Vault

The per-tenancy smart contract that holds the security deposit.

Factory contract | Contract that creates a vault for each tenancy.

Factory contract

Contract that creates a vault for each tenancy.

Registry contract | Contract that stores identity attestations or the list of approved arbitrators.

Registry contract

Contract that stores identity attestations or the list of approved arbitrators.

Security deposit | Money paid by the tenant before move-in, refundable at the end of the tenancy subject to deductions.

Security deposit

Money paid by the tenant before move-in, refundable at the end of the tenancy subject to deductions.

Cap | Maximum amount that may be deducted, written into the lease.

Cap

Maximum amount that may be deducted, written into the lease.

Claim window | Number of days after move-out in which the landlord may raise a claim.

Claim window

Number of days after move-out in which the landlord may raise a claim.

Arbitrator | Approved neutral party who decides disputed claims.

Arbitrator

Approved neutral party who decides disputed claims.

Evidence hash | Cryptographic hash of a lease or evidence file, anchored on-chain with a timestamp.

Evidence hash

Cryptographic hash of a lease or evidence file, anchored on-chain with a timestamp.

IPFS | InterPlanetary File System; decentralised file storage used for off-chain files.

IPFS

InterPlanetary File System; decentralised file storage used for off-chain files.

ERC-4337 | Ethereum standard for account abstraction using an alternative mempool.

ERC-4337

Ethereum standard for account abstraction using an alternative mempool.

Account abstraction | Use of smart-contract accounts so users do not need a conventional wallet.

Account abstraction

Use of smart-contract accounts so users do not need a conventional wallet.

Bundler / Paymaster | ERC-4337 services that submit user operations and sponsor their gas fees.

Bundler / Paymaster

ERC-4337 services that submit user operations and sponsor their gas fees.

Gas | Fee for executing a transaction on a blockchain.

Gas

Fee for executing a transaction on a blockchain.

Polygon Amoy | Polygon test network used for the prototype.

Polygon Amoy

Polygon test network used for the prototype.

The Graph | Indexing protocol that reads contract events and serves queryable data.

The Graph

Indexing protocol that reads contract events and serves queryable data.

Model Tenancy Act, 2021 | Indian model law recommending a two-month cap on residential deposits.

Model Tenancy Act, 2021

Indian model law recommending a two-month cap on residential deposits.

SRS | Software Requirements Specification.

SRS

Software Requirements Specification.

UPI | Unified Payments Interface, Indian instant payment system.

UPI

Unified Payments Interface, Indian instant payment system.

TBD | To be determined.

TBD

To be determined.

Appendix B: Analysis Models

B.1 Tenancy State-Transition Model

From | To | Trigger | Guard / action

From

To

Trigger

Guard / action

(start) | Drafted | Landlord creates tenancy | Factory creates vault; lease hash anchored

(start)

Drafted

Landlord creates tenancy

Factory creates vault; lease hash anchored

Drafted | Signed | Both parties sign | Both identity-verified

Drafted

Signed

Both parties sign

Both identity-verified

Signed | Active | Deposit locked | Move-in evidence hashed

Signed

Active

Deposit locked

Move-in evidence hashed

Active | MoveOut | Lease ends | Move-out evidence hashed; claim window starts

Active

MoveOut

Lease ends

Move-out evidence hashed; claim window starts

MoveOut | Refunded | No claim within N days | Full deposit returned to tenant

MoveOut

Refunded

No claim within N days

Full deposit returned to tenant

MoveOut | Disputed | Landlord raises claim | Amount ≤ cap; references evidence

MoveOut

Disputed

Landlord raises claim

Amount ≤ cap; references evidence

Disputed | Refunded | Arbitrator decides split | Payouts sum to deposit; landlord amount ≤ cap

Disputed

Refunded

Arbitrator decides split

Payouts sum to deposit; landlord amount ≤ cap

B.2 Main Use Cases

ID | Actor | Use case

ID

Actor

Use case

UC-1 | Tenant, Landlord | Sign in and verify identity

UC-1

Tenant, Landlord

Sign in and verify identity

UC-2 | Landlord | Create tenancy and upload lease

UC-2

Landlord

Create tenancy and upload lease

UC-3 | Tenant, Landlord | Sign lease

UC-3

Tenant, Landlord

Sign lease

UC-4 | Tenant | Lock deposit

UC-4

Tenant

Lock deposit

UC-5 | Tenant, Landlord | Submit move-in and move-out evidence

UC-5

Tenant, Landlord

Submit move-in and move-out evidence

UC-6 | Landlord | Raise claim within the cap

UC-6

Landlord

Raise claim within the cap

UC-7 | Arbitrator | Review evidence and decide split

UC-7

Arbitrator

Review evidence and decide split

UC-8 | All roles | View tenancy status and history on dashboard

UC-8

All roles

View tenancy status and history on dashboard

B.3 Class Structure (summary)

User (base class) with subclasses Tenant, Landlord and Arbitrator; attributes are encapsulated and exposed through methods.

Factory pattern: TenancyFactory creates Vault instances.

State pattern: the Vault behaviour depends on its tenancy state (Drafted, Signed, Active, MoveOut, Disputed, Refunded).

Strategy pattern: interchangeable policies such as the storage provider and the deduction/cap check.

Observer pattern: events emitted by contracts are observed by the indexer and the dashboards.

B.4 Principal Data Entities

Entity | Key attributes

Entity

Key attributes

User | id, social-login id, role(s), verification status, smart account address

User

id, social-login id, role(s), verification status, smart account address

Tenancy | id, vault address, landlord, tenant, deposit, cap, claim window, start/end dates, lease hash, state

Tenancy

id, vault address, landlord, tenant, deposit, cap, claim window, start/end dates, lease hash, state

Evidence | id, tenancy id, type (move-in/move-out), hash, timestamp, storage reference (CID)

Evidence

id, tenancy id, type (move-in/move-out), hash, timestamp, storage reference (CID)

Claim | tenancy id, amount, evidence references, raised at

Claim

tenancy id, amount, evidence references, raised at

Decision | tenancy id, arbitrator, landlord amount, tenant amount, timestamp

Decision

tenancy id, arbitrator, landlord amount, tenant amount, timestamp

Attestation / Arbitrator registry entry | address, verified flag or approval flag, timestamp

Attestation / Arbitrator registry entry

address, verified flag or approval flag, timestamp

Appendix C: To Be Determined List

No. | Open item

No.

Open item

TBD-1 | Default and maximum value of the claim window (N days) and whether the lease may set it freely.

TBD-1

Default and maximum value of the claim window (N days) and whether the lease may set it freely.

TBD-2 | Whether the deduction cap is enforced as a hard legal limit (two months’ rent) or is a lease parameter validated only against the agreed deposit.

TBD-2

Whether the deduction cap is enforced as a hard legal limit (two months’ rent) or is a lease parameter validated only against the agreed deposit.

TBD-3 | Whether the tenant may accept the landlord’s claim directly (skipping arbitration) or every claim goes to the arbitrator, and whether the tenant must respond within a time limit.

TBD-3

Whether the tenant may accept the landlord’s claim directly (skipping arbitration) or every claim goes to the arbitrator, and whether the tenant must respond within a time limit.

TBD-4 | How an arbitrator is assigned (random, by landlord/tenant agreement, or by an administrator) and how arbitrators are approved.

TBD-4

How an arbitrator is assigned (random, by landlord/tenant agreement, or by an administrator) and how arbitrators are approved.

TBD-5 | Arbitrator fees or incentives, if any, and who pays them.

TBD-5

Arbitrator fees or incentives, if any, and who pays them.

TBD-6 | Choice of identity verification method and data fields for the mock service; later production provider.

TBD-6

Choice of identity verification method and data fields for the mock service; later production provider.

TBD-7 | Hash function and evidence manifest format, file types and size limits for evidence uploads.

TBD-7

Hash function and evidence manifest format, file types and size limits for evidence uploads.

TBD-8 | Authentication token lifetime and sponsorship limits for the paymaster.

TBD-8

Authentication token lifetime and sponsorship limits for the paymaster.

TBD-9 | Quantitative targets for response time, event latency and test coverage (NFR-P-1, NFR-P-2, NFR-SEC-5).

TBD-9

Quantitative targets for response time, event latency and test coverage (NFR-P-1, NFR-P-2, NFR-SEC-5).

TBD-10 | Applicable Indian data protection requirements for stored identity data and evidence.

TBD-10

Applicable Indian data protection requirements for stored identity data and evidence.

TBD-11 | Handling of early termination, lease extension and arbitrator inaction (no decision within a time limit).

TBD-11

Handling of early termination, lease extension and arbitrator inaction (no decision within a time limit).