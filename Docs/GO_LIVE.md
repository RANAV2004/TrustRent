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
4. **Required:** the server refuses to start with `DEMO_MODE=False` and the demo key. Generate a new encryption key and keep it secret (losing it makes documents unreadable):
   `python -c "import secrets; print(secrets.token_hex(32))"` → `STORAGE_MASTER_KEY_HEX=...`

## 3. Payments (Razorpay)

1. Sign up at razorpay.com and finish KYC. Start with **test mode** keys (`rzp_test_...`).
2. In `.env`: `RAZORPAY_KEY_ID=...` and `RAZORPAY_KEY_SECRET=...`.
3. Premium and deposit payments now open the Razorpay window. The backend checks every payment's signature before activating anything, and refunds the tenant's share at settlement through Razorpay.
4. Add a webhook (Razorpay dashboard → Settings → Webhooks) pointing to
   `https://<your-backend>/api/v1/payments/razorpay/webhook` for the events `payment.captured` and `order.paid`,
   and put its secret in `RAZORPAY_WEBHOOK_SECRET`. Without it, a customer who pays and closes the window
   before returning to TrustRent is charged but gets nothing until you fix it by hand.
5. Switch to live keys after testing.

**Refund window:** Razorpay only refunds payments up to about 6 months old. For tenancies longer than that,
the automatic refund at settlement will be refused and the settlement will show an error; refund the tenant
by bank transfer instead. Plan an escrow product (Razorpay Route / bank escrow) before holding long deposits.

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

## 10. Safety checks built into the server

- On start-up with `DEMO_MODE=False`, the backend **refuses to start** if `STORAGE_MASTER_KEY_HEX` is the public demo key or not 64 hex characters, and logs a `Before going live:` warning for SQLite, local file storage, a missing Razorpay webhook secret, or `localhost` in `CORS_ORIGINS`. Read the logs after your first deploy.
- Sign-in allows 10 wrong passwords per account (50 per network) every 15 minutes; sign-up and reset codes are limited to 10 emails per network per hour. The limits live in the server's memory: if you run more than one instance, move them to Redis.
- Sign-ins last 7 days (`ACCESS_TOKEN_EXPIRE_MINUTES`). Resetting a password signs out every other device. When a session ends, the web app returns the user to the sign-in page.
- Forgot password sends a 6-digit code by email (same rules as the sign-up code), so it needs SMTP set up.
- A user can't change their email address from the profile form (an unverified address could take over someone's Google sign-in); change it for them from the database if asked.
- If the Polygon RPC is down, deposits and settlements still go through and keep their TrustRent ledger receipt; the error is logged.
- The frontend build fails if `NEXT_PUBLIC_API_URL` is missing, so a deploy can't silently fall back to the browser-only demo. Set `NEXT_PUBLIC_ALLOW_DEMO=true` only for a demo deployment.

## 11. Lawyers

- Lawyers click **Lawyer** next to "Create an account" on the sign-in page, then **Apply to get verified**, with their enrolment number, photo, ID and enrolment certificate. They get a reference such as `LAW-1A2B3C4D` and can check its status on the same page.
- **Admin → Legal → Applications**: open the documents, check the enrolment number with the State Bar Council, then **Approve and create account**. TrustRent creates the account and shows a username (e.g. `adv_meera0168`) and a temporary password once. With SMTP set up they're also emailed (set `APP_URL` so the email links to your site); otherwise send them yourself.
- The lawyer signs in from the **Lawyer** link next to "Create an account" on the sign-in page (`/lawyer-login`) and must choose their own password first. Lawyer accounts only see their portal: they can't browse homes, pay or switch account type.
- Owners see **Lawyers** in their menu: verified lawyers with photo, practice areas, contact details and experience. **Hire for an agreement** opens a chat. The lawyer uploads the agreement as a PDF; the owner downloads and prints it, and can share it with a tenant who has messaged them or paid them a deposit. Tenants find shared agreements under **Agreements**.
- **Admin → Legal → Lawyers**: suspend (hides them from the directory and blocks sign-in), restore, or issue a new password.
- Bar Council rules: profiles show facts only (no ratings or offers), and TrustRent takes no commission. Have your lawyer review the directory wording.

## 12. Security checks covered by tests

