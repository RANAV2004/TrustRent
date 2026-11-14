"""Replays each reported attack and checks that it is now blocked."""
import io
import uuid
from sqlalchemy import delete, select, update
from app.core.config import UNSAFE_JWT_SECRETS, settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.deposits import Deposit, Payment
from app.models.marketplace import Listing
from app.models.user import User, UserRole
from app.services.seed import seed_demo_admin
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, profile, signup, tag

ADMIN = "admin@trustrent.in"


def wallet(email, role="tenant", address=None):
    return {"email": email, "name": "Wallet User", "role": role, "smart_account_address": address or "0x" + uuid.uuid4().hex + "0" * 8}


async def make_arbitrator(client):
    user, headers = await signup(client)
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == user["id"]).values(role=UserRole.ARBITRATOR))
        await db.commit()
    return user, headers


async def pending_id(client, monkeypatch, headers, name="id.jpg", data=b"\xff\xd8\xffid-bytes"):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    res = await client.post("/api/v1/users/me/identity", headers=headers, data={"docType": "PAN card"},
                            files={"file": (name, io.BytesIO(data), "image/jpeg")})
    assert res.status_code == 200
    return res


async def submissions(client, ah, user_id):
    rows = (await client.get("/api/v1/admin/verifications", headers=ah)).json()["identities"]
    return [r for r in rows if r["userId"] == user_id]


# 1. passwordless /auth/login
async def test_wallet_login_is_off_outside_demo_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    res = await client.post("/api/v1/auth/login", json=wallet(f"w_{tag()}@example.com"))
    assert res.status_code == 404


async def test_wallet_login_cannot_take_admin_or_existing_accounts(client):
    await admin_headers(client)
    assert (await client.post("/api/v1/auth/login", json=wallet(ADMIN))).status_code == 403
    assert (await client.post("/api/v1/auth/login", json=wallet(ADMIN.upper()))).status_code == 403
    user, _ = await signup(client)
    assert (await client.post("/api/v1/auth/login", json=wallet(user["email"]))).status_code == 403


# 2. self-assigned arbitrator role
async def test_wallet_login_cannot_pick_arbitrator(client):
    res = await client.post("/api/v1/auth/login", json=wallet(f"arb_{tag()}@example.com", "arbitrator"))
    assert res.status_code == 403


async def test_wallet_login_new_and_returning_user(client):
    email = f"w_{tag()}@example.com"
    first = await client.post("/api/v1/auth/login", json=wallet(email, "landlord"))
    assert first.status_code == 200 and first.json()["user"]["role"] == "landlord"
    new_address = "0x" + uuid.uuid4().hex + "2" * 8
    again = await client.post("/api/v1/auth/login", json=wallet(email, "landlord", new_address))
    assert again.status_code == 200 and again.json()["user"]["wallet_address"] == new_address
    taken = await client.post("/api/v1/auth/login", json=wallet(f"w2_{tag()}@example.com", "tenant", new_address))
    assert taken.status_code == 409


async def test_arbitrator_cannot_open_documents_or_approve(client, monkeypatch):
    ah = await admin_headers(client)
    applicant, uh = await signup(client)
    await pending_id(client, monkeypatch, uh)
    sub = (await submissions(client, ah, applicant["id"]))[0]
    _, arb = await make_arbitrator(client)
    for path in ("/api/v1/admin/verifications", f"/api/v1/admin/identity/{sub['id']}/file",
                 "/api/v1/admin/verification-register.xlsx", "/api/v1/admin/users", "/api/v1/admin/conversations",
                 "/api/v1/admin/overview", "/api/v1/admin/ledger"):
        assert (await client.get(path, headers=arb)).status_code == 403, path
    res = await client.post(f"/api/v1/admin/identity/{sub['id']}/review", headers=arb, json={"approve": True})
    assert res.status_code == 403
    owner, oh = await signup(client, "owner")
    assert (await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=arb,
                              json={"approve": True})).status_code == 403
    assert (await client.get("/api/v1/arbitrator/disputes", headers=arb)).status_code == 200
    assert (await client.get(f"/api/v1/arbitrator/disputes/{uuid.uuid4()}", headers=arb)).status_code == 404
    assert (await client.get("/api/v1/arbitrator/disputes", headers=uh)).status_code == 403
    assert (await client.get(f"/api/v1/arbitrator/disputes/{uuid.uuid4()}", headers=uh)).status_code == 403
    assert (await client.get("/api/v1/admin/verifications", headers=uh)).status_code == 403


async def test_owner_cannot_self_approve_outside_demo_mode(client, monkeypatch):
    owner, oh = await signup(client, "owner")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    res = await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=oh, json={"approve": True})
    assert res.status_code == 403


