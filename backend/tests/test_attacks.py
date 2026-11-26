"""Each test plays an attacker from the launch checklist and checks they get nowhere."""
import hashlib
import hmac
import io
import uuid
from openpyxl import load_workbook
from app.core.config import settings
from app.services import payments
from tests.mailbox import OUTBOX
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, profile, signup

JPG = b"\xff\xd8\xffphoto"


# 1. Typing /admin: every admin API refuses normal users (the page itself shows "only for admins").
async def test_admin_api_refuses_normal_users(client):
    _, uh = await signup(client)
    some = str(uuid.uuid4())
    for method, path in [
        ("get", "/admin/overview"), ("get", "/admin/users"), ("get", "/admin/listings"), ("get", "/admin/conversations"),
        ("get", "/admin/premium"), ("get", "/admin/ledger"), ("get", "/admin/deposits"), ("get", "/admin/verifications"),
        ("get", "/admin/legal"), ("get", "/admin/verification-register.xlsx"), ("get", f"/admin/identity/{some}/file"),
        ("post", f"/admin/users/{some}/ban"), ("delete", f"/admin/users/{some}"), ("post", f"/admin/premium/{some}/revoke"),
        ("post", "/admin/legal/applications/LAW-1/review"), ("post", f"/admin/legal/lawyers/{some}/reset-password"),
        ("post", "/admin/deposits/DEP-1/settle"),
    ]:
        kw = {"json": {"reason": "x", "approve": True, "deducted": 0}} if method == "post" else {}
        res = await getattr(client, method)(f"/api/v1{path}", headers=uh, **kw)
        assert res.status_code == 403, (path, res.status_code)
    assert (await client.get("/api/v1/admin/overview")).status_code in (401, 403)  # no token at all


# 2. Changing an ID in the URL: other people's records stay hidden.
async def test_changing_ids_in_the_url(client):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    dep_id = (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})).json()["depositId"]
    conv_id = (await client.get("/api/v1/inbox", headers=th)).json()["conversations"][0]["id"]
    _, xh = await signup(client)
    assert (await client.get(f"/api/v1/deposits/{dep_id}", headers=xh)).status_code == 404
    assert (await client.get(f"/api/v1/deposits/{dep_id}/photos", headers=xh)).status_code == 404
    assert (await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=xh, json={"deducted": 0})).status_code == 403
    assert (await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=xh, json={"accept": True})).status_code == 403
    assert (await client.post(f"/api/v1/conversations/{conv_id}/messages", headers=xh, json={"text": "hi"})).status_code == 404
    assert (await client.post(f"/api/v1/conversations/{conv_id}/read", headers=xh)).status_code == 404
    assert (await client.patch(f"/api/v1/owner/listings/{listing['id']}", headers=xh, json={"status": "paused"})).status_code == 404
    assert (await client.delete(f"/api/v1/owner/listings/{listing['id']}", headers=xh)).status_code == 404
    assert (await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=xh, json={"approve": True})).status_code == 403
    # the inbox only ever contains your own chats
    assert (await client.get("/api/v1/inbox", headers=xh)).json()["conversations"] == []
    # verify an order that belongs to someone else
    other = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "premium", "planId": "week"})
    assert (await client.post("/api/v1/payments/verify", headers=xh, json={"orderId": other.json()["orderId"]})).status_code == 404


# 3. Editing prices in the browser: the server ignores any amount it is sent.
async def test_prices_come_from_the_server(client):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    for body in ({"purpose": "premium", "planId": "quarter", "amount": 1, "price": 1},
                 {"purpose": "deposit", "listingId": listing["id"], "amount": 1}):
        res = await client.post("/api/v1/payments/order", headers=th, json=body)
        assert res.json()["amount"] == (699 if body["purpose"] == "premium" else 34000)
    assert (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "premium", "planId": "free"})).status_code == 400
    assert (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "gift"})).status_code == 400


