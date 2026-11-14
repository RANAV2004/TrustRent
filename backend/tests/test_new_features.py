"""New features: password reset, notifications, auto-release deadlines, dispute workspace, rent agreements,
search + saved-search alerts, owner reputation."""
import io
import re
from datetime import timedelta
from sqlalchemy import update
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.deposits import Deposit
from app.models.marketplace import Listing, utcnow
from app.models.user import User
from app.services import notify
from app.services.search_alerts import send_alerts
from app.services.settlement import sweep_deadlines
from tests.test_hardening import paid_deposit
from tests.test_live_features import admin_headers
from tests.test_marketplace import owner_with_listing, signup


# password reset
async def test_password_reset_flow(client, mail):
    user, uh = await signup(client)
    unknown = await client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    res = await client.post("/api/v1/auth/password/forgot", json={"email": user["email"].upper()})
    assert res.json() == unknown.json()  # never reveals whether the account exists
    link = next(m for m in mail if m["to"] == user["email"] and "Reset" in m["subject"])["text"]
    token = re.search(r"token=([\w-]+)", link).group(1)
    weak = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "short"})
    assert weak.status_code == 400 and weak.json()["detail"]["field"] == "password"
    ok = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "newpass123"})
    assert ok.status_code == 200
    assert (await client.get("/api/v1/users/me", headers=uh)).status_code == 401  # old sessions signed out
    reused = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "another123"})
    assert reused.status_code == 400
    old = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "secret123"})
    new = await client.post("/api/v1/auth/password-login", json={"identifier": user["username"], "password": "newpass123"})
    assert old.status_code == 401 and new.status_code == 200
    await notify.drain()
    assert any("password was changed" in m["subject"] for m in mail if m["to"] == user["email"])


async def test_reset_link_expires(client, mail):
    user, _ = await signup(client)
    await client.post("/api/v1/auth/password/forgot", json={"email": user["email"]})
    token = re.search(r"token=([\w-]+)", mail[-1]["text"]).group(1)
    from app.models.extras import PasswordReset
    async with AsyncSessionLocal() as db:
        await db.execute(update(PasswordReset).values(expires_at=utcnow() - timedelta(minutes=1)))
        await db.commit()
    assert (await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "newpass123"})).status_code == 400


# email notifications
async def test_message_and_settlement_notifications(client, mail):
    await admin_headers(client)  # seeds the admin who gets dispute alerts
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await notify.drain()
    mail.clear()
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 1000, "reason": "Broken kitchen cabinet hinge"})
    await notify.drain()
    to_tenant = [m for m in mail if m["to"] == tenant["email"]]
    assert to_tenant and "Settlement proposed" in to_tenant[0]["subject"] and "₹1,000" in to_tenant[0]["text"]
    off = await client.put("/api/v1/users/me/notifications", headers=th, json={"email": False})
    assert off.json()["user"]["emailNotifications"] is False
    mail.clear()
    await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": False})
    await client.post(f"/api/v1/deposits/{dep}/notes", headers=oh, json={"text": "The hinge was fine at move-in, see photos."})
    await notify.drain()
    assert not [m for m in mail if m["to"] == tenant["email"]]  # opted out
    assert any("disputed" in m["subject"] for m in mail if m["to"] == owner["email"])
    assert any("New dispute" in m["subject"] for m in mail if m["to"] == settings.ADMIN_EMAILS[0])


async def test_first_unread_message_emails_once(client, mail):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    inbox = (await client.get("/api/v1/inbox", headers=th)).json()
    cid = inbox["conversations"][0]["id"]
    await client.post(f"/api/v1/conversations/{cid}/read", headers=oh)
    await notify.drain()
    mail.clear()
    for text in ("Hi, is the geyser fixed?", "Also the wifi?"):
        await client.post(f"/api/v1/conversations/{cid}/messages", headers=th, json={"kind": "text", "text": text})
    await notify.drain()
    assert len([m for m in mail if m["to"] == owner["email"]]) == 1