# 3. /identity/verify self-verification
async def test_identity_verify_does_not_verify(client):
    _, uh = await signup(client)
    res = await client.post("/api/v1/identity/verify", headers=uh, json={
        "full_name": "A B", "id_type": "AADHAAR", "id_number": "12345678", "phone": "+919999999999"})
    assert res.status_code == 200 and res.json()["verified"] is False
    me = (await client.get("/api/v1/users/me", headers=uh)).json()["user"]
    assert me["idVerified"] is False
    short = await client.post("/api/v1/identity/verify", headers=uh, json={
        "full_name": "A B", "id_type": "AADHAAR", "id_number": "123", "phone": "+919999999999"})
    assert short.status_code == 400


# 4. the email is fixed once the account exists (no admin address, no someone-else's address)
async def test_email_cannot_be_changed(client):
    await admin_headers(client)
    user, uh = await signup(client)
    t = user["username"].removeprefix("user_")
    body = {k: v for k, v in profile(t).items() if k not in ("password", "accountType")}
    for email in (ADMIN, ADMIN.upper(), "victim@gmail.com", f"new_{t}@example.com"):
        res = await client.put("/api/v1/users/me", headers=uh, json=body | {"email": email})
        assert res.status_code == 400 and res.json()["detail"]["field"] == "email"
    me = (await client.get("/api/v1/users/me", headers=uh)).json()["user"]
    assert me["email"] == user["email"] and me["isAdmin"] is False
    same = await client.put("/api/v1/users/me", headers=uh, json=body | {"email": user["email"].upper(), "country": "Nepal"})
    assert same.status_code == 200 and same.json()["user"]["country"] == "Nepal"  # other fields still editable


async def test_cannot_sign_up_with_admin_email(client):
    res = await client.post("/api/v1/auth/signup/email-code", json=profile(tag()) | {"email": ADMIN})
    assert res.status_code == 409


async def test_admin_can_keep_own_email(client):
    ah = await admin_headers(client)
    me = (await client.get("/api/v1/users/me", headers=ah)).json()["user"]
    body = {"firstName": "TrustRent", "lastName": "Admin", "username": "admin", "email": ADMIN,
            "phone": me["phone"], "country": "India"}
    assert (await client.put("/api/v1/users/me", headers=ah, json=body)).status_code == 200


async def test_demo_google_cannot_take_over_accounts(client):
    await admin_headers(client)
    assert (await client.post("/api/v1/auth/google", json={"email": ADMIN})).status_code == 403
    user, _ = await signup(client)
    assert (await client.post("/api/v1/auth/google", json={"email": user["email"]})).status_code == 403
    email = f"g_{tag()}@gmail.com"
    first = await client.post("/api/v1/auth/google", json={"email": email})
    assert first.status_code == 200
    assert (await client.post("/api/v1/auth/google", json={"email": email})).status_code == 200
    assert (await client.post("/api/v1/auth/google", json={"email": "not-an-email"})).status_code == 400


async def test_google_off_without_client_id_in_live_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert (await client.post("/api/v1/auth/google", json={"email": "x@gmail.com"})).status_code == 501


async def test_admin_is_seeded_in_live_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == ADMIN).values(password_hash=None))
        await db.commit()
        await seed_demo_admin(db)
        admin = await db.scalar(select(User).where(User.email == ADMIN))
    assert admin is not None and admin.password_hash
    res = await client.post("/api/v1/auth/password-login", json={"identifier": ADMIN, "password": settings.DEMO_ADMIN_PASSWORD})
    assert res.status_code == 200


# uploaded HTML must not render in the admin's browser
async def test_documents_never_render_html(client, monkeypatch):
    ah = await admin_headers(client)
    applicant, uh = await signup(client)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    refused = await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                                files={"file": ("evil.html", io.BytesIO(b"<script>alert(1)</script>"), "image/jpeg")})
    assert refused.status_code == 400 and refused.json()["detail"]["field"] == "file"  # not a PDF or image
    await pending_id(client, monkeypatch, uh, name="evil.html", data=b"\xff\xd8\xff<script>alert(1)</script>")
    sub = (await submissions(client, ah, applicant["id"]))[0]
    res = await client.get(f"/api/v1/admin/identity/{sub['id']}/file", headers=ah)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.headers["content-disposition"].startswith("attachment")
    assert res.headers["x-content-type-options"] == "nosniff"
    _, uh2 = await signup(client)
    applicant2 = (await client.get("/api/v1/users/me", headers=uh2)).json()["user"]
    await pending_id(client, monkeypatch, uh2, name="scan.jpg")
    sub2 = (await submissions(client, ah, applicant2["id"]))[0]
    img = await client.get(f"/api/v1/admin/identity/{sub2['id']}/file", headers=ah)
    assert img.headers["content-type"] == "image/jpeg" and img.headers["content-disposition"].startswith("inline")
    assert (await client.get(f"/api/v1/admin/identity/{uuid.uuid4()}/file", headers=ah)).status_code == 404
    assert (await client.post(f"/api/v1/admin/identity/{uuid.uuid4()}/review", headers=ah,
                              json={"approve": True})).status_code == 404
    assert (await client.get(f"/api/v1/admin/owner-applications/{uuid.uuid4()}/id", headers=ah)).status_code == 404


