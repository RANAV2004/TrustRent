import asyncio
import io
import re
from PIL import Image
from app.core.config import settings
from tests.mailbox import MAILS
from tests.test_live_features import admin_headers
from tests.test_marketplace import signup


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (60, 40), (200, 30, 30)).save(out, format="PNG")
    return out.getvalue()


QUERY = {"category": "Payments and Premium", "subject": "Premium not active after paying",
         "description": "I paid for the monthly plan but my account still shows the free plan.", "pageUrl": "/premium"}


async def raise_query(client, headers, images=2, **over):
    files = [("images", (f"shot{i}.png", io.BytesIO(png()), "image/png")) for i in range(images)]
    return await client.post("/api/v1/support/tickets", headers=headers, data=QUERY | over, files=files or None)


async def settle():
    for _ in range(10):
        await asyncio.sleep(0)


async def test_raise_query_and_find_it(client):
    user, uh = await signup(client)
    MAILS.clear()
    res = await raise_query(client, uh)
    assert res.status_code == 201, res.text
    t = res.json()
    assert re.fullmatch(r"TKT-\d{6}-[A-HJ-NP-Z2-9]{4}", t["ticketNo"]) and t["status"] == "open"
    assert len(t["images"]) == 2 and t["timeline"] == [] and t["pageUrl"] == "/premium" and "user" not in t
    await settle()
    assert any(m["subject"] == f"We got your query {t['ticketNo']}" and m["to"] == user["email"] for m in MAILS)
    assert any(m["subject"] == "[TrustRent admin] New support query" for m in MAILS)
    # search: case, spaces and missing dashes don't matter
    loose = t["ticketNo"].lower().replace("-", " ")
    found = await client.get(f"/api/v1/support/tickets/{loose}", headers=uh)
    assert found.status_code == 200 and found.json()["ticketNo"] == t["ticketNo"]
    assert [x["ticketNo"] for x in (await client.get("/api/v1/support/tickets", headers=uh)).json()] == [t["ticketNo"]]
    img = await client.get(f"/api/v1/support/tickets/{t['ticketNo']}/images/{t['images'][0]['id']}", headers=uh)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content[:3] == b"\xff\xd8\xff"
    # someone else can't find or open it
    _, xh = await signup(client)
    nope = await client.get(f"/api/v1/support/tickets/{t['ticketNo']}", headers=xh)
    assert nope.status_code == 404 and "No ticket of yours" in nope.json()["detail"]
    assert (await client.get(f"/api/v1/support/tickets/{t['ticketNo']}/images/{t['images'][0]['id']}", headers=xh)).status_code == 404
    assert (await client.get("/api/v1/support/tickets/TKT-000000-AAAA", headers=uh)).status_code == 404


async def test_ticket_numbers_are_unique(client):
    _, uh = await signup(client)
    nos = set()
    for _ in range(10):
        nos.add((await raise_query(client, uh, images=0)).json()["ticketNo"])
    assert len(nos) == 10
    limited = await raise_query(client, uh, images=0)
    assert limited.status_code == 429  # 10 a day per person


async def test_query_validation(client):
    _, uh = await signup(client)
    assert (await raise_query(client, uh, category="Gossip")).json()["detail"]["field"] == "category"
    assert (await raise_query(client, uh, subject="Hi")).json()["detail"]["field"] == "subject"
    assert (await raise_query(client, uh, description="Broken")).json()["detail"]["field"] == "description"
    six = [("images", (f"{i}.png", io.BytesIO(png()), "image/png")) for i in range(6)]
    res = await client.post("/api/v1/support/tickets", headers=uh, data=QUERY, files=six)
    assert res.status_code == 400 and res.json()["detail"]["field"] == "images"
    fake = [("images", ("bug.png", io.BytesIO(b"<script>alert(1)</script>"), "image/png"))]
    res = await client.post("/api/v1/support/tickets", headers=uh, data=QUERY, files=fake)
    assert res.status_code == 400 and "isn't an image" in res.json()["detail"]["message"]
    assert (await client.post("/api/v1/support/tickets", data=QUERY)).status_code in (401, 403)  # must be signed in


