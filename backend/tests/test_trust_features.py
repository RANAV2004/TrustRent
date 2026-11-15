"""Audit log, listing reports, reviews, move-in checklist, payouts (Razorpay Route), monthly rent,
DigiLocker and Aadhaar eSign / e-stamp. Outside providers are faked."""
import hashlib
import hmac
import io
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
import pytest
from sqlalchemy import select, update
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.deposits import Deposit
from app.models.marketplace import utcnow
from app.models.trust import AuditLog, RentInvoice
from app.services import notify
from app.services.ledger import ledger_state
from app.services.rent import rupees_in_words, send_reminders
from tests.test_condition_photos import jpeg_with_gps
from tests.test_hardening import paid_deposit
from tests.test_live_features import admin_headers
from tests.test_marketplace import signup, tag

TERMS = {"startDate": "2026-12-01", "months": 3, "monthlyRent": 17000, "rentDueDay": 5, "noticeDays": 30, "lockInMonths": 0,
         "maintenance": "", "extraClauses": ""}


async def settled(client, deducted=0):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": deducted, "reason": "Broken window pane replaced" if deducted else ""})
    await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True})
    return owner, oh, tenant, th, listing, dep


async def signed_agreement(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/agreement", headers=oh, json=TERMS)
    await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=th, json={"typedName": "Riya Sharma", "agree": True})
    await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=oh, json={"typedName": "Riya Sharma", "agree": True})
    return owner, oh, tenant, th, listing, dep


# audit log
async def test_admin_actions_are_audited(client):
    ah = await admin_headers(client)
    user, uh = await signup(client)
    await client.post(f"/api/v1/admin/users/{user['id']}/ban", headers=ah, json={"reason": "Spam"})
    await client.post(f"/api/v1/admin/users/{user['id']}/unban", headers=ah)
    log = (await client.get("/api/v1/admin/audit", headers=ah, params={"target": user["id"]})).json()
    actions = [r["action"] for r in log["rows"]]
    assert actions[:2] == ["user.unbanned", "user.banned"] and log["rows"][1]["details"]["reason"] == "Spam"
    assert log["rows"][0]["actor"] == settings.ADMIN_EMAILS[0] and "user.banned" in log["actions"]
    assert (await client.get("/api/v1/admin/audit", headers=uh)).status_code in (401, 403)


async def test_document_views_are_audited(client, monkeypatch):
    ah = await admin_headers(client)
    from tests.test_security import pending_id, submissions
    applicant, uh = await signup(client)
    await pending_id(client, monkeypatch, uh)
    sub = (await submissions(client, ah, applicant["id"]))[0]
    await client.get(f"/api/v1/admin/identity/{sub['id']}/file", headers=ah)
    rows = (await client.get("/api/v1/admin/audit", headers=ah, params={"action": "document.viewed", "target": applicant["id"]})).json()["rows"]
    assert rows and rows[0]["details"]["document"] == "PAN card"


