import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from app.api.v1 import messages as messages_api
from app.core.database import AsyncSessionLocal
from app.services.seed import seed_sample_listings
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
       b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
def tag() -> str:
    return uuid.uuid4().hex[:6]
def profile(t: str, account: str = "seeker", phone_tail: int | None = None) -> dict:
    return {
        "firstName": "Riya", "lastName": "Sharma", "username": f"user_{t}", "email": f"user_{t}@example.com",
        "phone": f"+91 9{phone_tail or int(t, 16) % 10**9:09d}", "country": "India",
        "password": "secret123", "accountType": account,
    }
def slot(days: int = 2) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
async def with_email_code(client: AsyncClient, p: dict) -> dict:
    from tests.mailbox import OUTBOX
    res = await client.post("/api/v1/auth/signup/email-code", json=p)
    assert res.status_code == 200, res.text
    return p | {"emailCode": OUTBOX[res.json()["email"]]}
async def signup(client: AsyncClient, account: str = "seeker") -> tuple[dict, dict]:
    res = await client.post("/api/v1/auth/signup", json=await with_email_code(client, profile(tag(), account)))
    assert res.status_code == 201, res.text
    body = res.json()
    return body["user"], {"Authorization": f"Bearer {body['access_token']}"}
async def test_signup_login_and_profile(client):
    t = tag()
    no_code = await client.post("/api/v1/auth/signup", json=profile(t))
    assert no_code.status_code == 400 and no_code.json()["detail"]["field"] == "emailCode"
    form = await with_email_code(client, profile(t))
    wrong = await client.post("/api/v1/auth/signup", json=form | {"emailCode": "000000"})
    assert wrong.status_code == 400 and wrong.json()["detail"]["field"] == "emailCode"
    res = await client.post("/api/v1/auth/signup", json=form)
    assert res.status_code == 201
    again = await client.post("/api/v1/auth/signup/email-code", json={**profile(tag()), "email": f"USER_{t}@example.com"})
    assert again.status_code == 409 and again.json()["detail"]["field"] == "email"
    user = res.json()["user"]
    assert user["accountType"] == "seeker" and user["premium"] is None and user["username"] == f"user_{t}"
    dup = await client.post("/api/v1/auth/signup", json={**profile(t), "email": f"other_{t}@example.com"})
    assert dup.status_code == 409 and dup.json()["detail"]["field"] == "username"
    weak = await client.post("/api/v1/auth/signup", json={**profile(tag()), "password": "short"})
    assert weak.status_code == 400 and weak.json()["detail"]["field"] == "password"
    bad = await client.post("/api/v1/auth/password-login", json={"identifier": f"user_{t}", "password": "wrong123"})
    assert bad.status_code == 401
    ok = await client.post("/api/v1/auth/password-login", json={"identifier": f"USER_{t}@example.com", "password": "secret123"})
    assert ok.status_code == 200
    headers = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.json()["user"]["id"] == user["id"]
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
    switched = await client.put("/api/v1/users/me/account-type", headers=headers, json={"accountType": "owner"})
    assert switched.json()["user"]["accountType"] == "owner"
async def test_google_demo(client):
    g = await client.post("/api/v1/auth/google", json={"email": f"g_{tag()}@gmail.com"})
    assert g.status_code == 200 and g.json()["user"]["provider"] == "google"
async def test_premium_needs_identity(client):
    _, headers = await signup(client)
    early = await client.post("/api/v1/subscriptions", headers=headers, json={"planId": "month"})
    assert early.status_code == 403
    idv = await client.post("/api/v1/users/me/identity", headers=headers, data={"docType": "PAN card"},
                            files={"file": ("pan.jpg", io.BytesIO(b"fake-pan-image"), "image/jpeg")})
    assert idv.status_code == 200 and idv.json()["user"]["idVerified"] is True
    sub = await client.post("/api/v1/subscriptions", headers=headers, json={"planId": "month"})
    assert sub.status_code == 200
    assert sub.json()["user"]["premium"]["planId"] == "month"
async def owner_with_listing(client: AsyncClient) -> tuple[dict, dict, dict]:
    owner, oh = await signup(client, "owner")
    blocked = await client.post("/api/v1/owner/listings", headers=oh, data={"data": "{}"},
                                files=[("photos", ("a.png", io.BytesIO(PNG), "image/png"))])
    assert blocked.status_code == 403
    app_res = await client.post(
        "/api/v1/owner/application", headers=oh,
        data={"relation": "owner", "idDocType": "Masked Aadhaar card", "propertyDocType": "Sale deed / title deed",
              "propertyAddress": "Flat 302, Shanti Residency, Vijay Nagar, Indore 452010"},
        files={"idFile": ("aadhaar.jpg", io.BytesIO(b"id"), "image/jpeg"),
               "propertyFile": ("deed.pdf", io.BytesIO(b"deed"), "application/pdf")},
    )
    assert app_res.status_code == 201 and app_res.json()["application"]["status"] == "submitted"
    approved = await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=oh, json={"approve": True})
    assert approved.json()["application"]["status"] == "approved"
    data = {
        "title": "Sunny 2 BHK near C21 Mall", "address": "Flat 302, Shanti Residency", "locality": "Vijay Nagar",
        "city": "Indore", "pincode": "452010", "lat": 22.753312, "lng": 75.893711, "show_exact_location": False,
        "rent": 17000, "deposit": 34000, "bhk": 2, "furnishing": "semi-furnished", "area_sqft": 950,
        "amenities": ["parking", "lift"], "preferred_tenants": ["any"], "available_from": "2026-11-15",
        "min_months": 11, "max_months": 22,
        "description": "Corner flat with cross ventilation, 24x7 water and covered parking.",
        "about_owner": "I live nearby.",
    }
    res = await client.post("/api/v1/owner/listings", headers=oh, data={"data": json.dumps(data)},
                            files=[("photos", ("1.png", io.BytesIO(PNG), "image/png")),
                                   ("photos", ("2.png", io.BytesIO(PNG), "image/png"))])
    assert res.status_code == 201, res.text
    listing = res.json()
    assert listing["id"].startswith("TR-") and len(listing["photos"]) == 2
    assert listing["photos"][0].startswith("http://test/media/listings/")
    return owner, oh, listing
