# TrustRent frontend

Web app for **TrustRent: A Blockchain-Based Security Deposit Escrow and Verified Tenancy System for the Indian Rental Market**
(SVIIT Indore, final-year major project: Vansh Rana, Aniket Parmar, Akhil Antony, Sameer Ajay Chauhan; guide Prof. Jagrati Nagdiya).

People looking for a home search verified listings, message owners and book visits. (HomePref, an AI assistant for finding homes, will be added shortly.)
Owners verify their identity and property, then list homes with photos, a Google Maps location and tenancy terms.
The deposit vault (lease, deposit lock, claims and disputes) runs as a mock in the browser until the Solidity `DepositVault` is connected.

Stack: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4.

## Run it

```bash
npm install
npm run dev            # http://localhost:3000
```

Requires Node 20 or later. There are two modes:

- **API mode** (`NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `.env.local`): accounts, listings, owner verification, messages and Premium go to the FastAPI backend in `../backend`. Start it first (see the root README).
- **Demo mode** (`NEXT_PUBLIC_API_URL` empty): everything is kept in the browser's localStorage, so the UI works with no server at all.

`NEXT_PUBLIC_*` values are built into the bundle, so restart `npm run dev` (or rebuild) after changing them.

### Environment variables (`.env.local`)

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | *(unset = demo mode)* | Backend base URL including `/api/v1`, e.g. `http://localhost:8000/api/v1`. |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | *(unset)* | Shows the real Google button; set `GOOGLE_CLIENT_ID` to the same value in the backend. Without it, "Continue with Google" asks for an email (demo). |

## Demo walkthrough (for the viva)

**People looking for a home**
1. On **Sign up**, choose *I'm looking for a home*, then fill in name, surname, username, email, phone and country.
   Sign in also works with Google (simulated in demo). Sign-up confirms the email with a 6-digit code (demo code `123456`).
2. **Search homes**: type `Indore` or a pin code such as `452010`, then filter by rent, BHK, furnishing, facilities, deposit cap and tenant type.
3. Open a listing marked **New · Premium only**. It is locked, so click *Get early access* to go to **Premium**: verify your ID, pay (demo), and you get the **Verified Premium** badge.
4. Back on the listing, click **Request a visit**. The sample owner accepts automatically after about 1.5 seconds (see **Messages**). The map then shows the exact location.
5. **HomePref AI** (in the nav) shows a "will be updated shortly" page for now.

**Owners**
1. Sign up choosing *I'm renting out my home*. This takes you to the **Owner dashboard**.
2. **Verify yourself**: upload an ID document (masked Aadhaar recommended) and a property document. In demo mode, use the *review desk* buttons to approve.
3. **Add listing**:
   - Add photos (up to 8).
   - Fill in facilities, address and pin code.
   - Pin the location: *use my current location*, or paste a Google Maps link.
   - Set rent and deposit (warns above 2 months), minimum and maximum stay, who can rent, and *About you*.
4. Sign in as the seeker again: the new home appears in search, in the first 48 hours for Premium members only. Request a visit.
5. Sign in as the owner. **Messages** shows an unread badge; accept a time slot.

Anyone can switch between the two account types from the header.

**Deposit vault**: under *My tenancies* → Tenant / Landlord / Arbitrator, as in the previous phase (lease → lock deposit → move-out → claim → dispute → award).

## Routes

| Route | What it is |
|---|---|
| `/login`, `/signup`, `/forgot-password`, `/setup-profile` | Authentication and profile setup |
| `/search?q=` | Search by city, locality, pin code or listing reference, with filters and sorting |
| `/listings/[id]` | Listing: photos, facilities, Google Maps, owner record, message or visit request |
| `/agent` | HomePref AI: placeholder ("will be updated shortly") |
| `/deposits`, `/deposits/lookup?q=` | Deposit receipts, move-out settlement, look up by deposit ID or receipt hash |
| `/admin` | Admin desk: verification requests, documents, approve/reject, deposits, Excel register |
| `/privacy`, `/terms` | Privacy Policy and Terms of Use (public) |
| `/messages?c=` | Inbox and threads, with visit requests the owner can accept or decline |
| `/premium?from=` | Plans, ID check, demo checkout |
| `/owner`, `/owner/verify`, `/owner/listings/new` | Owner dashboard, verification application, new listing |

## How it talks to the backend

- `src/lib/api.ts` is the HTTP client. It stores the JWT in localStorage and turns FastAPI errors (`{detail: {message, field}}`) into form errors.
- `src/lib/auth.ts` has `ApiAuthService` for `/auth/signup`, `/auth/password-login`, `/auth/google`, `/users/me`, `/users/me/identity` and `/subscriptions`.
- `src/lib/sync.ts` keeps a browser cache of `/listings`, `/owner/listings`, `/owner/application` and `/inbox`. It polls the inbox every 4 s and listings every 30 s. Screens read the cache, so the same components serve both modes. Every change is sent to the API first, then the cache refreshes.
- `src/lib/owner.ts` and `src/lib/messages.ts` call the API in API mode and use localStorage in demo mode.

The full endpoint list is in `../Docs/hand_off/MARKETPLACE_API.md`, and the schema in `../Docs/hand_off/openapi.json`.

The deposit-vault screens (*My tenancies*) are still a client-side mock of the on-chain flow (sign → lock → move-out → claim → dispute → award). They will move to the contracts in `../contracts` once those are deployed to Amoy and the account-abstraction wallet is wired in.

## Sample data

The sample homes are six flats in Vijay Nagar (452010) and Pipliyahana (452016), Indore. Rents and sizes reflect what similar flats were listed for in October 2026. Building and owner names are invented. Photos are from [Unsplash](https://unsplash.com/license) (free to use) and load directly from Unsplash, so they need an internet connection. Edit `src/data/listings.json` and `../backend/app/data/listings.json` to change them; the backend syncs its sample listings from that file on every start.

## Privacy notes

- Demo mode never stores ID or property documents (only the file name). In API mode the backend stores them AES-256-GCM encrypted and only reviewers (arbitrator accounts) can download them. Delete them after review in production.
- Ask for a **masked Aadhaar** (UIDAI lets anyone download one with only the last 4 digits shown).
- Listings show only the locality on the map until the owner confirms a visit, unless the owner chooses to show the exact pin. In API mode the backend enforces this: it withholds the address and rounds the coordinates.

## Structure

```
src/
  app/
    (auth)/                   login, signup, forgot password, profile setup
    (app)/                    signed-in area (RequireAuth + header)
      search/ listings/[id]/  find homes
      agent/                  HomePref AI (placeholder)
      messages/ premium/
      owner/                  dashboard, verify/, listings/new/
      tenant/ landlord/ arbitrator/ tenancy/[id]/ lease/new/   deposit vault
  components/                 app-shell, auth-ui, profile-form, listing-ui, vault components
  lib/
    api.ts sync.ts            backend client (JWT) and the polled browser cache
    auth.ts auth-context.tsx  auth service (demo or API) and React context
    listings.ts               search, filters, sort, maps helpers, early access
    owner.ts messages.ts      owner application and listings, chat and visits
    local-store.ts            localStorage store with live updates (demo data / API cache)
    store.tsx                 mock deposit vault state machine
  data/listings.json          sample homes (Indore: Vijay Nagar, Pipliyahana)
```

UI ideas from SpareRoom: classifieds-style result cards, Early Bird access for paying members, and an in-app inbox with viewing requests.

## Checks

```bash
npx tsc --noEmit && npm run lint && npm run build
```