# listing reports
async def test_reports_hold_listing_and_admin_resolves(client, monkeypatch):
    monkeypatch.setattr(settings, "REPORTS_TO_HOLD_LISTING", 2)
    ah = await admin_headers(client)
    from tests.test_marketplace import owner_with_listing
    owner, oh, listing = await owner_with_listing(client)
    assert (await client.post(f"/api/v1/listings/{listing['id']}/report", headers=oh, json={"reason": "fake"})).status_code == 400
    _, h1 = await signup(client)
    _, h2 = await signup(client)
    assert (await client.post(f"/api/v1/listings/{listing['id']}/report", headers=h1, json={"reason": "bogus"})).status_code == 400
    assert (await client.post(f"/api/v1/listings/{listing['id']}/report", headers=h1, json={"reason": "scam", "details": "Asked for UPI"})).status_code == 201
    assert (await client.post(f"/api/v1/listings/{listing['id']}/report", headers=h1, json={"reason": "scam"})).status_code == 409
    assert (await client.post(f"/api/v1/listings/{listing['id']}/report", headers=h2, json={"reason": "fake"})).status_code == 201
    assert (await client.get(f"/api/v1/listings/{listing['id']}", headers=h1)).status_code == 404  # held for review
    queue = [r for r in (await client.get("/api/v1/admin/reports", headers=ah)).json() if r["listing"]["id"] == listing["id"]]
    assert len(queue) == 2 and queue[0]["listing"]["openReports"] == 2
    for r in queue:
        assert (await client.post(f"/api/v1/admin/reports/{r['id']}/resolve", headers=ah, json={"action": "dismiss", "note": "Owner verified"})).status_code == 200
    assert (await client.get(f"/api/v1/listings/{listing['id']}", headers=h1)).status_code == 200  # back online
    await client.post(f"/api/v1/listings/{listing['id']}/report", headers=h1, json={"reason": "fake"})
    r = [x for x in (await client.get("/api/v1/admin/reports", headers=ah)).json() if x["listing"]["id"] == listing["id"]][0]
    done = (await client.post(f"/api/v1/admin/reports/{r['id']}/resolve", headers=ah, json={"action": "unlist", "note": "Photos are stock images"})).json()
    assert done["listing"]["status"] == "blocked"
    log = (await client.get("/api/v1/admin/audit", headers=ah, params={"target": listing["id"]})).json()["rows"]
    assert {"report.unlisted", "report.dismissed", "listing.held_for_reports"} <= {x["action"] for x in log}


# reviews
async def test_blind_reviews_after_settlement(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    assert (await client.post(f"/api/v1/deposits/{dep}/review", headers=th, json={"rating": 5})).status_code == 409  # not settled
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 0, "reason": ""})
    await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True})
    assert (await client.post(f"/api/v1/deposits/{dep}/review", headers=th, json={"rating": 6})).status_code == 422
    mine = (await client.post(f"/api/v1/deposits/{dep}/review", headers=th, json={"rating": 5, "text": "Full refund, quick replies."})).json()
    assert mine["mine"]["rating"] == 5 and mine["canReview"] is False
    owner_view = (await client.get(f"/api/v1/deposits/{dep}/review", headers=oh)).json()
    assert owner_view["theirs"] is None and owner_view["theirsWaiting"] and owner_view["canReview"]  # blind until they review
    assert (await client.get(f"/api/v1/users/{owner['id']}/reviews", headers=th)).json()["summary"]["count"] == 0
    await client.post(f"/api/v1/deposits/{dep}/review", headers=oh, json={"rating": 4, "text": "Left the flat clean."})
    assert (await client.post(f"/api/v1/deposits/{dep}/review", headers=oh, json={"rating": 4})).status_code == 409
    both = (await client.get(f"/api/v1/deposits/{dep}/review", headers=oh)).json()
    assert both["theirs"]["rating"] == 5
    pub = (await client.get(f"/api/v1/users/{owner['id']}/reviews", headers=th)).json()
    assert pub["summary"] == {"avg": 5.0, "count": 1}
    rec = (await client.get(f"/api/v1/listings/{listing['id']}", headers=th)).json()["landlord"]
    assert rec["rating"] == 5.0 and rec["reviews"] == 1
    inbox = (await client.get("/api/v1/inbox", headers=oh)).json()
    assert any(c.get("seekerRating", {}).get("avg") == 4.0 for c in inbox["conversations"])  # owners see tenant ratings
    ah = await admin_headers(client)
    rid = [r for r in (await client.get("/api/v1/admin/reviews", headers=ah)).json() if r["depositId"] == dep and r["rating"] == 5][0]["id"]
    await client.post(f"/api/v1/admin/reviews/{rid}/hide", headers=ah, json={"reason": "Contains a phone number"})
    assert (await client.get(f"/api/v1/users/{owner['id']}/reviews", headers=th)).json()["summary"]["count"] == 0


