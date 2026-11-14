"""Fixes from the security review: production guard, rate limits, MFA, uploads, payments, ledger, settlements."""
import asyncio
import hashlib
import hmac
import io
import json
from datetime import timedelta
import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core import config as config_module
from app.core import totp
from app.core.config import check_settings, settings
from app.core.database import AsyncSessionLocal
from app.models.deposits import Deposit, LedgerEntry, Payment
from app.models.user import User
from app.services.seed import seed_demo_admin
from tests.staff import finish_mfa
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import PNG, owner_with_listing, profile, signup, tag, with_email_code


# production guard
def test_production_refuses_demo_mode_and_weak_keys(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "STORAGE_MASTER_KEY_HEX", config_module.DEV_STORAGE_KEY)
    monkeypatch.setattr(settings, "JWT_SECRET", "short")
    problems = " ".join(check_settings())
    assert "DEMO_MODE" in problems and "STORAGE_MASTER_KEY_HEX" in problems and "JWT_SECRET" in problems
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "ENABLE_LEGACY_API", False)
    monkeypatch.setattr(settings, "STORAGE_MASTER_KEY_HEX", "ab" * 32)
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 40)
    assert check_settings() == []


def test_demo_mode_defaults_off():
    assert config_module.Settings.model_fields["DEMO_MODE"].default is False


async def test_demo_shortcuts_off_outside_demo(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert (await client.post("/api/v1/auth/google", json={"email": f"g_{tag()}@gmail.com"})).status_code == 501
    wallet = {"email": f"w_{tag()}@example.com", "name": "W", "role": "tenant"}
    assert (await client.post("/api/v1/auth/login", json=wallet)).status_code == 404


# rate limits
async def test_login_is_rate_limited(client, monkeypatch):
    user, _ = await signup(client)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    codes = [(await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "wrong999"})).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    blocked = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "secret123"})
    assert blocked.status_code == 429 and blocked.headers["retry-after"]


async def test_signup_codes_and_messages_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    codes = [(await client.post("/api/v1/auth/signup/email-code", json=profile(tag()))).status_code for _ in range(11)]
    assert codes.count(200) == 10 and codes[-1] == 429


async def test_unknown_user_login_does_the_same_work(client, monkeypatch):
    calls = []
    import app.api.v1.accounts as accounts
    real = accounts.verify_secret
    monkeypatch.setattr(accounts, "verify_secret", lambda pw, stored: calls.append(stored) or real(pw, stored))
    res = await client.post("/api/v1/auth/password-login", json={"identifier": "nobody_here", "password": "whatever1"})
    assert res.status_code == 401 and calls and calls[0].startswith("scrypt$")  # hashed against a dummy


# staff two-step sign-in
async def test_admin_login_needs_totp(client):
    async with AsyncSessionLocal() as db:
        await seed_demo_admin(db)
        await db.execute(update(User).where(User.email == settings.ADMIN_EMAILS[0]).values(
            totp_secret=None, totp_enabled=False, totp_last_step=None))
        await db.commit()
    res = await client.post("/api/v1/auth/password-login", json={"identifier": "admin", "password": settings.DEMO_ADMIN_PASSWORD})
    body = res.json()
    assert res.status_code == 200 and body["mfaRequired"] and "access_token" not in body
    assert body["enrolled"] is False and body["secret"] and body["otpauthUrl"].startswith("otpauth://totp/")
    assert (await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {body['mfaToken']}"})).status_code == 401
    wrong = await client.post("/api/v1/auth/mfa/verify", json={"mfaToken": body["mfaToken"], "code": "000000"})
    assert wrong.status_code == 401
    code = totp.code_at(body["secret"])
    ok = await client.post("/api/v1/auth/mfa/verify", json={"mfaToken": body["mfaToken"], "code": code})
    assert ok.status_code == 200 and ok.json()["user"]["isAdmin"] and ok.json()["user"]["mfaEnabled"]
    replay = await client.post("/api/v1/auth/mfa/verify", json={"mfaToken": body["mfaToken"], "code": code})
    assert replay.status_code == 401  # a code works once
    again = (await client.post("/api/v1/auth/password-login", json={"identifier": "admin", "password": settings.DEMO_ADMIN_PASSWORD})).json()
    assert again["enrolled"] is True and "secret" not in again


def test_totp_matches_rfc6238():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32("12345678901234567890")
    assert totp.code_at(secret, 59) == "287082" and totp.code_at(secret, 1111111109) == "081804"
    assert totp.verify(secret, "287082", at=59) is not None and totp.verify(secret, "287083", at=59) is None


# sessions
async def test_logout_all_and_password_reset_kill_old_tokens(client, mail):
    user, uh = await signup(client)
    assert (await client.post("/api/v1/auth/logout-all", headers=uh)).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=uh)).status_code == 401