async def test_owner_listing_early_access_and_visit(client):
    owner, oh, listing = await owner_with_listing(client)
    seeker, sh = await signup(client)
    seen = (await client.get(f"/api/v1/listings/{listing['id']}", headers=sh)).json()
    assert seen["address"] is None and seen["lat"] == 22.75
    locked = await client.post("/api/v1/conversations", headers=sh, json={"listingId": listing["id"]})
    assert locked.status_code == 403
    await client.post("/api/v1/users/me/identity", headers=sh, data={"docType": "Passport"},
                      files={"file": ("p.jpg", io.BytesIO(b"passport"), "image/jpeg")})
    await client.post("/api/v1/subscriptions", headers=sh, json={"planId": "week"})
    conv = await client.post("/api/v1/conversations", headers=sh, json={"listingId": listing["id"]})
    assert conv.status_code == 200
    cid = conv.json()["id"]
    again = await client.post("/api/v1/conversations", headers=sh, json={"listingId": listing["id"]})
    assert again.json()["id"] == cid
    await client.post(f"/api/v1/conversations/{cid}/messages", headers=sh, json={"kind": "text", "text": "Is it available?"})
    past = await client.post(f"/api/v1/conversations/{cid}/messages", headers=sh,
                             json={"kind": "visit", "slots": ["2020-01-01T10:00:00Z"]})
    assert past.status_code == 400
    visit = await client.post(f"/api/v1/conversations/{cid}/messages", headers=sh,
                              json={"kind": "visit", "slots": [slot(1), slot(2)], "text": "Evenings work"})
    assert visit.status_code == 201
    inbox = (await client.get("/api/v1/inbox", headers=oh)).json()
    assert len(inbox["conversations"]) == 1 and len(inbox["messages"]) == 2
    c = inbox["conversations"][0]
    assert c["seekerName"] == "Riya Sharma" and owner["id"] not in c["lastRead"]
    not_owner = await client.post(f"/api/v1/messages/{visit.json()['id']}/visit-response", headers=sh,
                                  json={"accept": True, "slot": slot(1)})
    assert not_owner.status_code == 403
    accepted = await client.post(f"/api/v1/messages/{visit.json()['id']}/visit-response", headers=oh,
                                 json={"accept": True, "slot": visit.json()["visit"]["slots"][1]})
    assert accepted.status_code == 200 and accepted.json()["visit"]["status"] == "accepted"
    revealed = (await client.get(f"/api/v1/listings/{listing['id']}", headers=sh)).json()
    assert revealed["address"] == "Flat 302, Shanti Residency" and revealed["lat"] == 22.753312
    paused = await client.patch(f"/api/v1/owner/listings/{listing['id']}", headers=oh, json={"status": "paused"})
    assert paused.json()["status"] == "paused"
    ids = [x["id"] for x in (await client.get("/api/v1/listings", headers=sh)).json()]
    assert listing["id"] not in ids
async def test_sample_listings_and_demo_owner_reply(client, monkeypatch):
    monkeypatch.setattr(messages_api, "DEMO_REPLY_DELAY_SECONDS", 0)
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)
    _, sh = await signup(client)
    all_listings = (await client.get("/api/v1/listings", headers=sh)).json()
    samples = [x for x in all_listings if x["id"].startswith("IND-")]
    assert len(samples) == 6 and all(x["photos"] for x in samples)
    old = next(x for x in all_listings if x["id"] == "IND-VN-101")
    conv = await client.post("/api/v1/conversations", headers=sh, json={"listingId": old["id"]})
    assert conv.status_code == 200
    cid = conv.json()["id"]
    await client.post(f"/api/v1/conversations/{cid}/messages", headers=sh, json={"kind": "visit", "slots": [slot(3)]})
    inbox = (await client.get("/api/v1/inbox", headers=sh)).json()
    visit = next(m for m in inbox["messages"] if m["conversationId"] == cid and m["kind"] == "visit")
    assert visit["visit"]["status"] == "accepted"
    assert any("Visit confirmed" in (m.get("text") or "") for m in inbox["messages"])
    new = next(x for x in all_listings if x["id"] == "IND-VN-102")
    locked = await client.post("/api/v1/conversations", headers=sh, json={"listingId": new["id"]})
    assert locked.status_code == 403