async def test_owner_documents_for_admin(client):
    ah = await admin_headers(client)
    owner, _, _ = await owner_with_listing(client)
    idf = await client.get(f"/api/v1/admin/owner-applications/{owner['id']}/id", headers=ah)
    assert idf.status_code == 200 and idf.content == b"\xff\xd8\xffid"
    deed = await client.get(f"/api/v1/admin/owner-applications/{owner['id']}/property", headers=ah)
    assert deed.headers["content-type"] == "application/pdf"
    assert (await client.get(f"/api/v1/admin/owner-applications/{owner['id']}/other", headers=ah)).status_code == 404


# rejecting a second ID keeps an earlier approval
async def test_reject_keeps_earlier_approval(client, monkeypatch):
    ah = await admin_headers(client)
    applicant, uh = await signup(client)
    await pending_id(client, monkeypatch, uh)
    first = (await submissions(client, ah, applicant["id"]))[0]
    await client.post(f"/api/v1/admin/identity/{first['id']}/review", headers=ah, json={"approve": True})
    await pending_id(client, monkeypatch, uh, name="blurry.jpg")
    second = next(s for s in await submissions(client, ah, applicant["id"]) if s["status"] == "pending")
    res = await client.post(f"/api/v1/admin/identity/{second['id']}/review", headers=ah, json={"approve": False})
    assert res.json()["submission"]["status"] == "rejected"
    assert (await client.get("/api/v1/users/me", headers=uh)).json()["user"]["idVerified"] is True
    await client.post(f"/api/v1/admin/identity/{first['id']}/review", headers=ah, json={"approve": False})
    assert (await client.get("/api/v1/users/me", headers=uh)).json()["user"]["idVerified"] is False


# double deposit and deleted listing
async def test_second_paid_order_does_not_create_second_deposit(client):
    owner, oh, listing = await owner_with_listing(client)
    _, th = await verified_tenant_with_visit(client, listing, oh)
    orders = []
    for _ in range(2):
        res = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
        assert res.status_code == 200
        orders.append(res.json()["orderId"])
    assert (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": orders[0]})).status_code == 200
    dup = await client.post("/api/v1/payments/verify", headers=th, json={"orderId": orders[1]})
    assert dup.status_code == 409 and "already have an active deposit" in dup.json()["detail"]["message"]
    async with AsyncSessionLocal() as db:
        count = len(list(await db.scalars(select(Deposit).where(Deposit.listing_id == listing["id"]))))
        status = await db.scalar(select(Payment.status).where(Payment.order_id == orders[1]))
    assert count == 1 and status == "cancelled"
    blocked = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    assert blocked.status_code == 409


async def test_paying_for_deleted_listing_does_not_crash(client):
    owner, oh, listing = await owner_with_listing(client)
    _, th = await verified_tenant_with_visit(client, listing, oh)
    order = (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})).json()
    async with AsyncSessionLocal() as db:
        from app.models.marketplace import Conversation, Message
        convs = list(await db.scalars(select(Conversation.id).where(Conversation.listing_id == listing["id"])))
        await db.execute(delete(Message).where(Message.conversation_id.in_(convs)))
        await db.execute(delete(Conversation).where(Conversation.id.in_(convs)))
        await db.execute(delete(Listing).where(Listing.id == listing["id"]))
        await db.commit()
    res = await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order["orderId"]})
    assert res.status_code == 409 and "no longer listed" in res.json()["detail"]["message"]


async def test_payment_edge_cases(client, monkeypatch):
    _, uh = await signup(client)
    assert (await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": "nope"})).status_code == 404
    unverified = await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "week"})
    assert unverified.status_code == 403
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "Passport"},
                      files={"file": ("p.jpg", io.BytesIO(b"\xff\xd8\xffpassport"), "image/jpeg")})
    assert (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "year"})).status_code == 400
    assert (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "gift"})).status_code == 400
    assert (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "deposit", "listingId": "NOPE"})).status_code == 404
    order = (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "week"})).json()
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert (await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": order["orderId"]})).status_code == 400
    assert (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "week"})).status_code == 503


async def test_owner_cannot_pay_deposit_on_own_home(client):
    owner, oh, listing = await owner_with_listing(client)
    await client.post("/api/v1/users/me/identity", headers=oh, data={"docType": "Passport"},
                      files={"file": ("p.jpg", io.BytesIO(b"\xff\xd8\xffpassport"), "image/jpeg")})
    res = await client.post("/api/v1/payments/order", headers=oh, json={"purpose": "deposit", "listingId": listing["id"]})
    assert res.status_code == 400


