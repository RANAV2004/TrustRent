# TrustRent: Project Charter

**A Blockchain-Based Security Deposit Escrow and Verified Tenancy System for the Indian Rental Market**

---

## 1. Project Overview & Problem Statement
In the Indian urban rental market, security deposits (typically 2 to 10 months of rent) are held unilaterally by landlords with zero neutral custody, tamper-prone records of property condition, and prohibitively expensive legal recourse for dispute resolution. 

This leads to:
1. **Arbitrary Deductions & Delayed Refunds:** Tenants routinely face delayed refunds or arbitrary deductions under the guise of "wear and tear".
2. **Lack of Verifiable Move-In/Move-Out Evidence:** Landlords lack indisputable, timestamped proof of pre-existing vs. tenant-caused damages.
3. **High Friction in Small Claims:** Disputing a ₹30,000–₹1,00,000 deduction in civil court takes years and costs more than the deposit itself.

**TrustRent** solves this by establishing:
- A smart-contract deposit escrow on Polygon Amoy EVM test network.
- Cryptographically anchored leases and dual-party signed condition evidence (keccak256 hashes of timestamped photos/videos).
- Deterministic tenancy state transitions (Drafted → Signed → Active → MoveOut → Disputed/Refunded).
- Automatic refund via autonomous keeper execution if no dispute is raised within a defined window.
- Fast, low-cost decentralized or appointed arbitration for disputed deductions with an enforced lease cap.
- Gasless, wallet-free UX via Account Abstraction (ERC-4337) and social login.

---

## 2. Project Identification & Team
- **Institution:** Shri Vaishnav Institute of Information Technology (T), Shri Vaishnav Vidyapeeth Vishwavidyalaya, Indore
- **Course Code:** BTCS706N (Major Project)
- **Project Guide:** Prof. Jagrati Nagdiya
- **Team Members:**
  - Aniket Parmar [23100BTCSAII14270]
  - Akhil Antony [23100BTCSAII14262]
  - Sameer Ajay Chauhan [23100BTCSAII14319]
  - Vansh Rana [22100BTCSAII11065]

---

## 3. Core Objectives & Success Metrics
1. **Objective 1 - Trustless Escrow:** Deposit locked in smart contract vault, withdrawable only via mutual agreement, passed timeout, or arbitrator ruling.
2. **Objective 2 - Tamper-Proof Evidence:** Hashes stored on-chain with AES-256-GCM encrypted media stored off-chain (IPFS/local encrypted store).
3. **Objective 3 - Enforced Deduction Caps:** Smart contract enforces that landlord claims cannot exceed the lease-agreed maximum damage cap (or deposit limit).
4. **Objective 4 - Seamless Onboarding:** Web2 social login abstraction so non-crypto native users do not need to manage private keys or pay gas fees.
5. **Success Metrics:**
   - Contract test coverage >= 90%.
   - Backend test coverage >= 70%.
   - API p95 response time < 3s.
   - 100% automated refund reliability upon claim timeout.

---

## 4. Key Constraints & Non-Goals
- **Testnet Scope:** Polygon Amoy test network using MockINR ERC-20 tokens (no real fiat INR directly on-chain).
- **Mock Identity:** Verification is simulated via a rule-based identity service issuing on-chain attestations without exposing PII on-chain.
- **Data Minimization:** No personal data (names, phone numbers, raw lease text) is stored in smart contracts; only hashes and attestation signatures.
