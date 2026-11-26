# TrustRent API v1.1–v1.2: web-app endpoints

**Change type:** additive. Every v1.0 route in [`INTERFACE_FREEZE_v1.0.md`](./INTERFACE_FREEZE_v1.0.md) is unchanged, including `POST /auth/login` and `GET /auth/me`.
Full schema: [`openapi.json`](./openapi.json) (regenerated). All routes are under `/api/v1` and take the same JWT bearer token as v1.0.

These endpoints back the Next.js frontend in `frontend/`: sign-up and sign-in, home search, owner verification and listings, messaging with visit requests, and Premium.

## Accounts (`app/api/v1/accounts.py`)

| Method & path | Body | Returns |
|---|---|---|
| `POST /auth/signup` | `{firstName, lastName, username, email, phone, country, password, accountType: "seeker"\|"owner", emailCode}` | Step 2: `{access_token, user}`; account created only with the right emailed code |
| `POST /auth/password-login` | `{identifier (username or email), password}` | `{access_token, user}` |
| `POST /auth/signup/email-code` | sign-up form | Step 1: validates the form, emails a 6-digit code; `{sent, email, demoCode}` (`demoCode` only in `DEMO_MODE` without SMTP); 429 within a minute |
| `POST /auth/google` | `{credential}` (Google ID token, needs `GOOGLE_CLIENT_ID`) or `{email}` (`DEMO_MODE` only) | `{access_token, user}` |
| `POST /auth/password/forgot` | `{email}` | always `{ok: true}` |
| `GET /users/me` · `PUT /users/me` | profile fields | `{user}` |
| `PUT /users/me/account-type` | `{accountType}` | `{user}` |
| `POST /users/me/identity` | multipart `docType`, `file` | `{user, pendingReview}` |
| `POST /subscriptions` · `GET /subscriptions/plans` | `{planId: "week"\|"month"\|"quarter"}` | `{user}` |

`accountType` maps to the existing `role` column: `seeker` is `tenant`, `owner` is `landlord`. Arbitrators keep their role.
Errors with a field look like `{"detail": {"message": "...", "field": "username"}}`.

## Listings (`app/api/v1/listings.py`)

| Method & path | Notes |
|---|---|
| `GET /listings` | All live listings. The address is withheld and the pin rounded to about 1 km unless the owner chose to show it, the viewer owns it, or the viewer has a confirmed visit. |
| `GET /listings/{id}` | Same privacy rule. |
| `GET /owner/listings` | My listings, including paused ones. |
| `POST /owner/listings` | multipart: `data` (JSON) + 1–8 `photos`. Needs an approved owner application. Photos are served from `/media/...`. |
| `PATCH /owner/listings/{id}` | `{status: "live"\|"paused"}` |
| `DELETE /owner/listings/{id}` | Hard delete, or a `removed` status if conversations exist. |

## Owner verification (`app/api/v1/owner.py`)

| Method & path | Notes |
|---|---|
| `GET /owner/application` · `POST /owner/application` | multipart: `relation`, `idDocType`, `propertyDocType`, `propertyAddress`, `idFile`, `propertyFile`. Files are stored AES-256-GCM encrypted, and keccak hashes are kept. |
| `GET /admin/owner-applications` | Reviewers (arbitrator role) only. |
| `GET /admin/owner-applications/{userId}/{id\|property}` | Decrypted download for reviewers. |
| `POST /owner/application/{userId}/review` | `{approve, note}`. Reviewers; in `DEMO_MODE` the owner may also review their own application. |

## Messages (`app/api/v1/messages.py`)

| Method & path | Notes |
|---|---|
| `GET /inbox` | `{conversations, messages}` for the signed-in user. The frontend polls this every 4 s. |
| `POST /conversations` | `{listingId}`: starts or reuses one conversation per listing per seeker. Returns 403 for non-Premium users while a listing is in early access (`EARLY_ACCESS_HOURS`, default 48). |
| `POST /conversations/{id}/messages` | `{kind: "text", text}` or `{kind: "visit", slots: [ISO,...≤3], text}` |
| `POST /messages/{id}/visit-response` | `{accept, slot}`. Owner only. |
| `POST /conversations/{id}/read` | Marks the conversation read. |

## New settings (`.env`)

