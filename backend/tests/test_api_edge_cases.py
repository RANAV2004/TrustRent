"""Validation, permission and conflict branches of the REST API."""
import io
import json
import uuid
from datetime import timedelta
from PIL import Image
from sqlalchemy import update
from app.api.v1 import messages as messages_api
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.deposits import ConditionPhoto, Deposit
from app.models.marketplace import EmailVerification, Listing, utcnow
from app.models.user import User
from app.services.seed import seed_sample_listings
from tests.test_condition_photos import paid_deposit, upload
from tests.test_live_features import admin_headers
from tests.test_marketplace import PNG, owner_with_listing, profile, signup, slot, tag, with_email_code
def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
async def legacy_login(client, role: str) -> tuple[dict, dict]:
    res = await client.post("/api/v1/auth/login", json={"email": f"{role}_{tag()}@example.com", "name": role.title(), "role": role})
    assert res.status_code == 200, res.text
    return res.json()["user"], bearer(res.json()["access_token"])
async def make_arbitrator() -> tuple[User, dict]:
    """Arbitrators can't sign themselves up, so tests create them directly."""
    from app.models.user import UserRole
    u = User(id=str(uuid.uuid4()), email=f"arb_{tag()}@example.com", name="Arbitrator", role=UserRole.ARBITRATOR,
             provider="password", is_verified=True)
    async with AsyncSessionLocal() as db:
        db.add(u)
        await db.commit()
    return u, bearer(create_access_token(u.id))
async def verify_id(client, headers):
    res = await client.post("/api/v1/users/me/identity", headers=headers, data={"docType": "PAN card"},
                            files={"file": ("pan.jpg", io.BytesIO(b"pan"), "image/jpeg")})
    assert res.status_code == 200
def detail_field(res) -> str | None:
    return res.json()["detail"]["field"]
# --- auth & accounts -------------------------------------------------------
async def test_token_problems(client):
    assert (await client.get("/api/v1/users/me", headers=bearer("garbage"))).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=bearer(create_access_token("no-such-user")))).status_code == 404
    user, h = await signup(client)
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == user["id"]).values(banned_at=utcnow()))
        await db.commit()
    assert (await client.get("/api/v1/users/me", headers=h)).status_code == 403
    login = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "secret123"})
    assert login.status_code == 403
async def test_legacy_wallet_login_updates_wallet(client):
    email = f"w_{tag()}@example.com"
    wallet = "0x" + uuid.uuid4().hex + "0" * 8
    first = await client.post("/api/v1/auth/login", json={"email": email, "name": "W", "role": "tenant"})
    assert first.json()["user"]["wallet_address"] is None
    again = await client.post("/api/v1/auth/login", json={"email": email, "name": "W", "role": "tenant", "smart_account_address": wallet})
    assert again.json()["user"]["id"] == first.json()["user"]["id"] and again.json()["user"]["wallet_address"] == wallet
async def test_profile_validation(client):
    t = tag()
    cases = [
        ({"firstName": " "}, "firstName"), ({"lastName": ""}, "lastName"), ({"username": "No Caps"}, "username"),
        ({"email": "not-an-email"}, "email"), ({"phone": "123"}, "phone"), ({"country": " "}, "country"),
        ({"accountType": "landlord"}, "accountType"),
    ]
    for change, field in cases:
        res = await client.post("/api/v1/auth/signup/email-code", json=profile(t) | change)
        assert res.status_code == 400 and detail_field(res) == field, (change, res.text)
    user, h = await signup(client)
    other, _ = await signup(client)
    taken = await client.put("/api/v1/users/me", headers=h, json=profile(t) | {"phone": other["phone"]})
    assert taken.status_code == 409 and detail_field(taken) == "phone"
    new = profile(t) | {"firstName": "Asha", "lastName": "Rao"}
    updated = await client.put("/api/v1/users/me", headers=h, json=new)
    assert updated.status_code == 200 and updated.json()["user"]["firstName"] == "Asha"