async def test_review_window_reveals_one_sided_review(client, monkeypatch):
    owner, oh, tenant, th, listing, dep = await settled(client)
    await client.post(f"/api/v1/deposits/{dep}/review", headers=th, json={"rating": 2, "text": "Slow to return the deposit."})
    async with AsyncSessionLocal() as db:
        await db.execute(update(Deposit).where(Deposit.id == dep).values(settled_at=utcnow() - timedelta(days=settings.REVIEW_WINDOW_DAYS + 1)))
        await db.commit()
    pub = (await client.get(f"/api/v1/users/{owner['id']}/reviews", headers=th)).json()
    assert pub["summary"]["count"] == 1
    assert (await client.post(f"/api/v1/deposits/{dep}/review", headers=oh, json={"rating": 5})).status_code == 409  # window closed


# move-in checklist
async def test_checklist_requires_every_room(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    c = (await client.get(f"/api/v1/deposits/{dep}/checklist", headers=th)).json()
    rooms = [r["name"] for r in c["rooms"]]
    assert rooms[:3] == ["Entrance and doors", "Hall / living room", "Kitchen"] and "Bedroom 2" in rooms and "Bathroom 2" in rooms
    missing = await client.post(f"/api/v1/deposits/{dep}/checklist/move_in/complete", headers=th)
    assert missing.status_code == 400 and "Kitchen" in missing.json()["detail"]["message"]
    for room in rooms:
        await client.post(f"/api/v1/deposits/{dep}/photos", headers=th, data={"stage": "move_in", "room": room},
                          files={"file": ("r.jpg", io.BytesIO(jpeg_with_gps()), "image/jpeg")})
    done = (await client.post(f"/api/v1/deposits/{dep}/checklist/move_in/complete", headers=th)).json()
    assert done["stages"]["move_in"]["tenant"]["completedAt"] and not done["stages"]["move_in"]["tenant"]["missing"]
    assert (await client.post(f"/api/v1/deposits/{dep}/checklist/move_in/complete", headers=th)).status_code == 409
    other = (await client.get(f"/api/v1/deposits/{dep}/checklist", headers=oh)).json()
    assert other["stages"]["move_in"]["tenant"] == {"completedAt": done["stages"]["move_in"]["tenant"]["completedAt"], "rooms": len(rooms)}
    async with AsyncSessionLocal() as db:
        assert (await ledger_state(db))[1] is True


# payouts and Razorpay Route
async def test_payout_details_are_encrypted_and_reviewed(client):
    ah = await admin_headers(client)
    _, sh = await signup(client)
    body = {"holderName": "Riya Sharma", "ifsc": "hdfc0001234", "accountNumber": "123456789012", "pan": "abcde1234f"}
    assert (await client.put("/api/v1/owner/payout-account", headers=sh, json=body)).status_code == 403
    owner, oh, listing = await __import__("tests.test_marketplace", fromlist=["x"]).owner_with_listing(client)
    assert (await client.put("/api/v1/owner/payout-account", headers=oh, json=body | {"ifsc": "BAD"})).json()["detail"]["field"] == "ifsc"
    assert (await client.put("/api/v1/owner/payout-account", headers=oh, json=body | {"pan": "123"})).json()["detail"]["field"] == "pan"
    acc = (await client.put("/api/v1/owner/payout-account", headers=oh, json=body)).json()["account"]
    assert acc == acc | {"ifsc": "HDFC0001234", "accountLast4": "9012", "panLast4": "234F", "status": "submitted"}
    assert "123456789012" not in json.dumps(acc)
    async with AsyncSessionLocal() as db:
        from app.models.trust import PayoutAccount
        raw = await db.get(PayoutAccount, owner["id"])
        assert "123456789012" not in raw.account_enc and "ABCDE1234F" not in raw.pan_enc
    full = (await client.get(f"/api/v1/admin/payout-accounts/{owner['id']}/reveal", headers=ah)).json()
    assert full["accountNumber"] == "123456789012" and full["pan"] == "ABCDE1234F"
    bad = await client.post(f"/api/v1/admin/payout-accounts/{owner['id']}", headers=ah, json={"approve": True, "linkedAccountId": "xyz"})
    assert bad.status_code == 400
    ok = (await client.post(f"/api/v1/admin/payout-accounts/{owner['id']}", headers=ah, json={"approve": True, "linkedAccountId": "acc_ABCDEFGHIJ1234"})).json()
    assert ok["status"] == "active" and ok["linkedAccountId"] == "acc_ABCDEFGHIJ1234"
    log = (await client.get("/api/v1/admin/audit", headers=ah, params={"target": owner["id"], "action": "payout_account"})).json()["rows"]
    assert {"payout_account.revealed", "payout_account.approved", "payout_account.updated"} <= {r["action"] for r in log}


async def route_owner(client, monkeypatch, oh, owner_id):
    ah = await admin_headers(client)
    await client.put("/api/v1/owner/payout-account", headers=oh, json={"holderName": "Riya Sharma", "ifsc": "HDFC0001234",
                                                                        "accountNumber": "123456789012", "pan": "ABCDE1234F"})
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret123")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "hook-secret")
    monkeypatch.setattr(settings, "RAZORPAY_ROUTE_ENABLED", True)
    await client.post(f"/api/v1/admin/payout-accounts/{owner_id}", headers=ah, json={"approve": True, "linkedAccountId": "acc_ABCDEFGHIJ1234"})
    return ah


def signed(raw: bytes) -> dict:
    return {"x-razorpay-signature": hmac.new(b"hook-secret", raw, hashlib.sha256).hexdigest()}


async def test_deposit_deduction_goes_to_owner_through_route(client, monkeypatch):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await route_owner(client, monkeypatch, oh, owner["id"])
    sent = []

    async def direct(account, amount, notes):
        sent.append((account, amount, notes))
        return "trf_DEP123"
    monkeypatch.setattr("app.services.payments.direct_transfer", direct)
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 3000, "reason": "Repainted the scuffed bedroom wall"})
    d = (await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True})).json()
    assert sent == [("acc_ABCDEFGHIJ1234", 3000, {"deposit": dep})] and d["ownerPayout"] == "transferred"
    raw = json.dumps({"event": "transfer.processed", "payload": {"transfer": {"entity": {"id": "trf_DEP123"}}}}).encode()
    res = await client.post("/api/v1/payments/webhook", content=raw, headers=signed(raw))
    assert res.json()["matched"] is True
    assert (await client.get(f"/api/v1/deposits/{dep}", headers=oh)).json()["ownerPayout"] == "paid"