`DEMO_MODE` (default true), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM_NAME`, `GOOGLE_CLIENT_ID`, `MEDIA_DIR`, `SEED_SAMPLE_LISTINGS`, `EARLY_ACCESS_HOURS`.
**Set `DEMO_MODE=false` in production.** It turns off:
- the on-screen OTP;
- Google sign-in by email alone;
- self-approval of owner applications;
- instant ID approval and payment-free Premium;
- auto-replies from the seeded sample owners.

## New tables

`listings`, `owner_applications`, `conversations`, `messages`, `otp_codes`, `email_verification_codes`. New nullable columns on `users`:
- `first_name`, `last_name`, `username`, `phone`, `country`
- `password_hash`, `provider`
- `premium_plan`, `premium_until`
- `is_demo`

`create_all` adds the new tables on startup. **An existing development database needs deleting (or an Alembic migration) for the new `users` columns.**

## v1.2 additions (admin desk, payments, deposit receipts)

| Method & path | Notes |
|---|---|
| `GET /config` | Public: demo mode, payment provider, email-code sender (`emailCodes`), deposit network. |
| `GET /admin/verifications` | Admins (`ADMIN_EMAILS`): owner and ID requests with applicant contact details. |
| `GET /admin/owner-applications/{userId}/{id\|property}` · `GET /admin/identity/{id}/file` | Decrypted document, `no-store`. |
| `POST /admin/identity/{id}/review` · `POST /owner/application/{userId}/review` | `{approve, note}`. Rewrites the Excel register. |
| `GET /admin/verification-register.xlsx` | The Excel register (2 sheets). |
| `POST /payments/order` | `{purpose:"premium", planId}` or `{purpose:"deposit", listingId}` (needs verified ID and a confirmed visit). Razorpay order, or a demo order in DEMO_MODE. |
| `POST /payments/verify` | `{orderId, paymentId, signature}`: checks the Razorpay signature, then activates Premium or creates the deposit and its receipt. |
| `GET /deposits` · `GET /deposits/{id}` · `GET /deposits/lookup?q=` | Receipts with a `verification` block (ledger intact, details match). Lookup takes a deposit ID or any receipt hash; outsiders see no personal data. |
| `POST /deposits/{id}/propose` | Owner: `{deducted, reason}`. |
| `POST /deposits/{id}/respond` | Tenant: `{accept}`. Accept settles (refund via Razorpay); reject marks it disputed. |
| `POST /admin/deposits/{id}/settle` · `GET /admin/deposits` · `POST /admin/deposits/{id}/owner-paid` | Admin settlement and payout tracking. |

Contract: `contracts/contracts/DepositRegistry.sol` (`recordDeposit`, `settleDeposit`, `getDeposit`), deployed with `scripts/deploy-deposit-registry.ts`. New tables: `identity_submissions`, `payments`, `deposits`, `ledger_entries`.

## v1.3 additions (admin console, `app/api/v1/admin_console.py`)

All under `/admin`, admin token required. Ban, delete and revoke need an `ADMIN_EMAILS` admin (not an arbitrator); admins can't act on admin accounts.

| Endpoint | What it does |
|---|---|
| `GET /admin/overview` | Counts: users, listings by status, deposits held/open/disputed/refunded, conversations, messages, Premium revenue, pending verifications |
| `GET /admin/users` | Every account with type, verification, Premium, ban/delete state, listing and deposit counts |
| `POST /admin/users/{id}/ban` `{reason}` · `POST /admin/users/{id}/unban` | A banned account gets 403 on every call and at sign-in; its listings disappear from search |
| `DELETE /admin/users/{id}` | Anonymises the account (personal details, ID documents and listings removed; deposits, payments and chats kept). Refused while the user has an unsettled deposit |
| `GET /admin/listings` · `POST /admin/listings/{id}/unlist` `{reason}` · `POST /admin/listings/{id}/relist` | Unlisted = status `blocked` with `admin_note`; the owner sees the reason and can't relist it |
| `GET /admin/conversations` · `GET /admin/conversations/{id}/messages` | Read-only chats |
| `GET /admin/premium` · `POST /admin/premium/{id}/revoke` | Plans, members, payments; revoking ends Premium now |
| `GET /admin/ledger` | Every receipt block with previous hash, details hash and block hash, and whether the chain is intact |

New columns (added automatically to an existing database on startup by `add_missing_columns`): `users.banned_at`, `users.ban_reason`, `users.deleted_at`, `listings.admin_note`.
With `SEED_SAMPLE_LISTINGS`, startup also seeds three sample tenants (two with Premium), their chats and three deposit receipts: `DEP-DEMO0001` held, `DEP-DEMO0002` settlement proposed, `DEP-DEMO0003` settled.