async def test_email_code_expiry_and_attempt_limit(client):
    form = await with_email_code(client, profile(tag()))
    for _ in range(5):
        assert (await client.post("/api/v1/auth/signup", json=form | {"emailCode": "999999"})).status_code == 400
    locked = await client.post("/api/v1/auth/signup", json=form)
    assert locked.status_code == 429
    async with AsyncSessionLocal() as db:
        row = await db.get(EmailVerification, form["email"])
        row.expires_at = utcnow() - timedelta(minutes=1)
        await db.commit()
    expired = await client.post("/api/v1/auth/signup", json=form)
    assert expired.status_code == 400 and "expired" in expired.json()["detail"]["message"]
async def test_account_type_identity_and_premium_rules(client):
    _, h = await signup(client)
    assert (await client.put("/api/v1/users/me/account-type", headers=h, json={"accountType": "boss"})).status_code == 400
    _, ah = await make_arbitrator()
    assert (await client.put("/api/v1/users/me/account-type", headers=ah, json={"accountType": "owner"})).status_code == 403
    bad_doc = await client.post("/api/v1/users/me/identity", headers=h, data={"docType": "Library card"},
                                files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert detail_field(bad_doc) == "docType"
    empty = await client.post("/api/v1/users/me/identity", headers=h, data={"docType": "PAN card"},
                              files={"file": ("x.jpg", io.BytesIO(b""), "image/jpeg")})
    assert detail_field(empty) == "file"
    big = await client.post("/api/v1/users/me/identity", headers=h, data={"docType": "PAN card"},
                            files={"file": ("x.jpg", io.BytesIO(b"0" * (10 * 1024 * 1024 + 1)), "image/jpeg")})
    assert big.status_code == 400 and "10 MB" in big.json()["detail"]["message"]
    await verify_id(client, h)
    assert (await client.post("/api/v1/subscriptions", headers=h, json={"planId": "year"})).status_code == 400
    week = (await client.post("/api/v1/subscriptions", headers=h, json={"planId": "week"})).json()["user"]["premium"]["until"]
    month = (await client.post("/api/v1/subscriptions", headers=h, json={"planId": "month"})).json()["user"]["premium"]["until"]
    assert month > week  # renewals extend the current period
    plans = (await client.get("/api/v1/subscriptions/plans")).json()
    assert [p["id"] for p in plans] == ["week", "month", "quarter"]
    settings_demo = settings.DEMO_MODE
    try:
        settings.DEMO_MODE = False
        assert (await client.post("/api/v1/subscriptions", headers=h, json={"planId": "week"})).status_code == 402
    finally:
        settings.DEMO_MODE = settings_demo
# --- legacy tenancy / evidence / arbitrator API ----------------------------
async def test_tenancy_evidence_and_arbitrator_rules(client):
    landlord, lh = await legacy_login(client, "landlord")
    tenant, th = await legacy_login(client, "tenant")
    _, xh = await legacy_login(client, "tenant")
    arbitrator, arh = await make_arbitrator()
    form = {"property_address": "Flat 1, Indore", "monthly_rent": "10000", "deposit_amount": "20000",
            "deduction_cap": "5000", "claim_window_days": "7", "tenant_email": tenant["email"]}
    lease = {"lease_file": ("lease.pdf", io.BytesIO(b"%PDF lease"), "application/pdf")}
    assert (await client.post("/api/v1/tenancies/draft", headers=th, data=form, files=lease)).status_code == 403
    assert (await client.post("/api/v1/tenancies/draft", headers=lh, data=form | {"deduction_cap": "30000"}, files=lease)).status_code == 400
    assert (await client.post("/api/v1/tenancies/draft", headers=lh, data=form | {"tenant_email": "ghost@x.com"}, files=lease)).status_code == 404
    draft = (await client.post("/api/v1/tenancies/draft", headers=lh, data=form, files=lease)).json()
    tid = draft["tenancy_id"]
    assert draft["claim_window_seconds"] == 7 * 86400
    assert [t["id"] for t in (await client.get("/api/v1/tenancies/", headers=lh)).json()] == [tid]
    assert [t["id"] for t in (await client.get("/api/v1/tenancies/", headers=th)).json()] == [tid]
    assert tid in [t["id"] for t in (await client.get("/api/v1/tenancies/", headers=arh)).json()]
    photo = {"file": ("p.jpg", io.BytesIO(b"photo"), "image/jpeg")}
    assert (await client.post("/api/v1/evidence/upload", headers=th, data={"tenancy_id": "nope", "evidence_type": "move_in"}, files=photo)).status_code == 404
    assert (await client.post("/api/v1/evidence/upload", headers=xh, data={"tenancy_id": tid, "evidence_type": "move_in"}, files=photo)).status_code == 403
    huge = {"file": ("p.jpg", io.BytesIO(b"0" * (10 * 1024 * 1024 + 1)), "image/jpeg")}
    assert (await client.post("/api/v1/evidence/upload", headers=th, data={"tenancy_id": tid, "evidence_type": "move_in"}, files=huge)).status_code == 400
    ev = (await client.post("/api/v1/evidence/upload", headers=th, data={"tenancy_id": tid, "evidence_type": "move_in"}, files=photo)).json()
    assert (await client.get("/api/v1/evidence/nope/verify", headers=th)).status_code == 404
    assert (await client.get("/api/v1/evidence/nope/download", headers=th)).status_code == 404
    assert (await client.get(f"/api/v1/evidence/{ev['evidence_id']}/download", headers=xh)).status_code == 403
    assert (await client.get(f"/api/v1/evidence/{ev['evidence_id']}/download", headers=arh)).content == b"photo"
    from app.models.evidence import Evidence
    async with AsyncSessionLocal() as db:
        await db.execute(update(Evidence).where(Evidence.id == ev["evidence_id"]).values(storage_path="/nonexistent/file"))
        await db.commit()
    assert (await client.get(f"/api/v1/evidence/{ev['evidence_id']}/verify", headers=th)).status_code == 500
    assert (await client.get("/api/v1/arbitrator/disputes", headers=th)).status_code == 403
    assert (await client.get(f"/api/v1/arbitrator/disputes/{tid}", headers=th)).status_code == 403
    disputes = await client.get("/api/v1/arbitrator/disputes", headers=arh)
    assert disputes.status_code == 200 and tid not in [t["id"] for t in disputes.json()]  # drafted, not disputed
    assert (await client.get(f"/api/v1/arbitrator/disputes/{tid}", headers=arh)).json()["id"] == tid
    assert (await client.get("/api/v1/arbitrator/disputes/nope", headers=arh)).status_code == 404
    assert (await client.post("/api/v1/faucet/", headers=th, json={"recipient_address": "0x123"})).status_code == 400
    short = await client.post("/api/v1/identity/verify", headers=th, json={"full_name": "a", "id_type": "x", "id_number": "123", "phone": "1"})
    assert short.status_code == 400
# --- owner verification & listings -----------------------------------------
async def test_owner_application_rules(client):
    owner, oh = await signup(client, "owner")
    assert (await client.get("/api/v1/owner/application", headers=oh)).json() == {"application": None}
    base = {"relation": "owner", "idDocType": "Masked Aadhaar card", "propertyDocType": "Sale deed / title deed",
            "propertyAddress": "Flat 302, Shanti Residency, Indore"}
    files = lambda: {"idFile": ("id.jpg", io.BytesIO(b"id"), "image/jpeg"),  # noqa: E731
                     "propertyFile": ("deed.pdf", io.BytesIO(b"deed"), "application/pdf")}
    for change, field in [({"relation": "tenant"}, "relation"), ({"idDocType": "x"}, "idDocType"),
                          ({"propertyDocType": "x"}, "propertyDocType"), ({"propertyAddress": "short"}, "propertyAddress")]:
        res = await client.post("/api/v1/owner/application", headers=oh, data=base | change, files=files())
        assert detail_field(res) == field
    empty = await client.post("/api/v1/owner/application", headers=oh, data=base,
                              files={"idFile": ("id.jpg", io.BytesIO(b""), "image/jpeg"),
                                     "propertyFile": ("deed.pdf", io.BytesIO(b"deed"), "application/pdf")})
    assert detail_field(empty) == "idFile"
    huge = await client.post("/api/v1/owner/application", headers=oh, data=base,
                             files={"idFile": ("id.jpg", io.BytesIO(b"id"), "image/jpeg"),
                                    "propertyFile": ("d.pdf", io.BytesIO(b"0" * (10 * 1024 * 1024 + 1)), "application/pdf")})
    assert detail_field(huge) == "propertyFile"
    assert (await client.post("/api/v1/owner/application", headers=oh, data=base, files=files())).status_code == 201
    _, sh = await signup(client)
    assert (await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=sh, json={"approve": True})).status_code == 403
    ah = await admin_headers(client)
    assert (await client.post("/api/v1/owner/application/nobody/review", headers=ah, json={"approve": True})).status_code == 404
    rejected = await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=ah, json={"approve": False})
    assert rejected.json()["application"]["status"] == "rejected" and rejected.json()["application"]["reviewNote"]
    doc = await client.get(f"/api/v1/admin/owner-applications/{owner['id']}/property", headers=ah)
    assert doc.content == b"deed" and doc.headers["content-type"] == "application/pdf"
    assert (await client.get(f"/api/v1/admin/owner-applications/{owner['id']}/other", headers=ah)).status_code == 404
    resubmit = await client.post("/api/v1/owner/application", headers=oh, data=base, files=files())
    assert resubmit.json()["application"]["status"] == "submitted"
    await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=ah, json={"approve": True})
    assert (await client.post("/api/v1/owner/application", headers=oh, data=base, files=files())).status_code == 409
