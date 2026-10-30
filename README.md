# TrustRent

A blockchain-based security deposit escrow and verified tenancy system for the Indian rental market.

# Table of Contents

1. [Overview](#overview)
2. [Screenshots](#screenshots)
3. [Features](#features)
4. [How Deposit Receipts Work](#how-deposit-receipts-work)
5. [Technology Stack](#technology-stack)
6. [Repository Structure](#repository-structure)
7. [Getting Started](#getting-started)
8. [Configuration](#configuration)
9. [Demo Mode and Sample Data](#demo-mode-and-sample-data)
10. [Running Tests](#running-tests)
11. [Deployment](#deployment)
12. [Documentation](#documentation)
13. [Team](#team)
14. [License](#license)

# Overview

Renting a home in India usually means paying a security deposit of two to ten months of rent directly to the landlord. At move-out, deductions are often decided by one side alone, records are kept on paper or in chat messages, and tenants have little proof of what was paid or agreed.

TrustRent addresses this in three ways:

- **Verified people.** Every renter and owner confirms their email at sign-up. Owners submit identity and property documents, which an admin reviews before any home goes live.
- **Tamper-proof deposit receipts.** Each deposit and each settlement is recorded as a cryptographic fingerprint in a hash-chained ledger, and optionally on the Polygon blockchain. Anyone can later check that the amount and details have not been changed.
- **A fair settlement process.** The owner proposes a deduction with a reason, the tenant accepts or disputes it, and disputed cases are settled by an admin. Every step is added to the receipt chain.

# Screenshots

Screenshots are stored in `Docs/screenshots`.

# Sign in

![Sign in](Docs/screenshots/sign-in.png)

# Sign up with email verification

![Sign up](Docs/screenshots/sign-up.png)

# Search homes

![Search](Docs/screenshots/search.png)

# Search results

![Search results](Docs/screenshots/search-results.png)

# Listing details

![Listing details](Docs/screenshots/listing.png)

# Messages and visit booking

![Messages](Docs/screenshots/messages.png)

# Deposits

![Deposits](Docs/screenshots/deposits.png)

# Owner dashboard

![Owner dashboard](Docs/screenshots/owner-dashboard.png)

# Premium

![Premium](Docs/screenshots/premium.png)

# Admin console overview

![Admin overview](Docs/screenshots/admin-overview.png)

# Admin deposits and receipt chain

![Admin deposits](Docs/screenshots/admin-deposits.png)

# Admin users

![Admin users](Docs/screenshots/admin-users.png)

## Features

# For people looking for a home

- Sign up with email verification (a six-digit code sent by email) or sign in with Google.
- Search homes by city, area or pin code, with filters for rent, bedrooms, furnishing, facilities and preferred tenants.
- View listing details, photos, the deposit amount and the owner's deposit track record.
- Message owners and book visits. The exact address is shown only after a visit is confirmed.
- Upload an identity document to become a verified user.
- Pay the security deposit and receive a deposit receipt.
- Accept or dispute a settlement proposed by the owner at move-out.
- Look up any receipt by deposit ID or receipt hash.

# For owners

- Apply for owner verification with an identity document and a property document.
- Add listings with photos, rent, deposit, facilities and availability.
- Pause, resume or delete listings.
- Reply to messages and accept or decline visit requests.
- Propose a deposit settlement with the deduction and the reason.

# Premium

- Weekly, monthly and quarterly plans.
- Premium members can contact owners of new listings during the first 48 hours, before everyone else.
- New listings still appear in everyone's search results, marked as Premium only until the early access period ends.

# Admin console

- Overview of users, listings, deposits, messages and Premium revenue.
- Review owner and identity documents, approve or reject them, and download the verification register as an Excel file.
- Ban, unban or delete user accounts. Deleting removes personal details and documents but keeps financial records.
- Unlist or relist any home with a reason that the owner can see.
- Read conversations between renters and owners for safety checks and disputes.
- View Premium members, plans and payments, and revoke Premium.
- View all deposits and the full receipt chain, settle disputed deposits and mark owner payouts.
- Generate a deposit receipt for a deposit paid outside the app, for example by bank transfer, UPI or cheque.

# How Deposit Receipts Work

1. **Payment.** The tenant pays the deposit through the payment gateway (Razorpay), or an admin records a deposit that was paid outside the app.
2. **Fingerprint.** The deposit details (deposit ID, home, tenant, owner, amount, time and payment reference) are hashed with Keccak-256. Only this fingerprint is recorded. Names and personal data are never written to the chain.
3. **Linked block.** The fingerprint is stored as a new block that also contains the hash of the previous block. Changing any earlier record breaks every link after it.
4. **On-chain copy.** When the DepositRegistry contract is configured, the receipt is also written to the Polygon Amoy network.
5. **Verification.** The receipt lookup page recomputes the fingerprint from the stored details and compares it with the receipt. Any change shows as a mismatch.
6. **Settlement.** At move-out, the agreed deduction and refund are recorded as a second block linked to the same deposit.

# Technology Stack

| Layer | Technology |

| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic |
| Database | SQLite for local development, PostgreSQL in production |
| Blockchain | Solidity 0.8.24, Hardhat, OpenZeppelin, Polygon Amoy, web3.py |
| Authentication | JWT, scrypt password hashing, email verification over SMTP, Google sign-in |
| Payments | Razorpay (demo checkout available for development) |
| File storage | AES-256-GCM encrypted documents on local disk or S3 compatible storage |
| Indexing | The Graph subgraph |
| Testing | Pytest, Hardhat with Mocha and Chai, ESLint, Ruff |

# Repository Structure

| Path | Contents |

| `frontend/` | Next.js web application |
| `frontend/src/app/` | Pages for sign in, sign up, search, listings, messages, deposits, premium, owner and admin |
| `frontend/src/components/` | Shared interface components |
| `frontend/src/lib/` | API client, authentication, listings, messages and deposits |
| `backend/` | FastAPI service |
| `backend/app/api/v1/` | REST endpoints |
| `backend/app/models/` | Database models |
| `backend/app/services/` | Ledger, chain client, email, payments, storage, seed data |
| `backend/tests/` | Backend test suite |
| `contracts/` | Solidity contracts, deployment scripts and tests |
| `subgraph/` | The Graph schema and mappings |
| `scripts/` | Evaluation and hand-off generation scripts |
| `Docs/` | SRS, synopsis, implementation plan, go-live guide and API reference |

## Getting Started

# Prerequisites

- Node.js 20 or later
- Python 3.12
- Git

# 1. Clone the repository

```bash
git clone https://github.com/RANAV2004/TrustRent.git
cd TrustRent
```

# 2. Create the environment file

Copy `.env.example` to `.env` in the project root and fill in the values you need. See [Configuration](#configuration).

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

macOS and Linux:

```bash
cp .env.example .env
```

# 3. Start the backend

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

macOS and Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://localhost:8000`, and the interactive API documentation is at `http://localhost:8000/docs`. On startup the backend prints whether email verification is configured.

# 4. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

On Windows, use `Copy-Item .env.example .env.local` instead of `cp`.

Open `http://localhost:3000` in a browser.

# 5. Deploy the contracts (optional)

The application works without a blockchain connection by using the built-in hash-chained ledger. To also write receipts to Polygon Amoy:

```bash
cd contracts
npm install
npx hardhat run scripts/deploy-deposit-registry.ts --network amoy
```

Then set `DEPOSIT_REGISTRY_ADDRESS` and `CHAIN_SIGNER_PRIVATE_KEY` in `.env`.

## Configuration

The backend reads `.env` from the project root or from the `backend` folder. The most important settings are listed below. The full list is in `.env.example`.

| Setting | Purpose |
|---|---|
| `DATABASE_URL` | SQLite by default. Paste a hosted PostgreSQL URL for production. |
| `JWT_SECRET` | Secret used to sign login tokens. Use a long random value in production. |
| `DEMO_MODE` | Enables demo checkout, automatic ID approval and the demo admin account. Set to `False` in production. |
| `SEED_SAMPLE_LISTINGS` | Loads the sample Indore homes, tenants and deposit receipts. |
| `ADMIN_EMAILS` | Accounts with these emails can open the admin console. |
| `SMTP_USER`, `SMTP_APP_PASSWORD` | Gmail address and app password used to send sign-up verification codes. Sign-up is paused without them. |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Live payments. Without them, payments use the demo checkout in demo mode. |
| `STORAGE_PROVIDER` | `local` or `s3` for encrypted document storage. |
| `DEPOSIT_REGISTRY_ADDRESS`, `CHAIN_SIGNER_PRIVATE_KEY` | Write deposit receipts to the Polygon contract. |

The frontend reads `frontend/.env.local`. Set `NEXT_PUBLIC_API_URL` to `http://localhost:8000/api/v1`.

Never commit `.env` or `.env.local`. Both are listed in `.gitignore`.

# Demo Mode and Sample Data

With `DEMO_MODE=True` and `SEED_SAMPLE_LISTINGS=True`, the backend creates:

- Six sample homes in Vijay Nagar and Pipliyahana, Indore.
- Sample owners who reply automatically to messages.
- Three sample tenants, two of them with Premium.
- Three deposit receipts: one held, one with a settlement proposed and one settled.
- An admin account with the username `admin`. Its password is the `DEMO_ADMIN_PASSWORD` value in your `.env` file.
  Turn both settings off before going live.

## Running Tests

Backend:

```bash
cd backend
pytest
```

Smart contracts:

```bash
cd contracts
npx hardhat test
```

Frontend checks:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

## Deployment

Step-by-step instructions for hosted PostgreSQL, encrypted file storage, Razorpay, Gmail SMTP, contract deployment, admin accounts and hosting are in [Docs/GO_LIVE.md](Docs/GO_LIVE.md).

## Documentation

| Document | Description |
|---|---|
| [Project Charter](PROJECT_CHARTER.md) | Problem statement, objectives, scope and team roles |
| [Architecture](ARCHITECTURE.md) | System components and contract design |
| [Roadmap](ROADMAP.md) | Timeline and milestones |
| [Backlog](BACKLOG.md) | Epics and user stories |
| [Software Requirements Specification](Docs/TrustRent_SRS.md) | Functional and non-functional requirements |
| [Synopsis](Docs/Synopsis.md) | Project synopsis |
| [Go-Live Guide](Docs/GO_LIVE.md) | Production setup |
| [Marketplace API](Docs/hand_off/MARKETPLACE_API.md) | Web application endpoints |
| [OpenAPI Specification](Docs/hand_off/openapi.json) | Full API schema |

## Team

| Name | Role |
|---|---|
| Aniket Parmar | Team member |
| Akhil Antony | Team member |
| Sameer Ajay Chauhan | Team member |
| Vansh Rana | Team member |


## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.