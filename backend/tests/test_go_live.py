import hashlib
import hmac
import io
import json
import uuid
import pytest
from app.core.config import settings
from app.services import chain, payments
from tests.mailbox import OUTBOX
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, profile, signup

async def _paid_deposit(client):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    paid = await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})
    assert paid.status_code == 200, paid.text
    return oh, th, paid.json()["depositId"]

def _chain_down(monkeypatch):
    monkeypatch.setattr(chain, "enabled", lambda: True)

    def boom(*_a, **_k):
        raise ConnectionError("RPC unreachable")
    monkeypatch.setattr(chain, "_send", boom)
    monkeypatch.setattr(chain, "_read", boom)

async def test_deposit_is_recorded_when_blockchain_is_down(client, monkeypatch):
    _chain_down(monkeypatch)
    _, th, dep_id = await _paid_deposit(client)
    dep = (await client.get(f"/api/v1/deposits/{dep_id}", headers=th)).json()
    assert dep["status"] == "held" and dep["receipt"]["network"] == "trustrent-ledger"
    assert dep["verification"]["verified"] is True

async def test_settling_ledger_only_deposit_after_chain_enabled(client, monkeypatch):
    oh, th, dep_id = await _paid_deposit(client)
    calls = []
    monkeypatch.setattr(chain, "enabled", lambda: True)

    def send(fn, *args):
        calls.append(fn)
        raise RuntimeError("settleDeposit reverted on-chain (UnknownDeposit)")
    monkeypatch.setattr(chain, "_send", send)
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 0, "reason": ""})
    res = await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "settled" and calls == []

async def test_password_reset_with_emailed_code(client):
    user, old_headers = await signup(client)
    res = await client.post("/api/v1/auth/password/forgot", json={"email": user["email"].upper()})
    assert res.status_code == 200
    code = OUTBOX[f"reset:{user['email']}"]
    bad = await client.post("/api/v1/auth/password/reset", json={"email": user["email"], "code": "000000", "password": "NewPass123"})
    assert bad.status_code == 400 and bad.json()["detail"]["field"] == "code"
    weak = await client.post("/api/v1/auth/password/reset", json={"email": user["email"], "code": code, "password": "short"})
    assert weak.status_code == 400 and weak.json()["detail"]["field"] == "password"
    ok = await client.post("/api/v1/auth/password/reset", json={"email": user["email"], "code": code, "password": "NewPass123"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    again = await client.post("/api/v1/auth/password/reset", json={"email": user["email"], "code": code, "password": "NewPass456"})
    assert again.status_code == 400
    assert (await client.get("/api/v1/users/me", headers=old_headers)).status_code == 401
    login = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "NewPass123"})
    assert login.status_code == 200
    OUTBOX.clear()
    ghost = await client.post("/api/v1/auth/password/forgot", json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"})
    assert ghost.status_code == 200 and OUTBOX == {}

async def test_password_login_is_rate_limited(client):
    user, _ = await signup(client)
    for _ in range(10):
        r = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "wrong-pass-1"})
        assert r.status_code == 401
    blocked = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "Secret123"})
    assert blocked.status_code == 429

async def test_email_cannot_be_changed_without_verification(client):
    user, uh = await signup(client)
    body = {k: user[k] for k in ("firstName", "lastName", "username", "phone", "country")}
    same = await client.put("/api/v1/users/me", headers=uh, json=body | {"email": user["email"]})
    assert same.status_code == 200
    other = await client.put("/api/v1/users/me", headers=uh, json=body | {"email": f"someone_{uuid.uuid4().hex[:6]}@example.com"})
    assert other.status_code == 400 and other.json()["detail"]["field"] == "email"

async def test_listing_photos_must_be_real_images(client):
    owner, oh, listing = await owner_with_listing(client)
    data = {k: listing[k] for k in ("title", "address", "locality", "city", "pincode", "lat", "lng", "rent", "deposit", "bhk",
                                     "furnishing", "area_sqft", "amenities", "preferred_tenants", "available_from",
                                     "min_months", "max_months", "description", "about_owner")}
    data["address"] = "Flat 302, Shanti Residency"
    fake = b"<html><script>alert(1)</script></html>"
    res = await client.post("/api/v1/owner/listings", headers=oh, data={"data": json.dumps(data)},
                            files=[("photos", ("x.png", io.BytesIO(fake), "image/png"))])
    assert res.status_code == 400 and res.json()["detail"]["field"] == "photos"

async def test_razorpay_webhook_completes_payment_when_browser_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "hook-secret")

    async def fake_order(amount, receipt, notes):
        return {"id": f"order_{uuid.uuid4().hex[:10]}"}
    monkeypatch.setattr(payments, "create_order", fake_order)
    user, uh = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "Passport"},
                      files={"file": ("p.jpg", io.BytesIO(b"\xff\xd8\xffpassport"), "image/jpeg")})
    order = (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "month"})).json()
    event = {"event": "payment.captured",
             "payload": {"payment": {"entity": {"id": "pay_123", "order_id": order["orderId"], "status": "captured"}}}}
    raw = json.dumps(event).encode()
    bad = await client.post("/api/v1/payments/razorpay/webhook", content=raw, headers={"X-Razorpay-Signature": "nope"})
    assert bad.status_code == 400
    sig = hmac.new(b"hook-secret", raw, hashlib.sha256).hexdigest()
    for _ in range(2):
        ok = await client.post("/api/v1/payments/razorpay/webhook", content=raw, headers={"X-Razorpay-Signature": sig})
        assert ok.status_code == 200
    me = (await client.get("/api/v1/users/me", headers=uh)).json()["user"]
    assert me["premium"]["planId"] == "month"
    ah = await admin_headers(client)
    pays = (await client.get("/api/v1/admin/premium", headers=ah)).json()["payments"]
    assert sum(1 for p in pays if p["user"]["id"] == user["id"]) == 1

def test_production_refuses_the_public_storage_key(monkeypatch):
    from app.core.config import production_problems
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "STORAGE_MASTER_KEY_HEX", "0123456789abcdef" * 4)
    assert any("STORAGE_MASTER_KEY_HEX" in p for p in production_problems())
    monkeypatch.setattr(settings, "STORAGE_MASTER_KEY_HEX", "abc")
    assert any("STORAGE_MASTER_KEY_HEX" in p for p in production_problems())
    monkeypatch.setattr(settings, "STORAGE_MASTER_KEY_HEX", "ab" * 32)
    assert production_problems() == []

async def test_security_headers(client):
    res = await client.get("/api/v1/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"

async def test_signup_code_requests_are_rate_limited_per_ip(client):
    codes = 0
    for i in range(12):
        r = await client.post("/api/v1/auth/signup/email-code", json=profile(uuid.uuid4().hex[:6]))
        codes += r.status_code == 200
        last = r.status_code
    assert codes == 10 and last == 429

@pytest.mark.parametrize("path", ["/api/v1/users/me/identity"])
async def test_oversized_upload_rejected(client, path, monkeypatch):
    monkeypatch.setattr("app.api.v1.accounts.MAX_DOC_BYTES", 1024)
    _, uh = await signup(client)
    res = await client.post(path, headers=uh, data={"docType": "Passport"},
                            files={"file": ("p.jpg", io.BytesIO(b"x" * 5000), "image/jpeg")})
    assert res.status_code == 400 and res.json()["detail"]["field"] == "file"