async def test_admin_identity_review_rules(client):
    ah = await admin_headers(client)
    assert (await client.get("/api/v1/admin/identity/nope/file", headers=ah)).status_code == 404
    assert (await client.post("/api/v1/admin/identity/nope/review", headers=ah, json={"approve": True})).status_code == 404
    user, uh = await signup(client)
    await verify_id(client, uh)
    sub = next(s for s in (await client.get("/api/v1/admin/verifications", headers=ah)).json()["identities"] if s["userId"] == user["id"])
    rej = await client.post(f"/api/v1/admin/identity/{sub['id']}/review", headers=ah, json={"approve": False, "note": "Blurry"})
    assert rej.json()["submission"]["reviewNote"] == "Blurry"
    assert (await client.get("/api/v1/users/me", headers=uh)).json()["user"]["idVerified"] is False
LISTING = {
    "title": "Bright 1 BHK near the park", "address": "House 12, Palasia", "locality": "Palasia", "city": "Indore",
    "pincode": "452001", "lat": 22.72, "lng": 75.87, "rent": 9000, "deposit": 18000, "bhk": 1,
    "furnishing": "furnished", "available_from": "2026-12-01", "min_months": 6, "max_months": 12,
    "description": "Quiet lane, close to the market and the bus stop, with morning sun.",
}
def photos(n=1, kind="image/png", data=PNG):
    return [("photos", (f"{i}.png", io.BytesIO(data), kind)) for i in range(n)]
