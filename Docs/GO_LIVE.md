# Taking TrustRent live

TrustRent runs in **demo mode** by default, which is right for the presentation. Each live service switches on by itself as soon as its keys are in the backend `.env`. Turn demo mode off last.

| Feature | Demo mode (now) | Live (after these steps) |
|---|---|---|
| Email verification at sign-up | Code `123456` shown on screen | Real 6-digit code emailed from your Gmail |
| Payments (Premium, deposits) | Demo checkout, no money | Razorpay: UPI, cards, net banking |
| Deposit refunds | Marked "demo-refund" | Refunded to the original payment by Razorpay |
| ID / owner verification | Auto-approved / self-approved | Approved by an admin on the Admin desk |
| Database | SQLite file | Hosted PostgreSQL |
| Documents and photos | Encrypted on the server's disk | Encrypted in a private S3 / Cloudflare R2 bucket; photos in a public bucket |
| Deposit receipts | TrustRent hash-chained ledger | Also written to the DepositRegistry contract on Polygon |

## 1. Hosted PostgreSQL (free tier is enough to start)

1. Create a database on **Neon** (neon.tech), **Supabase** or **Render**.
2. Copy its connection string and put it in `.env` as it is, for example
   `DATABASE_URL=postgres://user:password@ep-xyz.ap-southeast-1.aws.neon.tech/trustrent?sslmode=require`.
   The backend converts it for asyncpg and turns on SSL.
3. Start the backend once: tables are created automatically.

## 2. Secure file storage (Cloudflare R2, or AWS S3)

1. Create two buckets: `trustrent-private` (no public access) and `trustrent-public` (public access on, or a custom domain).
2. Create an API token with read/write on both.
3. In `.env`:
   ```
   STORAGE_PROVIDER=s3
   S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
   S3_ACCESS_KEY_ID=...
   S3_SECRET_ACCESS_KEY=...
   S3_PRIVATE_BUCKET=trustrent-private
   S3_PUBLIC_BUCKET=trustrent-public
   MEDIA_PUBLIC_BASE_URL=https://<your public bucket URL>
   ```
4. Generate a new encryption key and keep it secret (losing it makes documents unreadable):
   `python -c "import secrets; print(secrets.token_hex(32))"` → `STORAGE_MASTER_KEY_HEX=...`

## 3. Payments (Razorpay)

1. Sign up at razorpay.com and finish KYC. Start with **test mode** keys (`rzp_test_...`).
2. In `.env`: `RAZORPAY_KEY_ID=...` and `RAZORPAY_KEY_SECRET=...`.
3. Premium and deposit payments now open the Razorpay window. The backend checks every payment's signature before activating anything, and refunds the tenant's share at settlement through Razorpay.
4. Switch to live keys after testing.

**Before holding real deposits:** collecting and holding other people's money (escrow) is regulated in India. Use Razorpay's escrow / Route product or a bank escrow account, and get advice on RBI payment-aggregator rules. Paying the owner's share is currently marked on the Admin desk after you pay it out.

## 4. Email verification at sign-up (Gmail, free)

Every new account confirms its email: after the sign-up form, a 6-digit code (valid 10 minutes, 5 tries, one new code a minute, stored only as a hash) is emailed and the account is created only with the right code.

1. Use a Gmail account for sending, e.g. a new `trustrent.otp@gmail.com`.
2. Turn on **2-Step Verification** for it (Google Account → Security).
3. Create an **App Password** (Google Account → Security → App passwords, name it "TrustRent"). Copy the 16 characters without spaces. It is not your Gmail password and can be revoked any time.
4. In `.env`:
   ```
   SMTP_USER=trustrent.otp@gmail.com
   SMTP_APP_PASSWORD=abcdefghijklmnop
   SMTP_FROM_NAME=TrustRent
   ```
   `SMTP_HOST` / `SMTP_PORT` default to Gmail (`smtp.gmail.com`, `587`); another SMTP service works by changing them.
5. Restart the backend.

Gmail allows roughly 500 emails a day. The first emails may land in spam: mark them "Not spam". If sending fails, the backend log says why (usually a wrong app password). With `DEMO_MODE=False` and no SMTP settings, sign-up is paused (Google sign-in still works).

## 5. Deposit receipts on the blockchain (optional, recommended for the project)

```bash
cd contracts
npm install
# .env: POLYGON_AMOY_RPC_URL and DEPLOYER_PRIVATE_KEY (a wallet with test MATIC from the Amoy faucet)
npx hardhat run scripts/deploy-deposit-registry.ts --network amoy
```
Then in the backend `.env`: `DEPOSIT_REGISTRY_ADDRESS=<printed address>` and `CHAIN_SIGNER_PRIVATE_KEY=<the same deployer key>`. New deposits then show "Polygon Amoy blockchain" and a "View on explorer" link. Without these, receipts use the built-in hash-chained ledger, which the lookup page verifies the same way.

## 6. Admins

`ADMIN_EMAILS=["you@yourdomain.in","partner@yourdomain.in"]`. Those accounts see **Admin** in the menu: verification requests with their documents, approve/reject, deposit settlement, and **Download Excel register**. The register file is also kept at `VERIFICATION_REGISTER_PATH` and rewritten on every submission and decision. It contains personal contact details: keep it off GitHub (it is git-ignored) and share it only with your team.

## 7. Legal pages

The Privacy Policy (`/privacy`) and Terms of Use (`/terms`) are written for India (DPDP Act 2023). Before launch:
- set `NEXT_PUBLIC_CONTACT_EMAIL` and `NEXT_PUBLIC_GRIEVANCE_OFFICER` in the frontend `.env.local`;
- have a lawyer review both pages for your company and deposit model.

## 8. Deploy

- **Backend** (Render, Railway or a VPS): start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, root directory `backend`, environment from `.env`. Set `CORS_ORIGINS=["https://your-frontend-domain"]`, a long random `JWT_SECRET`, `DEBUG=false`.
- **Frontend** (Vercel): root directory `frontend`, `NEXT_PUBLIC_API_URL=https://your-backend-domain/api/v1`.

## 9. Switch off demo mode

`DEMO_MODE=False` and `SEED_SAMPLE_LISTINGS=False` (removes the sample Indore homes and their auto-replying owners). With demo mode off and a key missing, that feature says it is unavailable instead of faking it: payments return "not set up" and sign-up is paused until email is set up.