async def test_without_route_payout_stays_on_admin_desk(client):
    owner, oh, tenant, th, listing, dep = await settled(client, deducted=2500)
    ah = await admin_headers(client)
    desk = (await client.get("/api/v1/admin/payouts", headers=ah)).json()
    assert any(x["kind"] == "deposit" and x["id"] == dep and x["amount"] == 2500 for x in desk["due"])


# monthly rent
def test_rupees_in_words():
    assert rupees_in_words(17000) == "Seventeen Thousand Rupees Only"
    assert rupees_in_words(125450) == "One Lakh Twenty Five Thousand Four Hundred Fifty Rupees Only"
    assert rupees_in_words(10_000_000) == "One Crore Rupees Only"


async def test_rent_schedule_payment_receipt_and_statement(client, mail):
    owner, oh, tenant, th, listing, dep = await signed_agreement(client)
    sched = (await client.get(f"/api/v1/deposits/{dep}/rent", headers=th)).json()
    assert [i["period"] for i in sched["invoices"]] == ["2026-12", "2027-01", "2027-02"]
    first = sched["invoices"][0]
    assert first["dueDate"] == "2026-12-05" and first["amount"] == 17000
    _, sh = await signup(client)
    assert (await client.post("/api/v1/payments/order", headers=sh, json={"purpose": "rent", "invoiceId": first["id"]})).status_code == 404
    order = (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "rent", "invoiceId": first["id"]})).json()
    assert order["amount"] == 17000
    await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order["orderId"]})
    paid = (await client.get(f"/api/v1/deposits/{dep}/rent", headers=th)).json()["invoices"][0]
    assert paid["status"] == "paid" and paid["receiptNo"].startswith("RR-202612-")
    again = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "rent", "invoiceId": first["id"]})
    assert again.status_code == 409
    await client.put("/api/v1/owner/payout-account", headers=oh, json={"holderName": "Riya Sharma", "ifsc": "HDFC0001234",
                                                                        "accountNumber": "123456789012", "pan": "ABCDE1234F"})
    rec = await client.get(f"/api/v1/rent/{first['id']}/receipt", headers=th)
    assert rec.status_code == 200 and "Seventeen Thousand Rupees Only" in rec.text and "ABCDE1234F" in rec.text  # 2.04 lakh/yr: PAN shown
    second = (await client.get(f"/api/v1/deposits/{dep}/rent", headers=oh)).json()["invoices"][1]
    assert (await client.post(f"/api/v1/rent/{second['id']}/mark-paid", headers=th, json={"method": "cash"})).status_code == 403
    off = (await client.post(f"/api/v1/rent/{second['id']}/mark-paid", headers=oh, json={"method": "upi", "reference": "UTR123"})).json()
    assert off["status"] == "paid" and off["method"] == "offline" and off["payout"] == "none"
    stmt = await client.get(f"/api/v1/deposits/{dep}/rent/statement", headers=th, params={"fy": 2026})
    assert "₹34,000" in stmt.text and "Thirty Four Thousand" in stmt.text
    async with AsyncSessionLocal() as db:
        assert (await ledger_state(db))[1] is True


