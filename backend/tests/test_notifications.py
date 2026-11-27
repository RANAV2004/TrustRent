import asyncio
import io
from app.core.config import settings
from tests.mailbox import MAILS
from tests.test_lawyers import PDF, approved_lawyer, apply
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, signup, slot

JPG = b"\xff\xd8\xffphoto"

async def settle():
    for _ in range(10):
        await asyncio.sleep(0)

def to(email: str) -> list[dict]:
    return [m for m in MAILS if m["to"] == email]

async def test_chat_and_visit_emails(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_URL", "https://trustrent.in")
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=th, data={"docType": "Passport"},
                      files={"file": ("p.jpg", io.BytesIO(JPG), "image/jpeg")})
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "premium", "planId": "week"})
    await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})
    await settle()
    assert any("Premium is active" in m["subject"] for m in to(tenant["email"]))
    conv = (await client.post("/api/v1/conversations", headers=th, json={"listingId": listing["id"]})).json()
    MAILS.clear()
    for text in ("Is it still available?", "Also, is parking included?"):
        await client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=th, json={"text": text})
    await settle()
    chat = to(owner["email"])
    assert len(chat) == 1
    assert chat[0]["subject"] == "New message from Riya Sharma" and "Is it still available?" in chat[0]["body"]
    assert "https://trustrent.in/messages" in chat[0]["body"]
    await client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=oh, json={"text": "Yes, it is."})
    await settle()
    assert to(tenant["email"]) == []
    visit = (await client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=th,
                               json={"kind": "visit", "slots": [slot(2)]})).json()
    await client.post(f"/api/v1/messages/{visit['id']}/visit-response", headers=oh, json={"accept": True, "slot": visit["visit"]["slots"][0]})
    await settle()
    assert any(m["subject"].startswith("Visit request for") for m in to(owner["email"]))
    confirmed = [m for m in to(tenant["email"]) if m["subject"].startswith("Visit confirmed")]
    assert confirmed and "IST" in confirmed[0]["body"]

async def test_deposit_emails(client):
    ah = await admin_headers(client)
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    MAILS.clear()
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    dep_id = (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})).json()["depositId"]
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 4000, "reason": "Broken window in the hall"})
    await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": False})
    await client.post(f"/api/v1/admin/deposits/{dep_id}/settle", headers=ah, json={"deducted": 2000, "reason": "Half the window cost"})
    await settle()
    t = [m["subject"] for m in to(tenant["email"])]
    o = [m["subject"] for m in to(owner["email"])]
    assert f"Deposit receipt {dep_id}" in t and f"Settlement proposed for deposit {dep_id}" in t
    assert f"Deposit received for {listing['title']}" in o and f"Deposit {dep_id} disputed" in o
    assert f"TrustRent settled deposit {dep_id}" in t and f"TrustRent settled deposit {dep_id}" in o
    proposal = next(m for m in to(tenant["email"]) if m["subject"].startswith("Settlement proposed"))
    assert "Rs 4,000" in proposal["body"] and "Rs 30,000" in proposal["body"] and "Broken window" in proposal["body"]
    assert any(m["subject"] == f"[TrustRent admin] Deposit {dep_id} is disputed" for m in to(settings.ADMIN_EMAILS[0]))

async def test_verification_emails(client, monkeypatch):
    ah = await admin_headers(client)
    user, uh = await signup(client)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("pan.jpg", io.BytesIO(JPG), "image/jpeg")})
    await settle()
    assert any(m["subject"] == "[TrustRent admin] ID verification waiting" for m in to(settings.ADMIN_EMAILS[0]))
    sub = next(s for s in (await client.get("/api/v1/admin/verifications", headers=ah)).json()["identities"] if s["userId"] == user["id"])
    await client.post(f"/api/v1/admin/identity/{sub['id']}/review", headers=ah, json={"approve": False, "note": "Photo is blurry"})
    await settle()
    rejected = [m for m in to(user["email"]) if m["subject"] == "We couldn't verify your ID"]
    assert rejected and "Photo is blurry" in rejected[0]["body"]

async def test_lawyer_emails(client):
    ah = await admin_headers(client)
    MAILS.clear()
    res, data = await apply(client)
    await settle()
    assert any(res.json()["reference"] in m["subject"] for m in to(data["email"]))
    assert any(m["subject"] == "[TrustRent admin] Lawyer application waiting" for m in to(settings.ADMIN_EMAILS[0]))
    lawyer, lh, _, ldata = await approved_lawyer(client, ah)
    await settle()
    assert any(m["subject"] == "Your TrustRent lawyer account is ready" for m in to(ldata["email"]))
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    case = (await client.post("/api/v1/legal/cases", headers=oh, json={"lawyerId": lawyer["id"], "listingId": listing["id"],
                                                                       "message": "Please draft the agreement."})).json()
    up = await client.post(f"/api/v1/legal/cases/{case['id']}/agreements", headers=lh, data={"title": "Leave and licence"},
                           files={"file": ("a.pdf", io.BytesIO(PDF), "application/pdf")})
    await client.post(f"/api/v1/legal/agreements/{up.json()['documents'][0]['id']}/share", headers=oh, json={"tenantId": tenant["id"]})
    await settle()
    assert any(m["subject"].startswith("New agreement request from") for m in to(ldata["email"]))
    assert any(m["subject"].endswith("sent you a document") for m in to(owner["email"]))
    assert any(m["subject"].endswith("shared a rental agreement with you") for m in to(tenant["email"]))

async def test_no_emails_to_demo_banned_or_when_switched_off(client, monkeypatch):
    ah = await admin_headers(client)
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    conv = (await client.get("/api/v1/inbox", headers=th)).json()["conversations"][0]["id"]
    await client.post(f"/api/v1/admin/users/{owner['id']}/ban", headers=ah, json={"reason": "spam"})
    MAILS.clear()
    await client.post(f"/api/v1/conversations/{conv}/messages", headers=th, json={"text": "Hello?"})
    await settle()
    assert to(owner["email"]) == []
    await client.post(f"/api/v1/admin/users/{owner['id']}/unban", headers=ah)
    monkeypatch.setattr(settings, "EMAIL_NOTIFICATIONS", False)
    await client.post(f"/api/v1/conversations/{conv}/messages", headers=th, json={"text": "Hello again?"})
    await settle()
    assert MAILS == []