async def test_listing_validation_status_and_delete(client):
    owner, oh, listing = await owner_with_listing(client)
    async def create(data, files=None):
        raw = data if isinstance(data, str) else json.dumps(data)
        return await client.post("/api/v1/owner/listings", headers=oh, data={"data": raw}, files=files or photos())
    assert (await create("{not json")).json()["detail"]["message"] == "Listing data is not valid JSON."
    assert detail_field(await create(LISTING | {"pincode": "12"})) == "pincode"
    assert detail_field(await create(LISTING | {"furnishing": "luxury"})) == "furnishing"
    assert detail_field(await create(LISTING | {"max_months": 3})) == "max_months"
    assert detail_field(await create(LISTING | {"amenities": ["helipad"]})) == "amenities"
    assert detail_field(await create(LISTING, photos(9))) == "photos"
    assert detail_field(await create(LISTING, photos(1, "image/gif"))) == "photos"
    assert detail_field(await create(LISTING, photos(1, data=b"0" * (5 * 1024 * 1024 + 1)))) == "photos"
    fresh = await create(LISTING)
    assert fresh.status_code == 201
    lid = fresh.json()["id"]
    mine = (await client.get("/api/v1/owner/listings", headers=oh)).json()
    assert {x["id"] for x in mine} == {listing["id"], lid}
    _, sh = await signup(client)
    assert (await client.get("/api/v1/listings/nope", headers=sh)).status_code == 404
    assert (await client.patch(f"/api/v1/owner/listings/{lid}", headers=oh, json={"status": "sold"})).status_code == 400
    assert (await client.patch(f"/api/v1/owner/listings/{lid}", headers=sh, json={"status": "live"})).status_code == 404
    ah = await admin_headers(client)
    await client.post(f"/api/v1/admin/listings/{lid}/unlist", headers=ah, json={"reason": "Wrong photos"})
    blocked = await client.patch(f"/api/v1/owner/listings/{lid}", headers=oh, json={"status": "live"})
    assert blocked.status_code == 403 and "Wrong photos" in blocked.json()["detail"]["message"]
    assert (await client.get(f"/api/v1/listings/{lid}", headers=sh)).status_code == 404
    assert (await client.get(f"/api/v1/listings/{lid}", headers=oh)).status_code == 200
    assert (await client.delete(f"/api/v1/owner/listings/{lid}", headers=sh)).status_code == 404
    assert (await client.delete(f"/api/v1/owner/listings/{lid}", headers=oh)).status_code == 204
    async with AsyncSessionLocal() as db:
        assert await db.get(Listing, lid) is None
    await verify_id(client, sh)
    await client.post("/api/v1/subscriptions", headers=sh, json={"planId": "week"})
    await client.post("/api/v1/conversations", headers=sh, json={"listingId": listing["id"]})
    assert (await client.delete(f"/api/v1/owner/listings/{listing['id']}", headers=oh)).status_code == 204
    async with AsyncSessionLocal() as db:
        assert (await db.get(Listing, listing["id"])).status == "removed"  # kept for the chat history
    assert (await client.post(f"/api/v1/admin/listings/{listing['id']}/relist", headers=ah)).status_code == 404