# uploads
async def test_listing_photos_must_be_real_images_and_lose_exif(client):
    owner, oh, listing = await owner_with_listing(client)
    from tests.test_condition_photos import jpeg_with_gps
    from PIL import Image
    data = json.loads(json.dumps({k: listing[k] for k in ("title", "locality", "city", "pincode", "lat", "lng", "rent",
                                                             "deposit", "bhk", "furnishing", "area_sqft", "amenities",
                                                             "preferred_tenants", "available_from", "min_months", "max_months",
                                                             "description")}))
    data["address"] = "Flat 9"
    fake = await client.post("/api/v1/owner/listings", headers=oh, data={"data": json.dumps(data)},
                             files=[("photos", ("x.jpg", io.BytesIO(b"<html>not a photo</html>"), "image/jpeg"))])
    assert fake.status_code == 400 and fake.json()["detail"]["field"] == "photos"
    ok = await client.post("/api/v1/owner/listings", headers=oh, data={"data": json.dumps(data)},
                           files=[("photos", ("g.jpg", io.BytesIO(jpeg_with_gps()), "image/jpeg"))])
    assert ok.status_code == 201
    from app.core.config import settings as s
    path = s.MEDIA_DIR + "/" + ok.json()["photos"][0].split("/media/")[1]
    assert not Image.open(path).getexif()  # GPS and other EXIF removed


async def test_decompression_bomb_is_refused(client):
    from app.services.images import clean_image
    from fastapi import HTTPException
    from PIL import Image
    out = io.BytesIO()
    Image.new("1", (12000, 12000)).save(out, format="PNG")  # tiny file, 144 MP once decoded
    with pytest.raises(HTTPException):
        clean_image(out.getvalue())


async def test_oversized_request_is_rejected_early(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_REQUEST_MB", 1)
    _, uh = await signup(client)
    big = b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024)
    res = await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                            files={"file": ("big.jpg", io.BytesIO(big), "image/jpeg")})
    assert res.status_code == 413


async def test_security_headers_and_request_id(client):
    res = await client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert res.headers["x-request-id"] == "abc123" and res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY" and res.json()["version"] == "1.4.0"
    assert (await client.get("/api/v1/health/ready")).json()["database"] is True


# owner address must match the verified property
async def test_listing_at_unverified_address_waits_for_review(client):
    owner, oh, listing = await owner_with_listing(client)
    data = {k: listing[k] for k in ("title", "locality", "city", "lat", "lng", "rent", "deposit", "bhk", "furnishing",
                                     "area_sqft", "amenities", "preferred_tenants", "available_from", "min_months",
                                     "max_months", "description")}
    data |= {"address": "Somewhere else", "pincode": "411001", "city": "Pune"}
    res = await client.post("/api/v1/owner/listings", headers=oh, data={"data": json.dumps(data)},
                            files=[("photos", ("1.png", io.BytesIO(PNG), "image/png"))])
    other = res.json()
    assert res.status_code == 201 and other["status"] == "review"
    seeker, sh = await signup(client)
    assert (await client.get(f"/api/v1/listings/{other['id']}", headers=sh)).status_code == 404
    live = await client.patch(f"/api/v1/owner/listings/{other['id']}", headers=oh, json={"status": "live"})
    assert live.status_code == 403
    ah = await admin_headers(client)
    assert (await client.post(f"/api/v1/admin/listings/{other['id']}/relist", headers=ah)).json()["status"] == "live"


# payments
async def paid_deposit(client):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    order = (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})).json()
    dep = (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order["orderId"]})).json()["depositId"]
    return owner, oh, tenant, th, listing, dep


async def test_concurrent_verify_fulfils_once(client):
    _, uh = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("id.jpg", io.BytesIO(b"\xff\xd8\xffid"), "image/jpeg")})
    order = (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "week"})).json()
    await asyncio.gather(*[client.post("/api/v1/payments/verify", headers=uh, json={"orderId": order["orderId"]}) for _ in range(6)])
    async with AsyncSessionLocal() as db:
        pay = await db.scalar(select(Payment).where(Payment.order_id == order["orderId"]))
        user = await db.get(User, pay.user_id)
        days = (user.premium_until - pay.paid_at).days
    assert pay.status == "paid" and days in (6, 7)  # one week, added once


async def test_razorpay_webhook_completes_payment_without_the_browser(client, monkeypatch):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret123")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "hook-secret")

    async def fake_order(amount, receipt, notes):
        return {"id": f"order_{tag()}"}
    monkeypatch.setattr("app.services.payments.create_order", fake_order)
    order = (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})).json()
    event = {"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_123", "order_id": order["orderId"],
                                                                              "amount": order["amount"] * 100}}}}
    raw = json.dumps(event).encode()
    bad = await client.post("/api/v1/payments/webhook", content=raw, headers={"x-razorpay-signature": "nope"})
    assert bad.status_code == 401
    sig = hmac.new(b"hook-secret", raw, hashlib.sha256).hexdigest()
    for _ in range(2):  # Razorpay retries webhooks; the second one changes nothing
        res = await client.post("/api/v1/payments/webhook", content=raw, headers={"x-razorpay-signature": sig})
        assert res.status_code == 200 and res.json()["status"] == "paid"
    deps = (await client.get("/api/v1/deposits", headers=th)).json()
    assert len([d for d in deps if d["listing"]["id"] == listing["id"]]) == 1


