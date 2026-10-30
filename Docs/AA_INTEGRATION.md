# ERC-4337 Account Abstraction Integration & Spike Report

**Date:** October 27, 2026  
**Status:** Spike Completed / Architecture Frozen  
**Target Network:** Polygon Amoy Testnet (Chain ID 80002)

---

## 1. Executive Summary & Objective

In accordance with **SRS FR-7.1–FR-7.5**, TrustRent provides a completely wallet-free, gasless experience for tenants, landlords, and arbitrators. End users log in via standard social authentication (e.g. Google/Email), receive a deterministic smart contract account, and sign actions without paying MATIC/POL gas fees or managing private keys.

---

## 2. Provider Spike & Evaluation Matrix

We evaluated leading ERC-4337 infrastructure providers on the following criteria:
1. **Polygon Amoy Support:** Stable Bundler and Verifying Paymaster RPC endpoints.
2. **Social Login / Embedded Signer Integration:** Native compatibility with passkeys/social login (e.g. Web3Auth / Privy / Turnkey / Dynamic).
3. **Free Testnet Sponsorship:** Availability of developer sponsorship quotas on Amoy.
4. **Batched Transactions:** Support for multi-call user operations (e.g. ERC-20 `approve` + `lockDeposit` in a single transaction).

| Provider | Polygon Amoy Support | Paymaster Sponsorship Policy | Social Login SDK | Verdict |
|---|---|---|---|---|
| **Pimlico (alto + permissionless.js)** | ✅ Excellent (Native Amoy Bundler & Paymaster) | ✅ Rules-based gas policy allowlisting specific contracts | ✅ Compatible with Privy / Turnkey | **Recommended Primary** |
| **Biconomy (v4 SDK)** | ✅ Supported | ✅ Gas tank sponsorship on testnet | ✅ Native Social Login SDK | **Strong Alternative** |
| **ZeroDev (Kernel v3)** | ✅ Supported | ✅ Session keys & paymaster | ✅ Web3Auth / Dynamic | **Viable** |
| **Alchemy Light Account** | ⚠️ Limited Amoy support on free tier | ⚠️ Paymaster credits primarily on Sepolia | ✅ Embedded Accounts | Secondary |

---

## 3. Paymaster Sponsorship Policy (FR-7.5)

To prevent fund draining or arbitrary transaction sponsorship, the Paymaster policy enforces strict access controls:

### 3.1 Allowlisted Contracts & Selectors
Gas sponsorship is strictly restricted to calls targeting TrustRent contracts with valid function selectors:
- `TenancyFactory.sol`: `createTenancy(...)`
- `DepositVault.sol`:
  - `sign()`
  - `lockDeposit()`
  - `recordMoveInEvidence(bytes32)`
  - `startMoveOut(bytes32)`
  - `raiseClaim(uint256,string)`
  - `acceptClaim()`
  - `assignArbitrator(address)`
  - `decide(uint256,uint256)`
  - `finalizeRefund()`
- `MockINR.sol`:
  - `requestFaucet()`
  - `approve(address,uint256)` (restricted only when `spender == vaultAddress`)

### 3.2 Rate Limiting
- Maximum sponsored UserOperations per user smart account: **15 transactions per 24-hour rolling window**.

---

## 4. Fallback Strategy: Plain EOA Signing

If Polygon Amoy paymaster endpoints or bundlers experience downtime during viva evaluations:
1. The frontend toggles to standard Web3 provider mode (`ethers.BrowserProvider` / MetaMask / Hardhat test accounts).
2. Users fund their EOA with faucet POL from Polygon's official Amoy faucet.
3. Contracts function identically without code alteration because `msg.sender` validation supports both Smart Contract Accounts (ERC-4337) and standard EOAs.