async def test_rent_reminders_and_tenancy_end(client, mail):
    owner, oh, tenant, th, listing, dep = await signed_agreement(client)
    today = utcnow().date()
    async with AsyncSessionLocal() as db:
        rows = list(await db.scalars(select(RentInvoice).where(RentInvoice.deposit_id == dep).order_by(RentInvoice.period)))
        rows[0].due_date = (today - timedelta(days=2)).isoformat()
        rows[1].due_date = (today + timedelta(days=1)).isoformat()
        rows[2].due_date = (today + timedelta(days=40)).isoformat()
        await db.commit()
    mail.clear()
    async with AsyncSessionLocal() as db:
        assert await send_reminders(db) >= 2
    await notify.drain()
    subjects = [m["subject"] for m in mail if m["to"] == tenant["email"]]
    assert any("overdue" in s for s in subjects) and any("is due on" in s for s in subjects)
    async with AsyncSessionLocal() as db:
        await send_reminders(db)
    await notify.drain()
    assert len([m for m in mail if m["to"] == tenant["email"]]) == len(subjects)  # once each
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 0, "reason": ""})
    await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True})
    statuses = [i["status"] for i in (await client.get(f"/api/v1/deposits/{dep}/rent", headers=th)).json()["invoices"]]
    assert statuses[2] == "cancelled" and statuses[0] == "overdue"  # past months still owed, future ones dropped


async def test_online_rent_goes_to_owner_through_route(client, monkeypatch):
    owner, oh, tenant, th, listing, dep = await signed_agreement(client)
    await route_owner(client, monkeypatch, oh, owner["id"])
    monkeypatch.setattr(settings, "RENT_PLATFORM_FEE_PCT", 1.0)

    async def fake_order(amount, receipt, notes):
        return {"id": f"order_{tag()}"}
    sent = []

    async def from_payment(pid, account, amount, notes):
        sent.append((pid, account, amount))
        return "trf_RENT1"
    monkeypatch.setattr("app.services.payments.create_order", fake_order)
    monkeypatch.setattr("app.services.payments.transfer_from_payment", from_payment)
    inv = (await client.get(f"/api/v1/deposits/{dep}/rent", headers=th)).json()["invoices"][0]
    order = (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "rent", "invoiceId": inv["id"]})).json()
    raw = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_RENT1", "order_id": order["orderId"],
                                                                                         "amount": 1700000}}}}).encode()
    assert (await client.post("/api/v1/payments/webhook", content=raw, headers=signed(raw))).json()["status"] == "paid"
    assert sent == [("pay_RENT1", "acc_ABCDEFGHIJ1234", 16830)]  # 1% platform fee kept
    got = (await client.get(f"/api/v1/deposits/{dep}/rent", headers=oh)).json()["invoices"][0]
    assert got["status"] == "paid" and got["payout"] == "transferred"