# deadlines
async def test_auto_accept_after_response_window(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    p = (await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 2000, "reason": "Two broken window panes"})).json()
    assert p["respondBy"]
    async with AsyncSessionLocal() as db:
        await db.execute(update(Deposit).where(Deposit.id == dep).values(
            proposed_at=utcnow() - timedelta(days=settings.SETTLEMENT_RESPONSE_DAYS, minutes=1)))
        await db.commit()
    async with AsyncSessionLocal() as db:
        assert (await sweep_deadlines(db))["autoAccepted"] >= 1
    d = (await client.get(f"/api/v1/deposits/{dep}", headers=th)).json()
    assert d["status"] == "settled" and d["deducted"] == 2000 and d["autoSettled"] and d["verification"]["verified"]


async def test_full_refund_when_owner_misses_claim_window(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    _, sh = await signup(client)
    assert (await client.post(f"/api/v1/deposits/{dep}/move-out", headers=sh)).status_code == 403
    moved = (await client.post(f"/api/v1/deposits/{dep}/move-out", headers=th)).json()
    assert moved["movedOutAt"] and moved["claimBy"]
    assert (await client.post(f"/api/v1/deposits/{dep}/move-out", headers=th)).status_code == 409
    async with AsyncSessionLocal() as db:
        assert (await sweep_deadlines(db))["autoRefunded"] == 0  # still inside the window
        await db.execute(update(Deposit).where(Deposit.id == dep).values(
            moved_out_at=utcnow() - timedelta(days=settings.MOVE_OUT_CLAIM_DAYS, minutes=1)))
        await db.commit()
    async with AsyncSessionLocal() as db:
        assert (await sweep_deadlines(db))["autoRefunded"] >= 1
    d = (await client.get(f"/api/v1/deposits/{dep}", headers=th)).json()
    assert d["status"] == "settled" and d["refunded"] == d["amount"] and d["deducted"] == 0


# dispute workspace
async def test_dispute_workspace_and_arbitrator(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    from tests.test_condition_photos import jpeg_with_gps
    for h, stage in ((th, "move_in"), (oh, "move_out")):
        await client.post(f"/api/v1/deposits/{dep}/photos", headers=h, data={"stage": stage, "room": "Kitchen"},
                          files={"file": ("k.jpg", io.BytesIO(jpeg_with_gps()), "image/jpeg")})
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 5000, "reason": "Cracked kitchen counter top"})
    await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": False})
    note = await client.post(f"/api/v1/deposits/{dep}/notes", headers=th, json={"text": "The crack was there when I moved in."})
    assert note.status_code == 201 and note.json()["notes"][0]["role"] == "tenant"
    assert (await client.get(f"/api/v1/admin/deposits/{dep}/workspace", headers=th)).status_code == 403
    ah = await admin_headers(client)
    ws = (await client.get(f"/api/v1/admin/deposits/{dep}/workspace", headers=ah)).json()
    kitchen = ws["photos"]["Kitchen"]
    assert kitchen["move_in"]["tenant"] and kitchen["move_out"]["owner"]
    assert ws["ownerAsked"] == 5000 and ws["tenant"]["email"] == tenant["email"] and ws["canDecide"]
    kinds = [e["kind"] for e in ws["timeline"]]
    assert kinds[0] == "paid" and {"proposed", "disputed", "note"} <= set(kinds) and ws["chat"]
    from tests.test_security import make_arbitrator  # arbitrators can decide disputes
    from tests.staff import finish_mfa
    arb, _ = await make_arbitrator(client)
    login = await client.post("/api/v1/auth/password-login", json={"identifier": arb["username"], "password": "secret123"})
    arb_h = {"Authorization": f"Bearer {(await finish_mfa(client, login))['access_token']}"}
    done = await client.post(f"/api/v1/admin/deposits/{dep}/settle", headers=arb_h, json={"deducted": 1000, "reason": "Only part of the crack is new"})
    assert done.status_code == 200 and done.json()["status"] == "settled"
    assert (await client.post(f"/api/v1/deposits/{dep}/notes", headers=th, json={"text": "Thanks for checking."})).status_code == 409
    rep = (await client.get(f"/api/v1/listings/{listing['id']}", headers=th)).json()["landlord"]
    assert rep["tenancies_completed"] == 1 and rep["disputes_lost"] == 1 and rep["computed"] is True