async def test_banned_owner_listing_hidden(client):
    owner, oh, listing = await owner_with_listing(client)
    _, sh = await signup(client)
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == owner["id"]).values(banned_at=utcnow()))
        await db.commit()
    assert (await client.get(f"/api/v1/listings/{listing['id']}", headers=sh)).status_code == 404
# --- messages ---------------------------------------------------------------
async def test_message_rules(client):
    owner, oh, listing = await owner_with_listing(client)
    _, sh = await signup(client)
    await verify_id(client, sh)
    await client.post("/api/v1/subscriptions", headers=sh, json={"planId": "week"})
    assert (await client.post("/api/v1/conversations", headers=sh, json={"listingId": "nope"})).status_code == 404
    assert (await client.post("/api/v1/conversations", headers=oh, json={"listingId": listing["id"]})).status_code == 400
    cid = (await client.post("/api/v1/conversations", headers=sh, json={"listingId": listing["id"]})).json()["id"]
    url = f"/api/v1/conversations/{cid}/messages"
    _, xh = await signup(client)
    assert (await client.post(url, headers=xh, json={"kind": "text", "text": "hi"})).status_code == 404
    assert detail_field(await client.post(url, headers=sh, json={"kind": "text", "text": "   "})) == "text"
    assert detail_field(await client.post(url, headers=sh, json={"kind": "sticker"})) == "kind"
    assert detail_field(await client.post(url, headers=sh, json={"kind": "visit", "slots": []})) == "slots"
    assert detail_field(await client.post(url, headers=sh, json={"kind": "visit", "slots": ["tomorrow"]})) == "slots"
    assert (await client.post(url, headers=oh, json={"kind": "visit", "slots": [slot()]})).status_code == 403
    reply = await client.post(url, headers=oh, json={"kind": "text", "text": "Yes, it's available"})
    assert reply.status_code == 201
    visit = (await client.post(url, headers=sh, json={"kind": "visit", "slots": [slot(1), slot(2)]})).json()
    vurl = f"/api/v1/messages/{visit['id']}/visit-response"
    assert (await client.post("/api/v1/messages/nope/visit-response", headers=oh, json={"accept": True})).status_code == 404
    assert (await client.post(f"/api/v1/messages/{reply.json()['id']}/visit-response", headers=oh, json={"accept": True})).status_code == 404
    assert detail_field(await client.post(vurl, headers=oh, json={"accept": True, "slot": slot(5)})) == "slot"
    declined = await client.post(vurl, headers=oh, json={"accept": False})
    assert declined.json()["visit"]["status"] == "declined"
    assert (await client.post(vurl, headers=oh, json={"accept": False})).status_code == 409
    for h in (sh, oh):
        assert (await client.post(f"/api/v1/conversations/{cid}/read", headers=h)).json() == {"ok": True}
    inbox = (await client.get("/api/v1/inbox", headers=xh)).json()
    assert inbox == {"conversations": [], "messages": []}
    admin = await admin_headers(client)
    chats = (await client.get("/api/v1/admin/conversations", headers=admin)).json()
    assert any(c["id"] == cid for c in chats)
    msgs = (await client.get(f"/api/v1/admin/conversations/{cid}/messages", headers=admin)).json()
    assert {m["from"] for m in msgs} == {"seeker", "owner"}
    assert (await client.get("/api/v1/admin/conversations/nope/messages", headers=admin)).status_code == 404