# DigiLocker
EAADHAAR = (b'<?xml version="1.0"?><Certificate><CertificateData><KycRes><UidData uid="xxxxxxxx4321">'
            b'<Poi name="Riya Sharma" dob="01-01-1998" gender="F"/></UidData></KycRes></CertificateData></Certificate>')


@pytest.fixture
def digilocker_on(monkeypatch):
    monkeypatch.setattr(settings, "DIGILOCKER_CLIENT_ID", "dl-client")
    monkeypatch.setattr(settings, "DIGILOCKER_CLIENT_SECRET", "dl-secret")
    monkeypatch.setattr(settings, "DIGILOCKER_REDIRECT_URI", "http://localhost:3000/identity/digilocker")
    seen = {}

    async def fake_fetch(code, verifier):
        seen["verifier"] = verifier
        return seen.get("xml", EAADHAAR)
    monkeypatch.setattr("app.services.digilocker.fetch_eaadhaar", fake_fetch)
    return seen


async def test_digilocker_verifies_matching_name(client, digilocker_on, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    user, uh = await signup(client)
    url = (await client.get("/api/v1/identity/digilocker/start", headers=uh)).json()["url"]
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"] and q["client_id"] == ["dl-client"]
    _, other = await signup(client)
    assert (await client.post("/api/v1/identity/digilocker/complete", headers=other, json={"code": "abcd", "state": q["state"][0]})).status_code == 400
    res = (await client.post("/api/v1/identity/digilocker/complete", headers=uh, json={"code": "abcd", "state": q["state"][0]})).json()
    assert res["matched"] and res["user"]["idVerified"] is True
    import base64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(digilocker_on["verifier"].encode()).digest()).decode().rstrip("=")
    assert challenge == q["code_challenge"][0]  # PKCE verifier stayed on the server
    assert (await client.post("/api/v1/identity/digilocker/complete", headers=uh, json={"code": "abcd", "state": q["state"][0]})).status_code == 400