# rent agreement e-signing
async def test_agreement_draft_sign_and_lock(client):
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    terms = {"startDate": "2026-12-01", "months": 11, "monthlyRent": 17000, "noticeDays": 30, "lockInMonths": 3,
             "maintenance": "Tenant pays electricity.", "extraClauses": "No smoking indoors."}
    assert (await client.post(f"/api/v1/deposits/{dep}/agreement", headers=th, json=terms)).status_code == 403
    draft = (await client.post(f"/api/v1/deposits/{dep}/agreement", headers=oh, json=terms)).json()
    a = draft["agreement"]
    assert a["status"] == "draft" and "No smoking indoors." in a["text"] and a["verified"]
    view = (await client.get(f"/api/v1/deposits/{dep}/agreement", headers=th)).json()
    assert view["canSign"] and view["signAs"] == "Riya Sharma"
    wrong = await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=th, json={"typedName": "Someone Else", "agree": True})
    assert wrong.status_code == 400 and wrong.json()["detail"]["field"] == "typedName"
    no_tick = await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=th, json={"typedName": "riya  sharma", "agree": False})
    assert no_tick.status_code == 400
    signed = (await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=th, json={"typedName": "riya sharma", "agree": True})).json()
    assert signed["agreement"]["status"] == "partly_signed" and signed["canSign"] is False
    assert (await client.post(f"/api/v1/deposits/{dep}/agreement", headers=oh, json=terms)).status_code == 409  # locked now
    both = (await client.post(f"/api/v1/deposits/{dep}/agreement/sign", headers=oh, json={"typedName": "Riya Sharma", "agree": True})).json()
    assert both["agreement"]["status"] == "signed" and len(both["agreement"]["signatures"]) == 2
    doc = await client.get(f"/api/v1/deposits/{dep}/agreement/document", headers=th)
    assert doc.status_code == 200 and "default-src 'none'" in doc.headers["content-security-policy"] and a["textHash"] in doc.text
    _, sh = await signup(client)
    assert (await client.get(f"/api/v1/deposits/{dep}/agreement", headers=sh)).status_code == 404
    async with AsyncSessionLocal() as db:  # tampering with the stored text is detected
        from app.models.extras import Agreement
        await db.execute(update(Agreement).where(Agreement.deposit_id == dep).values(text="Rent is Rs 1."))
        await db.commit()
    assert (await client.get(f"/api/v1/deposits/{dep}/agreement", headers=th)).json()["agreement"]["verified"] is False
    ah = await admin_headers(client)
    assert (await client.get("/api/v1/admin/ledger", headers=ah)).json()["intact"] is True


# search
async def test_server_side_search_filters_sort_and_pages(client):
    owner, oh, listing = await owner_with_listing(client)
    _, sh = await signup(client)
    r = await client.get("/api/v1/listings", headers=sh, params={"q": "452010", "budgetMax": 17000, "bhk": "2",
                                                                  "amenities": "parking,lift", "sort": "rent-asc"})
    ids = [x["id"] for x in r.json()]
    assert listing["id"] in ids and int(r.headers["x-total-count"]) >= 1
    assert all(x["rent"] <= 17000 for x in r.json())
    none = await client.get("/api/v1/listings", headers=sh, params={"q": "452010", "budgetMax": 1000})
    assert none.json() == [] and none.headers["x-total-count"] == "0"
    page = await client.get("/api/v1/listings", headers=sh, params={"page": 1, "pageSize": 1})
    assert len(page.json()) <= 1
    assert (await client.get("/api/v1/listings", headers=sh, params={"sort": "bogus"})).status_code == 400