`backend/tests/test_attacks.py` tries each of these on every test run: opening admin APIs as a normal user, changing IDs in URLs, editing prices, faking payments with forged signatures in live mode, giving yourself admin/lawyer/verified/Premium at sign-up, guessing email codes and passwords, scripts and Excel formulas in names, non-photo uploads, and SQL injection.

**Demo mode is not safe for real users:** with `DEMO_MODE=True`, payments are simulated (anyone can "pay"), ID uploads are auto-approved and owners can approve themselves. Always run the live site with `DEMO_MODE=False`.

## 13. Admin two-step sign-in

- With `ADMIN_TWO_FACTOR=required` (the default), an admin signs in with their password and then a 6-digit code from an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password...).
- The first time, the admin console shows **Set up two-step sign-in**: scan the QR code, enter a code, then **save the 8 recovery codes** (download or print them). Each recovery code works once if the phone is lost; using one emails the admins.
- New recovery codes: **Admin → Overview → Get new recovery codes** (the old ones stop working).
- Lost the phone *and* the recovery codes: on the server (Render → your service → **Shell**) run
  `python scripts/reset_admin_2fa.py admin@yourdomain.in`, then sign in and set it up again. It can't be switched off from the website, so a stolen session can't remove it.
- Passwords reset by email still need the authenticator code for admins.

## 14. Email notifications

Users get an email (when SMTP is set up) for: a new chat message (at most one per conversation every 15 minutes, and none while they're reading it), visit requests and answers, deposit payments, settlement proposals, accept/dispute, admin settlements, ID and owner verification decisions, an unlisted home, lawyer requests, replies and documents, and agreements shared with tenants. Admins get a heads-up (at most hourly) about new ID, owner and lawyer applications and disputed deposits. Set `APP_URL` so the emails link to your site. Demo, banned and deleted accounts never get emails. Switch everything off with `EMAIL_NOTIFICATIONS=False`.

## 15. Error alerts and uptime monitoring

- **Alert emails:** when the server hits an unexpected error, a payment needs a manual refund, the blockchain fails, the database is unreachable or a recovery code is used, the admins get an email (the same problem at most every 30 minutes, at most 10 an hour). Send them elsewhere with `ERROR_ALERT_EMAILS=["you@yourdomain.in"]`, or turn them off with `ERROR_ALERTS=False`. Users see a plain "Something went wrong" message, never the technical details.
- **Sentry (optional, free plan):** create a Python project at sentry.io and put its DSN in `SENTRY_DSN`. Server errors and website crashes (reported by visitors' browsers to `/api/v1/client-errors`) appear there. Passwords, tokens, cookies and request bodies are removed before sending.
- **Uptime (free, 5 minutes):** at uptimerobot.com add an HTTP(s) monitor for `https://<your-backend>/api/v1/health` with the keyword `healthy`, and a second one for your website. It alerts you by email or app when either goes down; `/health` also checks the database. On Render's free plan, a monitor every 5 minutes also stops the backend from falling asleep.
- **Releases:** `/health` shows the deployed commit, so you can tell which version is live.

## 16. Removed prototype endpoints

The early blockchain-prototype endpoints (`/auth/login` wallet login, `/auth/me`, `/identity/verify`, `/tenancies`, `/evidence`, `/faucet`, `/arbitrator`) are gone; the website never used them. The API documentation pages (`/docs`, `/redoc`, `/openapi.json`) only appear in demo mode or with `DEBUG=True`. The files in `Docs/hand_off/` still describe the old prototype API.

## 17. Help & support queries

- Everyone signed in (tenants, owners, lawyers) has **Help** in the menu: raise a query with a category, a short problem title, a description and up to 5 screenshots (JPG/PNG/WebP, 5 MB each; re-saved as JPEG so hidden location data is removed, and stored encrypted like ID documents).
- Each query gets a unique ticket number such as `TKT-261126-4F7K` (date + 4 characters without look-alikes like 0/O). It's shown on screen and emailed. Users can search it under **Find a ticket**; they only ever see their own tickets.
- **Admin → Queries** lists them (Open / In progress / Closed, search by ticket number, title or email); the Overview shows how many are waiting. On a ticket: reply (the user gets an email; a first reply marks it *In progress*), **Resolve and close** with a resolution note the user sees, or **Reopen**. Closed tickets take no new messages from the user.
- A user can raise 10 queries a day. Deleting an account removes that user's screenshots but keeps the ticket text as a support record.