async def test_admin_replies_and_closes(client):
    ah = await admin_headers(client)
    user, uh = await signup(client)
    no = (await raise_query(client, uh, images=1)).json()["ticketNo"]
    # the user adds a screenshot
    more = await client.post(f"/api/v1/support/tickets/{no}/messages", headers=uh, data={"text": "Here's the payment page too."},
                             files=[("images", ("pay.png", io.BytesIO(png()), "image/png"))])
    assert more.status_code == 201 and more.json()["timeline"][-1]["images"]
    # admin queue: filters, search, counts
    assert (await client.get("/api/v1/admin/support", headers=uh)).status_code == 403
    queue = (await client.get("/api/v1/admin/support", headers=ah, params={"status": "open"})).json()
    row = next(x for x in queue["tickets"] if x["ticketNo"] == no)
    assert row["user"]["email"] == user["email"] and queue["counts"]["open"] >= 1
    assert [x["ticketNo"] for x in (await client.get("/api/v1/admin/support", headers=ah, params={"q": no.lower()})).json()["tickets"]] == [no]
    assert any(x["ticketNo"] == no for x in (await client.get("/api/v1/admin/support", headers=ah, params={"q": user["email"]})).json()["tickets"])
    assert (await client.get("/api/v1/admin/overview", headers=ah)).json()["openQueries"] >= 1
    detail = (await client.get(f"/api/v1/support/tickets/{no}", headers=ah)).json()
    assert detail["isSupport"] is True and detail["user"]["email"] == user["email"] and len(detail["images"]) == 1
    MAILS.clear()
    replied = await client.post(f"/api/v1/support/tickets/{no}/messages", headers=ah, data={"text": "Thanks, we're checking with Razorpay."})
    assert replied.json()["status"] == "in_progress" and replied.json()["timeline"][-1]["author"] == "TrustRent support"
    # closing needs a resolution note
    assert (await client.post(f"/api/v1/admin/support/{no}/status", headers=ah, json={"status": "closed"})).status_code == 400
    assert (await client.post(f"/api/v1/admin/support/{no}/status", headers=uh, json={"status": "closed", "note": "done!"})).status_code == 403
    closed = await client.post(f"/api/v1/admin/support/{no}/status", headers=ah,
                               json={"status": "closed", "note": "Premium is now active until 26 Dec."})
    assert closed.json()["status"] == "closed" and closed.json()["resolution"].startswith("Premium is now active")
    await settle()
    mine = [m["subject"] for m in MAILS if m["to"] == user["email"]]
    assert f"TrustRent support replied to {no}" in mine and f"Your query {no} is resolved" in mine
    # the user sees the result, but can't write on a closed ticket
    seen = (await client.get(f"/api/v1/support/tickets/{no}", headers=uh)).json()
    assert seen["status"] == "closed" and seen["canReply"] is False and seen["timeline"][-1]["statusLabel"] == "Closed"
    assert (await client.post(f"/api/v1/support/tickets/{no}/messages", headers=uh, data={"text": "Thanks!"})).status_code == 409
    assert (await client.post(f"/api/v1/admin/support/{no}/status", headers=ah, json={"status": "closed", "note": "again"})).status_code == 409
    reopened = await client.post(f"/api/v1/admin/support/{no}/status", headers=ah, json={"status": "open", "note": "Reopened to check"})
    assert reopened.json()["status"] == "open" and reopened.json()["resolution"] is None


async def test_deleting_a_user_removes_their_screenshots(client):
    ah = await admin_headers(client)
    user, uh = await signup(client)
    t = (await raise_query(client, uh, images=1)).json()
    assert (await client.delete(f"/api/v1/admin/users/{user['id']}", headers=ah)).status_code == 200
    after = (await client.get(f"/api/v1/support/tickets/{t['ticketNo']}", headers=ah)).json()
    assert after["images"] == [] and after["subject"] == QUERY["subject"]
    assert settings.ADMIN_EMAILS