async def test_saved_search_alerts(client, mail):
    seeker, sh = await signup(client)
    bad = await client.post("/api/v1/searches", headers=sh, json={"name": "x", "filters": {}})
    assert bad.status_code == 400
    saved = await client.post("/api/v1/searches", headers=sh, json={"name": "Vijay Nagar 2BHK",
                                                                    "filters": {"q": "Vijay Nagar", "bhk": [2], "budgetMax": 20000}})
    assert saved.status_code == 201
    async with AsyncSessionLocal() as db:  # pretend the search was saved a minute ago
        from app.models.extras import SavedSearch
        await db.execute(update(SavedSearch).values(created_at=utcnow() - timedelta(minutes=1), last_alert_at=None))
        await db.commit()
    owner, oh, listing = await owner_with_listing(client)
    mail.clear()
    async with AsyncSessionLocal() as db:
        assert await send_alerts(db) >= 1
    await notify.drain()
    alert = [m for m in mail if m["to"] == seeker["email"]]
    assert alert and "Vijay Nagar 2BHK" in alert[0]["subject"] and "Sunny 2 BHK" in alert[0]["text"]
    async with AsyncSessionLocal() as db:
        await send_alerts(db)
    await notify.drain()
    assert len([m for m in mail if m["to"] == seeker["email"]]) == 1  # same home isn't sent twice
    mine = (await client.get("/api/v1/searches", headers=sh)).json()
    assert (await client.delete(f"/api/v1/searches/{mine[0]['id']}", headers=sh)).status_code == 204


async def test_sample_homes_keep_seeded_reputation(client):
    from app.services.seed import seed_sample_listings
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)
        sample = await db.get(Listing, "IND-VN-101")
    _, sh = await signup(client)
    out = (await client.get("/api/v1/listings/IND-VN-101", headers=sh)).json()["landlord"]
    assert out["tenancies_completed"] == sample.tenancies_completed and out["computed"] is False
    async with AsyncSessionLocal() as db:
        u = await db.get(User, sample.owner_id)
        assert u.is_demo


# blockchain copy happens in the background job, never inside a request
async def test_background_job_anchors_on_chain(client, monkeypatch):
    from app.services import chain, jobs
    owner, oh, tenant, th, listing, dep = await paid_deposit(client)
    await client.post(f"/api/v1/deposits/{dep}/propose", headers=oh, json={"deducted": 0, "reason": ""})
    await client.post(f"/api/v1/deposits/{dep}/respond", headers=th, json={"accept": True})
    sent, store = [], {}

    async def rec(did, amount, data_hash):
        sent.append(("deposit", did))
        store[did] = {"dataHash": data_hash}
        return "0x" + "a" * 64

    async def settle_tx(did, deducted, refunded, h):
        sent.append(("settle", did))
        return "0x" + "b" * 64

    async def read(did):
        return store.get(did)
    monkeypatch.setattr(chain, "enabled", lambda: True)
    monkeypatch.setattr(chain, "record_deposit", rec)
    monkeypatch.setattr(chain, "settle_deposit", settle_tx)
    monkeypatch.setattr(chain, "read_deposit", read)
    for _ in range(10):  # older test deposits are anchored too, 20 blocks per round
        if ("settle", dep) in sent:
            break
        await jobs.run_once()
    assert ("deposit", dep) in sent and ("settle", dep) in sent
    d = (await client.get(f"/api/v1/deposits/{dep}", headers=th)).json()
    assert d["receipt"]["network"] == "polygon-amoy" and d["receipt"]["recordTx"] == "0x" + "a" * 64
    assert d["verification"]["verified"] and d["verification"]["onChain"]
    count = len(sent)
    await jobs.run_once()
    assert len([s for s in sent[count:] if s[1] == dep]) == 0  # never sent twice