# evidence verify needs a party to the tenancy
async def tenancy_with_evidence(client):
    landlord = await client.post("/api/v1/auth/login", json=wallet(f"l_{tag()}@example.com", "landlord"))
    tenant_email = f"t_{tag()}@example.com"
    tenant = await client.post("/api/v1/auth/login", json=wallet(tenant_email))
    lh = {"Authorization": f"Bearer {landlord.json()['access_token']}"}
    th = {"Authorization": f"Bearer {tenant.json()['access_token']}"}
    return lh, th, tenant_email


def draft(**over):
    data = {"property_address": "Flat 1, Indore", "monthly_rent": "20000", "deposit_amount": "40000",
            "deduction_cap": "10000", "claim_window_days": "7"}
    return data | over


async def test_evidence_verify_requires_party(client):
    lh, th, tenant_email = await tenancy_with_evidence(client)
    res = await client.post("/api/v1/tenancies/draft", headers=lh, data=draft(tenant_email=tenant_email),
                            files={"lease_file": ("lease.pdf", io.BytesIO(b"%PDF lease"), "application/pdf")})
    tenancy_id = res.json()["tenancy_id"]
    up = await client.post("/api/v1/evidence/upload", headers=th, data={"tenancy_id": tenancy_id, "evidence_type": "move_in"},
                           files={"file": ("x.html", io.BytesIO(b"<script>1</script>"), "text/html")})
    evidence_id = up.json()["evidence_id"]
    _, sh = await signup(client)
    assert (await client.get(f"/api/v1/evidence/{evidence_id}/verify", headers=sh)).status_code == 403
    assert (await client.get(f"/api/v1/evidence/{evidence_id}/download", headers=sh)).status_code == 403
    assert (await client.get(f"/api/v1/evidence/{uuid.uuid4()}/verify", headers=th)).status_code == 404
    assert (await client.post("/api/v1/evidence/upload", headers=sh, data={"tenancy_id": tenancy_id, "evidence_type": "move_in"},
                              files={"file": ("a.jpg", io.BytesIO(b"a"), "image/jpeg")})).status_code == 403
    assert (await client.post("/api/v1/evidence/upload", headers=th, data={"tenancy_id": "missing", "evidence_type": "move_in"},
                              files={"file": ("a.jpg", io.BytesIO(b"a"), "image/jpeg")})).status_code == 404
    assert (await client.get(f"/api/v1/evidence/{evidence_id}/verify", headers=lh)).json()["matches"] is True
    dl = await client.get(f"/api/v1/evidence/{evidence_id}/download", headers=lh)
    assert dl.headers["content-type"] == "application/octet-stream" and dl.headers["x-content-type-options"] == "nosniff"
    ah = await admin_headers(client)
    assert (await client.get(f"/api/v1/evidence/{evidence_id}/verify", headers=ah)).status_code == 200


# tenancy draft input checks
async def test_tenancy_draft_validation(client):
    lh, th, tenant_email = await tenancy_with_evidence(client)
    lease = {"lease_file": ("lease.pdf", io.BytesIO(b"%PDF"), "application/pdf")}
    for bad in (draft(claim_window_days="1"), draft(claim_window_days="31"), draft(deposit_amount="0"),
                draft(deposit_amount="-5"), draft(deduction_cap="0"), draft(deduction_cap="50000"), draft(monthly_rent="0")):
        res = await client.post("/api/v1/tenancies/draft", headers=lh, data=bad | {"tenant_email": tenant_email}, files=lease)
        assert res.status_code == 400, bad
    assert (await client.post("/api/v1/tenancies/draft", headers=th, data=draft(tenant_email=tenant_email), files=lease)).status_code == 403
    missing = await client.post("/api/v1/tenancies/draft", headers=lh, data=draft(tenant_email="ghost@example.com"), files=lease)
    assert missing.status_code == 404
    ok = await client.post("/api/v1/tenancies/draft", headers=lh, data=draft(tenant_email=tenant_email, claim_window_days="30"), files=lease)
    assert ok.status_code == 200
    tid = ok.json()["tenancy_id"]
    listed = await client.get("/api/v1/tenancies/", headers=lh)
    assert listed.status_code == 200 and any(t["id"] == tid for t in listed.json())


# tokens and secrets
async def test_token_for_deleted_user_is_401(client):
    token = create_access_token(subject=str(uuid.uuid4()))
    res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert (await client.get("/api/v1/users/me", headers={"Authorization": "Bearer junk"})).status_code == 401


def test_jwt_secret_is_never_a_known_default():
    assert settings.JWT_SECRET not in UNSAFE_JWT_SECRETS and len(settings.JWT_SECRET) >= 32
    assert settings.DEBUG is False