async def test_demo_owner_greets_once(client, monkeypatch):
    monkeypatch.setattr(messages_api, "DEMO_REPLY_DELAY_SECONDS", 0)
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)
    _, sh = await signup(client)
    cid = (await client.post("/api/v1/conversations", headers=sh, json={"listingId": "IND-VN-101"})).json()["id"]
    for text in ("Hello", "Still there?"):
        await client.post(f"/api/v1/conversations/{cid}/messages", headers=sh, json={"kind": "text", "text": text})
    msgs = [m for m in (await client.get("/api/v1/inbox", headers=sh)).json()["messages"] if m["conversationId"] == cid]
    greetings = [m for m in msgs if "Thanks for your interest" in (m.get("text") or "")]
    assert len(greetings) == 1
    await messages_api.demo_owner_reply("no-such-conversation", "no-such-message")
# --- deposits, payments & condition photos ----------------------------------
async def test_deposit_permission_and_state_rules(client):
    dep_id, th, oh = await paid_deposit(client)
    _, xh = await signup(client)
    assert (await client.get(f"/api/v1/deposits/{dep_id}", headers=xh)).status_code == 404
    assert (await client.get("/api/v1/deposits/DEP-NOPE", headers=th)).status_code == 404
    assert (await client.get("/api/v1/deposits/lookup", headers=th, params={"q": "0x" + "f" * 64})).status_code == 404
    assert (await client.get("/api/v1/deposits/lookup", headers=th, params={"q": "hello"})).status_code == 404
    assert (await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=th, json={"deducted": 0})).status_code == 403
    short = await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 100, "reason": "dirty"})
    assert detail_field(short) == "reason"
    assert (await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})).status_code == 409
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 0})
    assert (await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=oh, json={"accept": True})).status_code == 403
    await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})
    assert (await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 0})).status_code == 409
    ah = await admin_headers(client)
    assert (await client.post(f"/api/v1/admin/deposits/{dep_id}/settle", headers=ah, json={"deducted": 0})).status_code == 409
    assert (await client.post(f"/api/v1/admin/deposits/{dep_id}/owner-paid", headers=ah)).status_code == 409
async def test_payment_order_rules(client):
    owner, oh, listing = await owner_with_listing(client)
    _, uh = await signup(client)
    await verify_id(client, uh)
    await verify_id(client, oh)
    assert detail_field(await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "donation"})) == "purpose"
    assert detail_field(await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "x"})) == "planId"
    assert (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "deposit", "listingId": "nope"})).status_code == 404
    own = await client.post("/api/v1/payments/order", headers=oh, json={"purpose": "deposit", "listingId": listing["id"]})
    assert own.status_code == 400
    order = (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "week"})).json()
    settings_demo = settings.DEMO_MODE
    try:
        settings.DEMO_MODE = False
        off = await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": order["orderId"]})
        assert off.status_code == 400
    finally:
        settings.DEMO_MODE = settings_demo