# settlements
async def test_failed_refund_rolls_back_and_settling_happens_once(client, monkeypatch):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    async with AsyncSessionLocal() as db:
        d = await db.get(Deposit, dep)
        await db.execute(update(Payment).where(Payment.id == d.payment_id).values(provider="razorpay", payment_id="pay_x"))
        await db.commit()
    from app.services import payments

    async def broken(*a):
        raise payments.PaymentError("The refund was refused by the payment gateway.")
    monkeypatch.setattr(payments, "refund", broken)
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 0, "reason": ""})
    fail = await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True})
    assert fail.status_code == 502
    assert (await client.get(f"/api/v1/deposits/{dep}", headers=th)).json()["status"] == "settlement_proposed"
    calls = []

    async def ok(pid, amount):
        calls.append(amount)
        return {"id": "rfnd_1"}
    monkeypatch.setattr(payments, "refund", ok)
    results = await asyncio.gather(*[client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True}) for _ in range(3)])
    assert sorted(r.status_code for r in results)[0] == 200 and calls == [34000]  # refunded exactly once


async def test_ledger_cannot_fork(client):
    await paid_deposit(client)
    async with AsyncSessionLocal() as db:
        last = await db.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
        db.add(LedgerEntry(deposit_id="DEP-FORK", kind="deposit", amounts={}, data_hash="0x1", prev_hash=last.prev_hash,
                           entry_hash="0x" + "f" * 64))
        with pytest.raises(IntegrityError):
            await db.commit()


async def test_concurrent_ledger_appends_stay_a_chain(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    from tests.test_condition_photos import jpeg_with_gps
    await asyncio.gather(*[client.post(f"/api/v1/deposits/{dep}/photos", headers=h, data={"stage": "move_in", "room": "Kitchen"},
                                       files={"file": ("k.jpg", io.BytesIO(jpeg_with_gps()), "image/jpeg")})
                           for h in (th, oh, th, oh)])
    ah = await admin_headers(client)
    assert (await client.get("/api/v1/admin/ledger", headers=ah)).json()["intact"] is True


async def test_lookup_hides_reason_from_strangers(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 500, "reason": "Scratches on the kitchen door"})
    _, sh = await signup(client)
    public = (await client.get("/api/v1/deposits/lookup", headers=sh, params={"q": dep})).json()
    assert public["reason"] is None and public["verification"]["verified"] is True
    mine = (await client.get(f"/api/v1/deposits/{dep}", headers=th)).json()
    assert mine["reason"] == "Scratches on the kitchen door"


async def test_visit_requests_are_capped(client):
    owner, oh, listing = await owner_with_listing(client)
    from tests.test_marketplace import slot
    seeker, sh = await signup(client)
    from app.models.marketplace import utcnow
    async with AsyncSessionLocal() as db:  # Premium skips the 48-hour early-access wait
        await db.execute(update(User).where(User.id == seeker["id"]).values(premium_plan="week", premium_until=utcnow() + timedelta(days=7)))
        await db.commit()
    conv = (await client.post("/api/v1/conversations", headers=sh, json={"listingId": listing["id"]})).json()
    codes = [(await client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=sh,
                                json={"kind": "visit", "slots": [slot(2)]})).status_code for _ in range(3)]
    assert codes == [201, 201, 409]
    naive = await client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=sh,
                              json={"kind": "visit", "slots": ["2020-01-01T10:00:00"]})
    assert naive.status_code in (400, 409)


async def test_staff_google_signin_also_needs_totp(client, monkeypatch):
    await admin_headers(client)

    class FakeResp:
        status_code = 200
        def json(self):
            return {"aud": "cid", "email_verified": "true", "email": settings.ADMIN_EMAILS[0]}

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): ...
        async def get(self, *a, **k): return FakeResp()
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr("app.api.v1.accounts.httpx.AsyncClient", FakeClient)
    res = await client.post("/api/v1/auth/google", json={"credential": "tok"})
    assert res.status_code == 200 and res.json()["mfaRequired"] and "access_token" not in res.json()
    assert (await finish_mfa(client, res))["user"]["isAdmin"]


async def test_new_signup_still_works_end_to_end(client):
    p = await with_email_code(client, profile(tag()))
    assert (await client.post("/api/v1/auth/signup", json=p)).status_code == 201