async def test_digilocker_name_mismatch_goes_to_admin(client, digilocker_on, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    digilocker_on["xml"] = EAADHAAR.replace(b"Riya Sharma", b"Someone Else")
    _, uh = await signup(client)
    state = parse_qs(urlparse((await client.get("/api/v1/identity/digilocker/start", headers=uh)).json()["url"]).query)["state"][0]
    res = (await client.post("/api/v1/identity/digilocker/complete", headers=uh, json={"code": "abcd", "state": state})).json()
    assert res["matched"] is False and res["pendingReview"] and res["user"]["idVerified"] is False


def test_eaadhaar_parser_rejects_entity_attacks():
    from app.services.digilocker import DigilockerError, parse_eaadhaar
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><Poi name="&b;"/>'
    with pytest.raises(DigilockerError):
        parse_eaadhaar(bomb)
    assert parse_eaadhaar(EAADHAAR) == {"name": "Riya Sharma", "dob": "01-01-1998", "last4": "4321"}


# Aadhaar eSign and e-stamp
async def test_estamp_is_part_of_the_signed_text(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/agreement", headers=oh, json=TERMS)
    form = {"state": "Madhya Pradesh", "certificateNumber": "IN-MP12345678901234X", "amount": "500"}
    pdf = ("estamp.pdf", io.BytesIO(b"%PDF-1.4 e-stamp"), "application/pdf")
    assert (await client.post(f"/api/v1/deposits/{dep}/agreement/estamp", headers=th, data=form, files={"file": pdf})).status_code == 403
    out = (await client.post(f"/api/v1/deposits/{dep}/agreement/estamp", headers=oh, data=form,
                             files={"file": ("estamp.pdf", io.BytesIO(b"%PDF-1.4 e-stamp"), "application/pdf")})).json()
    a = out["agreement"]
    assert "IN-MP12345678901234X" in a["text"] and a["estamp"]["amount"] == 500 and a["verified"]
    edited = (await client.post(f"/api/v1/deposits/{dep}/agreement", headers=oh, json=TERMS | {"noticeDays": 60})).json()
    assert "IN-MP12345678901234X" in edited["agreement"]["text"]  # editing terms keeps the e-stamp
    assert (await client.get(f"/api/v1/deposits/{dep}/agreement/estamp", headers=th)).content.startswith(b"%PDF")
    await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=th, json={"typedName": "Riya Sharma", "agree": True})
    late = await client.post(f"/api/v1/deposits/{dep}/agreement/estamp", headers=oh, data=form,
                             files={"file": ("estamp.pdf", io.BytesIO(b"%PDF-1.4 e-stamp"), "application/pdf")})
    assert late.status_code == 409


async def test_aadhaar_esign_flow(client, monkeypatch):
    from app.services import esign
    monkeypatch.setattr(settings, "ESIGN_PROVIDER", "digio")
    monkeypatch.setattr(settings, "DIGIO_CLIENT_ID", "d")
    monkeypatch.setattr(settings, "DIGIO_CLIENT_SECRET", "s")
    state = {"complete": False}

    async def create(pdf, name, signers):
        assert pdf.startswith(b"%PDF") and len(signers) == 2
        return "DID_TEST_1"

    async def fetch(doc_id):
        return {"id": doc_id, "agreement_status": "completed" if state["complete"] else "requested"}

    async def download(doc_id):
        return b"%PDF-1.7 signed with aadhaar"
    monkeypatch.setattr(esign, "create_request", create)
    monkeypatch.setattr(esign, "fetch", fetch)
    monkeypatch.setattr(esign, "download", download)
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/agreement", headers=oh, json=TERMS)
    assert (await client.get(f"/api/v1/deposits/{dep}/agreement", headers=th)).json()["esignAvailable"] is True
    started = (await client.post(f"/api/v1/deposits/{dep}/agreement/esign", headers=th)).json()
    assert started["agreement"]["esign"]["status"] == "requested" and started["esignAvailable"] is False
    blocked = await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=th, json={"typedName": "Riya Sharma", "agree": True})
    assert blocked.status_code == 409
    fake = await client.post("/api/v1/agreements/esign/webhook", json={"payload": {"document": {"id": "DID_TEST_1", "agreement_status": "completed"}}})
    assert fake.json()["completed"] == 0  # the provider still says not signed: a forged webhook changes nothing
    state["complete"] = True
    assert (await client.post("/api/v1/agreements/esign/webhook", json={"payload": {"document": {"id": "DID_TEST_1"}}})).json()["completed"] == 1
    a = (await client.get(f"/api/v1/deposits/{dep}/agreement", headers=oh)).json()["agreement"]
    assert a["status"] == "signed" and a["esign"]["status"] == "completed" and a["esign"]["pdfHash"]
    assert (await client.get(f"/api/v1/deposits/{dep}/agreement/esigned.pdf", headers=th)).content.startswith(b"%PDF-1.7")
    assert len((await client.get(f"/api/v1/deposits/{dep}/rent", headers=th)).json()["invoices"]) == 3  # rent schedule started


def test_agreement_pdf_renders():
    from app.services.esign import agreement_pdf
    pdf = agreement_pdf("RESIDENTIAL RENT AGREEMENT\n\n1. Rent ₹17,000 — due on the 5th.", "fingerprint 0xabc")
    assert pdf.startswith(b"%PDF") and len(pdf) > 500


async def test_config_reports_integrations(client):
    cfg = (await client.get("/api/v1/config")).json()
    assert {"digilocker", "aadhaarEsign", "routePayouts"} <= set(cfg)


async def test_system_auto_settle_is_audited(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 100, "reason": "Lost one key, replaced it"})
    async with AsyncSessionLocal() as db:
        await db.execute(update(Deposit).where(Deposit.id == dep).values(proposed_at=utcnow() - timedelta(days=30)))
        await db.commit()
    from app.services.settlement import sweep_deadlines
    async with AsyncSessionLocal() as db:
        await sweep_deadlines(db)
        row = await db.scalar(select(AuditLog).where(AuditLog.target_id == dep, AuditLog.action == "deposit.auto_settled"))
    assert row is not None and row.actor_label == "system"
