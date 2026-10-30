# TrustRent

> **A Blockchain-Based Security Deposit Escrow and Verified Tenancy System for the Indian Rental Market**
> Major Project (BTCS706N), T, Shri Vaishnav Vidyapeeth Vishwavidyalaya, Indore.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.24-363636.svg?style=flat&logo=solidity)](https://soliditylang.org/)
[![Polygon Amoy](https://img.shields.io/badge/Polygon-Amoy%20Testnet-8247E5.svg?style=flat&logo=polygon)](https://polygon.technology/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000.svg?style=flat&logo=nextdotjs)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org/)

---

## 📖 Key Documentation
- **[Project Charter](PROJECT_CHARTER.md)**: Problem statement, objectives, team roles, and boundaries.
- **[System Architecture](ARCHITECTURE.md)**: Component topology, smart contract state machine, off-chain storage & encryption.
- **[12-Week Roadmap](ROADMAP.md)**: Sprint timeline, deliverables, and course milestones.
- **[Product Backlog](BACKLOG.md)**: Jira-style epics, user stories, and acceptance criteria.
- **[SRS & Academic Docs](Docs/)**: Original SRS v1.0, Project Synopsis, and course implementation plan.

---

## 🏗 Repository Layout

```text
TrustRent/
├── contracts/               # Hardhat, Solidity 0.8.x, OpenZeppelin contracts & tests
│   ├── contracts/           # DepositVault, TenancyFactory, Registries, MockINR
│   ├── scripts/             # Deployment and verification scripts
│   └── test/                # Unit tests for state machines & security invariants
├── backend/                 # Python 3.12+ FastAPI asynchronous REST backend
│   ├── app/
│   │   ├── api/v1/          # auth, identity, tenancies, evidence, arbitrator, faucet (v1.0)
│   │   │                    # accounts, listings, owner, messages (v1.1, web app)
│   │   ├── core/            # Config, security, database engine
│   │   ├── models/          # SQLAlchemy 2.0 ORM models
│   │   ├── services/        # Hashing, encryption, ledger, email, seed data
│   │   └── data/            # Sample listings (Indore: Vijay Nagar, Pipliyahana)
│   └── tests/               # Pytest async test suite
├── frontend/                # Next.js 16 + React 19 + TypeScript + Tailwind 4 web app
│   └── src/
│       ├── app/             # Pages: auth, search, listings, messages, HomePref AI (coming soon),
│       │                    # premium, owner dashboard, deposits, admin console
│       ├── components/      # UI components
│       └── lib/             # API client, auth, listings, owner, messages, sync cache
├── subgraph/                # The Graph indexer schema & mappings
├── Docs/                    # SRS, Synopsis, plan, frozen hand-off interfaces
│   └── hand_off/            # openapi.json, ABIs, MARKETPLACE_API.md
├── docker-compose.yml       # Local PostgreSQL database
└── .env.example             # Unified environment variables template
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Node.js** v20+ · **Python** v3.12+ · **Git** · **Docker** (optional, for PostgreSQL)

### 2. Configure environment
```bash
cp .env.example .env                       # backend (SQLite works without Docker:
                                           #   DATABASE_URL=sqlite+aiosqlite:///./trustrent.db)
cp frontend/.env.example frontend/.env.local
```

### 3. Backend (port 8000)
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows
source venv/bin/activate         # Linux / Mac
pip install -r requirements.txt
pytest                           # 21 tests
uvicorn app.main:app --reload --port 8000
```
API docs are at http://localhost:8000/docs. On first start the backend creates the tables and loads the sample homes in Vijay Nagar and Pipliyahana, Indore.

### 4. Frontend (port 3000)
```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```
If `NEXT_PUBLIC_API_URL` is empty, the frontend runs in **demo mode** with everything kept in the browser, which is handy when the backend isn't running.

### 5. Smart contracts
```bash
cd contracts
npm install
npx hardhat compile
npx hardhat test
```

### Demo walkthrough
See [frontend/README.md](frontend/README.md#demo-walkthrough-for-the-viva). In short:
1. Sign up as **looking for a home** → search `Indore` or `452010` → open a home → **Request a visit**. The sample owner accepts on its own.
2. Try a home marked **New · Premium only** → get Premium (ID check + demo payment) → contact the owner.
3. Sign up as **renting out my home** → verify (ID + property document) → approve on the demo review desk → **Add listing** with photos and a map pin.
4. Sign in as the seeker again, request a visit to the new home → as the owner, accept it in **Messages**.
5. Pay the **deposit** on a home after your visit is confirmed: you get a receipt (deposit ID + hash). At move-out the owner proposes any deduction in **Deposits**, the tenant accepts or disputes, and anyone can check a receipt on **Look up deposit**.
6. Sign in as the demo admin (**admin** / **admin12345**): a separate **admin console** with Overview, Users (ban, unban, delete), Listings (unlist, relist), Messages (read-only), Deposits & receipts (three sample receipts and the linked receipt chain), Premium (members, payments, revoke) and Verifications (documents, approve/reject, **Download Excel register**).

> **Demo mode is on** (`DEMO_MODE=True`): demo checkout, self-approval for owners, auto-approved IDs, demo admin. Real verification emails (Gmail), Razorpay payments, hosted PostgreSQL and S3/R2 storage switch on when their keys are set; see **[Docs/GO_LIVE.md](Docs/GO_LIVE.md)**, then set `DEMO_MODE=False`.

---

## 👥 Authors & Supervision
- **Team**: Aniket Parmar, Akhil Antony, Sameer Ajay Chauhan, Vansh Rana