async def test_offline_deposit_rules(client):
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await signup(client)
    ah = await admin_headers(client)
    body = {"tenant": tenant["username"], "listingId": listing["id"], "amount": 20000, "transactionId": f"UPI-{tag()}"}
    missing = await client.post("/api/v1/admin/deposits", headers=ah, json=body | {"listingId": "IND-NOPE"})
    assert missing.status_code == 404 and detail_field(missing) == "listingId"
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == tenant["id"]).values(banned_at=utcnow()))
        await db.commit()
    assert (await client.post("/api/v1/admin/deposits", headers=ah, json=body)).status_code == 409
async def test_admin_console_guards_and_delete_owner(client):
    ah = await admin_headers(client)
    me = (await client.get("/api/v1/users/me", headers=ah)).json()["user"]
    _, arh = await make_arbitrator()
    owner, oh, listing = await owner_with_listing(client)
    assert (await client.get("/api/v1/admin/users", headers=arh)).status_code == 200
    assert (await client.post(f"/api/v1/admin/users/{owner['id']}/ban", headers=arh, json={})).status_code == 403
    assert (await client.post("/api/v1/admin/users/nobody/ban", headers=ah, json={})).status_code == 404
    assert (await client.delete(f"/api/v1/admin/users/{me['id']}", headers=ah)).status_code == 403
    assert (await client.post("/api/v1/admin/listings/nope/unlist", headers=ah, json={})).status_code == 404
    assert (await client.delete(f"/api/v1/admin/users/{owner['id']}", headers=ah)).json() == {"ok": True}
    async with AsyncSessionLocal() as db:
        gone = await db.get(Listing, listing["id"])
        assert gone.status == "removed" and gone.admin_note == "Owner account deleted"
    users = {u["id"]: u for u in (await client.get("/api/v1/admin/users", headers=ah)).json()}
    assert users[owner["id"]]["deletedAt"] and users[owner["id"]]["banned"] is None
    assert (await client.post(f"/api/v1/admin/users/{owner['id']}/unban", headers=ah)).status_code == 404
    rows = {x["id"]: x for x in (await client.get("/api/v1/admin/listings", headers=ah)).json()}
    assert rows[listing["id"]]["status"] == "removed"
    assert (await client.post(f"/api/v1/admin/premium/{owner['id']}/revoke", headers=ah)).status_code == 404
    overview = (await client.get("/api/v1/admin/overview", headers=ah)).json()
    assert overview["users"]["deleted"] >= 1
def png_photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (10, 10), (0, 0, 255, 128)).save(out, format="PNG")
    return out.getvalue()
async def test_condition_photo_rules(client, monkeypatch):
    dep_id, th, oh = await paid_deposit(client)
    res = await upload(client, dep_id, th, data=png_photo())  # RGBA converted to JPEG
    assert res.status_code == 201
    pid = res.json()["id"]
    assert detail_field(await upload(client, dep_id, th, stage="moving_day")) == "stage"
    assert (await upload(client, dep_id, th, stage="move_out")).status_code == 201
    empty = await client.post(f"/api/v1/deposits/{dep_id}/photos", headers=th, data={"stage": "move_in", "room": "Kitchen"},
                              files={"file": ("e.jpg", io.BytesIO(b""), "image/jpeg")})
    assert detail_field(empty) == "file"
    huge = await upload(client, dep_id, th, data=b"0" * (10 * 1024 * 1024 + 1))
    assert huge.status_code == 400 and "10 MB" in huge.json()["detail"]["message"]
    from app.api.v1 import condition
    monkeypatch.setattr(condition, "MAX_PER_STAGE", 1)
    assert (await upload(client, dep_id, th)).status_code == 409
    assert (await client.get(f"/api/v1/deposits/{dep_id}/photos/nope/file", headers=th)).status_code == 404
    async with AsyncSessionLocal() as db:
        await db.execute(update(ConditionPhoto).where(ConditionPhoto.id == pid).values(file_path="/nonexistent/photo"))
        await db.commit()
    assert (await client.get(f"/api/v1/deposits/{dep_id}/photos/{pid}/file", headers=th)).status_code == 410
    ah = await admin_headers(client)
    assert (await upload(client, dep_id, ah)).status_code == 403
    async with AsyncSessionLocal() as db:
        assert (await db.get(Deposit, dep_id)).status == "held"