# 4. Faking a payment on the live site (demo mode off, Razorpay on).
async def test_fake_payments_are_refused_live(client, monkeypatch):
    _, uh = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("pan.jpg", io.BytesIO(JPG), "image/jpeg")})
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_live_x")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "real-secret")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "hook-secret")

    async def fake_order(amount, receipt, notes):
        return {"id": f"order_{uuid.uuid4().hex[:10]}"}
    monkeypatch.setattr(payments, "create_order", fake_order)
    # the old demo shortcuts are off
    assert (await client.post("/api/v1/subscriptions", headers=uh, json={"planId": "month"})).status_code == 402
    order = (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "month"})).json()
    assert order["provider"] == "razorpay"
    for forged in ({}, {"paymentId": "pay_1", "signature": "0" * 64},
                   {"paymentId": "pay_1", "signature": hmac.new(b"guessed", f"{order['orderId']}|pay_1".encode(), hashlib.sha256).hexdigest()}):
        res = await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": order["orderId"]} | forged)
        assert res.status_code == 400
    raw = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_1","order_id":"%s"}}}}' % order["orderId"].encode()
    assert (await client.post("/api/v1/payments/razorpay/webhook", content=raw, headers={"X-Razorpay-Signature": "f" * 64})).status_code == 400
    assert (await client.get("/api/v1/users/me", headers=uh)).json()["user"]["premium"] is None
    # with the real secret's signature it goes through (what Razorpay sends)
    good = hmac.new(b"real-secret", f"{order['orderId']}|pay_1".encode(), hashlib.sha256).hexdigest()
    ok = await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": order["orderId"], "paymentId": "pay_1", "signature": good})
    assert ok.status_code == 200 and ok.json()["user"]["premium"]["planId"] == "month"


# 5. Making yourself admin at sign-up.
async def test_cannot_become_admin_or_lawyer_at_sign_up(client):
    t = uuid.uuid4().hex[:6]
    form = profile(t) | {"isAdmin": True, "role": "arbitrator", "is_lawyer": True, "idVerified": True, "premium": {"planId": "quarter"}}
    await client.post("/api/v1/auth/signup/email-code", json=form)
    res = await client.post("/api/v1/auth/signup", json=form | {"emailCode": OUTBOX[form["email"].lower()]})
    me = res.json()["user"]
    assert res.status_code == 201 and me["isAdmin"] is False and me["role"] == "tenant"
    assert me["accountType"] == "seeker" and me["idVerified"] is False and me["premium"] is None
    for kind in ("admin", "lawyer", "arbitrator"):
        bad = await client.post("/api/v1/auth/signup/email-code", json=profile(uuid.uuid4().hex[:6]) | {"accountType": kind})
        assert bad.status_code == 400
    uh = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert (await client.put("/api/v1/users/me/account-type", headers=uh, json={"accountType": "lawyer"})).status_code == 400
    await admin_headers(client)
    taken = await client.post("/api/v1/auth/signup/email-code", json=profile(uuid.uuid4().hex[:6]) | {"email": settings.ADMIN_EMAILS[0].upper()})
    assert taken.status_code == 409


# 6. Guessing codes and passwords.
async def test_guessing_codes_is_capped(client):
    t = uuid.uuid4().hex[:6]
    form = profile(t)
    await client.post("/api/v1/auth/signup/email-code", json=form)
    codes = [f"{i:06d}" for i in range(6)]
    statuses = [(await client.post("/api/v1/auth/signup", json=form | {"emailCode": c})).status_code for c in codes]
    assert statuses[-1] == 429  # the code dies after 5 wrong tries
    user, _ = await signup(client)
    sent = 0
    for _ in range(8):  # a fresh code every time: still only 5 a day reach the inbox
        from app.core.ratelimit import EMAILS_PER_IP
        EMAILS_PER_IP.reset()
        from app.models.marketplace import EmailVerification
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:  # skip the one-a-minute wait
            row = await db.get(EmailVerification, f"reset:{user['email']}")
            if row:
                await db.delete(row)
                await db.commit()
        OUTBOX.pop(f"reset:{user['email']}", None)
        await client.post("/api/v1/auth/password/forgot", json={"email": user["email"]})
        sent += f"reset:{user['email']}" in OUTBOX
    assert sent == 5


# 7. Putting a script in your username or name.
async def test_scripts_in_names_are_refused(client):
    for field, value in (("username", "<script>alert(1)</script>"), ("username", "a'; DROP TABLE users;--"),
                         ("firstName", "<img src=x onerror=alert(1)>"), ("lastName", "=HYPERLINK(\"http://evil\")"),
                         ("firstName", "Robert'); DROP TABLE users;--")):
        res = await client.post("/api/v1/auth/signup/email-code", json=profile(uuid.uuid4().hex[:6]) | {field: value})
        assert res.status_code == 400 and res.json()["detail"]["field"] == field, (field, value)
    ok = await client.post("/api/v1/auth/signup/email-code", json=profile(uuid.uuid4().hex[:6]) | {"firstName": "Anne-Marie", "lastName": "D'Souza"})
    assert ok.status_code == 200
    hindi = await client.post("/api/v1/auth/signup/email-code", json=profile(uuid.uuid4().hex[:6]) | {"firstName": "प्रिया", "lastName": "शर्मा"})
    assert hindi.status_code == 200


async def test_excel_register_never_holds_formulas(client, monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.services.register import rebuild_register
    user, uh = await signup(client)
    async with AsyncSessionLocal() as db:  # e.g. a name that came from Google sign-in
        u = await db.get(User, user["id"])
        u.first_name, u.last_name = '=HYPERLINK("http://evil","Click")', "x"
        await db.commit()
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("p.jpg", io.BytesIO(JPG), "image/jpeg")})
    async with AsyncSessionLocal() as db:
        path = await rebuild_register(db)
    ws = load_workbook(path)["ID verification"]
    assert all(c.data_type != "f" for row in ws.iter_rows() for c in row)


# 8. Uploading something that isn't a photo or document.
async def test_non_photos_are_refused_everywhere(client):
    owner, oh, listing = await owner_with_listing(client)
    html = b"<html><script>alert(1)</script></html>"
    _, uh = await signup(client)
    res = await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                            files={"file": ("pan.jpg", io.BytesIO(html), "image/jpeg")})
    assert res.status_code == 400
    exe = await client.post("/api/v1/owner/application", headers=uh,
                            data={"relation": "owner", "idDocType": "PAN card", "propertyDocType": "Sale deed / title deed",
                                  "propertyAddress": "Flat 1, Some Building, Indore 452001"},
                            files={"idFile": ("id.jpg", io.BytesIO(b"MZ\x90\x00windows-program"), "image/jpeg"),
                                   "propertyFile": ("deed.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
    assert exe.status_code == 400 and exe.json()["detail"]["field"] == "idFile"
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    dep_id = (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})).json()["depositId"]
    photo = await client.post(f"/api/v1/deposits/{dep_id}/photos", headers=th, data={"stage": "move_in", "room": "Kitchen"},
                              files={"file": ("k.jpg", io.BytesIO(html), "image/jpeg")})
    assert photo.status_code == 400


# 9. Querying the database through inputs (SQL injection).
async def test_sql_injection_attempts_do_nothing(client):
    user, uh = await signup(client)
    for ident in ("' OR '1'='1", "admin'--", "\" OR 1=1 --"):
        res = await client.post("/api/v1/auth/password-login", json={"identifier": ident, "password": "' OR '1'='1"})
        assert res.status_code == 401
    for q in ("DEP-' OR 1=1--", "0x' UNION SELECT * FROM users--"):
        assert (await client.get("/api/v1/deposits/lookup", headers=uh, params={"q": q})).status_code == 404
    assert (await client.get("/api/v1/listings/x' OR '1'='1", headers=uh)).status_code == 404
    assert (await client.get("/api/v1/lawyers/applications/status", params={"reference": "' OR 1=1--", "email": "a@b.c"})).status_code == 404
    assert (await client.get("/api/v1/users/me", headers=uh)).status_code == 200  # the table is still there
