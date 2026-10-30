import io
from sqlalchemy import create_engine, text
from app.core.database import AsyncSessionLocal, add_missing_columns
from app.services.seed import seed_demo_deposits, seed_sample_listings
from tests.test_live_features import admin_headers
from tests.test_marketplace import owner_with_listing, signup
async def test_demo_receipts_and_overview(client):
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)
        assert await seed_demo_deposits(db) == 3
        assert await seed_demo_deposits(db) == 0
    ah = await admin_headers(client)
    deps = {d["id"]: d for d in (await client.get("/api/v1/admin/deposits", headers=ah)).json()}
    assert {"DEP-DEMO0001", "DEP-DEMO0002", "DEP-DEMO0003"} <= set(deps)
    assert deps["DEP-DEMO0001"]["status"] == "held" and deps["DEP-DEMO0002"]["status"] == "settlement_proposed"
    assert deps["DEP-DEMO0003"]["status"] == "settled" and deps["DEP-DEMO0003"]["receipt"]["settleHash"]
    assert all(deps[k]["verification"]["verified"] for k in deps if k.startswith("DEP-DEMO"))
    led = (await client.get("/api/v1/admin/ledger", headers=ah)).json()
    assert led["intact"] and led["blocks"][0]["prevHash"] == led["genesis"]
    assert all(b["prevHash"] == a["hash"] for a, b in zip(led["blocks"], led["blocks"][1:]))
    ov = (await client.get("/api/v1/admin/overview", headers=ah)).json()
    assert ov["deposits"]["count"] >= 3 and ov["users"]["premium"] >= 2 and ov["conversations"] >= 3
    prem = (await client.get("/api/v1/admin/premium", headers=ah)).json()
    names = {m["name"] for m in prem["members"]}
    assert {"Aditi Joshi", "Rohan Mehta"} <= names and len(prem["plans"]) == 3
    convs = (await client.get("/api/v1/admin/conversations", headers=ah)).json()
    demo = next(c for c in convs if c["seeker"]["name"] == "Aditi Joshi")
    msgs = (await client.get(f"/api/v1/admin/conversations/{demo['id']}/messages", headers=ah)).json()
    assert len(msgs) == 4 and msgs[0]["from"] == "seeker" and msgs[1]["from"] == "owner"
async def test_admin_only(client):
    _, uh = await signup(client)
    for path in ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/premium", "/api/v1/admin/conversations"):
        assert (await client.get(path, headers=uh)).status_code == 403
async def test_ban_unban_and_listing_hidden(client):
    ah = await admin_headers(client)
    owner, oh, listing = await owner_with_listing(client)
    seeker, sh = await signup(client)
    me = (await client.get("/api/v1/users/me", headers=ah)).json()["user"]
    assert (await client.post(f"/api/v1/admin/users/{me['id']}/ban", headers=ah, json={})).status_code == 403
    res = await client.post(f"/api/v1/admin/users/{owner['id']}/ban", headers=ah, json={"reason": "Fake listing"})
    assert res.json()["user"]["banned"]["reason"] == "Fake listing"
    assert (await client.get("/api/v1/users/me", headers=oh)).status_code == 403
    login = await client.post("/api/v1/auth/password-login", json={"identifier": owner["username"], "password": "secret123"})
    assert login.status_code == 403 and "suspended" in login.json()["detail"]["message"]
    ids = [x["id"] for x in (await client.get("/api/v1/listings", headers=sh)).json()]
    assert listing["id"] not in ids
    await client.post(f"/api/v1/admin/users/{owner['id']}/unban", headers=ah)
    assert (await client.get("/api/v1/users/me", headers=oh)).status_code == 200
    rows = {u["id"]: u for u in (await client.get("/api/v1/admin/users", headers=ah)).json()}
    assert rows[owner["id"]]["banned"] is None and rows[owner["id"]]["listings"] == 1
async def test_unlist_and_relist(client):
    ah = await admin_headers(client)
    owner, oh, listing = await owner_with_listing(client)
    _, sh = await signup(client)
    res = await client.post(f"/api/v1/admin/listings/{listing['id']}/unlist", headers=ah, json={"reason": "Photos are of a different flat"})
    assert res.json()["status"] == "blocked"
    assert listing["id"] not in [x["id"] for x in (await client.get("/api/v1/listings", headers=sh)).json()]
    mine = (await client.get("/api/v1/owner/listings", headers=oh)).json()
    assert mine[0]["status"] == "blocked" and mine[0]["admin_note"] == "Photos are of a different flat"
    back = await client.patch(f"/api/v1/owner/listings/{listing['id']}", headers=oh, json={"status": "live"})
    assert back.status_code == 403
    await client.post(f"/api/v1/admin/listings/{listing['id']}/relist", headers=ah)
    assert listing["id"] in [x["id"] for x in (await client.get("/api/v1/listings", headers=sh)).json()]
async def test_delete_anonymises_and_premium_revoke(client):
    ah = await admin_headers(client)
    user, uh = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("pan.jpg", io.BytesIO(b"pan"), "image/jpeg")})
    await client.post("/api/v1/subscriptions", headers=uh, json={"planId": "month"})
    prem = (await client.get("/api/v1/admin/premium", headers=ah)).json()
    assert any(p["user"]["id"] == user["id"] and p["amount"] == 299 for p in prem["payments"])
    rev = await client.post(f"/api/v1/admin/premium/{user['id']}/revoke", headers=ah)
    assert rev.json()["user"]["premium"]["active"] is False
    assert (await client.post(f"/api/v1/admin/premium/{user['id']}/revoke", headers=ah)).status_code == 409
    gone = await client.delete(f"/api/v1/admin/users/{user['id']}", headers=ah)
    assert gone.status_code == 200
    rows = {u["id"]: u for u in (await client.get("/api/v1/admin/users", headers=ah)).json()}
    assert rows[user["id"]]["deletedAt"] and rows[user["id"]]["name"] == "Deleted user" and rows[user["id"]]["phone"] == ""
    assert (await client.get("/api/v1/users/me", headers=uh)).status_code == 403
    again = await client.post("/api/v1/auth/signup/email-code", json={
        "firstName": "A", "lastName": "B", "username": user["username"], "email": user["email"], "phone": user["phone"],
        "country": "India", "password": "secret123", "accountType": "seeker"})
    assert again.status_code == 200
async def test_delete_blocked_by_open_deposit(client):
    async with AsyncSessionLocal() as db:
        await seed_sample_listings(db)
        await seed_demo_deposits(db)
    ah = await admin_headers(client)
    rows = (await client.get("/api/v1/admin/users", headers=ah)).json()
    aditi = next(u for u in rows if u["name"] == "Aditi Joshi")
    res = await client.delete(f"/api/v1/admin/users/{aditi['id']}", headers=ah)
    assert res.status_code == 409 and "DEP-DEMO0001" in res.json()["detail"]["message"]
def test_add_missing_columns(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255), name VARCHAR(255), role VARCHAR(10))")
        added = add_missing_columns(conn)
        assert "users.banned_at" in added and "users.deleted_at" in added
        conn.execute(text("SELECT banned_at, ban_reason, deleted_at, premium_until FROM users"))
        assert add_missing_columns(conn) == []
async def test_admin_records_offline_deposit(client):
    ah = await admin_headers(client)
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await signup(client)
    body = {"tenant": "@" + tenant["username"], "listingId": listing["id"].lower(), "amount": 34000, "transactionId": "UPI-41802233917"}
    res = await client.post("/api/v1/admin/deposits", headers=ah, json=body)
    assert res.status_code == 201, res.text
    d = res.json()
    assert d["status"] == "held" and d["amount"] == 34000 and d["tenant"]["id"] == tenant["id"]
    assert d["receipt"]["recordHash"].startswith("0x") and d["receipt"]["recordTx"] and d["verification"]["verified"]
    assert d["payment"] == {"provider": "manual", "reference": "UPI-41802233917"}
    assert any(x["id"] == d["id"] for x in (await client.get("/api/v1/deposits", headers=th)).json())
    assert any(x["id"] == d["id"] for x in (await client.get("/api/v1/deposits", headers=oh)).json())
    found = await client.get("/api/v1/deposits/lookup", headers=th, params={"q": d["receipt"]["recordHash"]})
    assert found.json()["id"] == d["id"]
    again = await client.post("/api/v1/admin/deposits", headers=ah, json=body | {"transactionId": "UPI-41802233917"})
    assert again.status_code == 409 and again.json()["detail"]["field"] == "transactionId"
    dup = await client.post("/api/v1/admin/deposits", headers=ah, json=body | {"transactionId": "NEFT-0001"})
    assert dup.status_code == 409 and dup.json()["detail"]["field"] == "listingId"
    nobody = await client.post("/api/v1/admin/deposits", headers=ah, json=body | {"tenant": "no_such_user", "transactionId": "X-9999"})
    assert nobody.status_code == 404 and nobody.json()["detail"]["field"] == "tenant"
    own = await client.post("/api/v1/admin/deposits", headers=ah, json=body | {"tenant": owner["id"], "transactionId": "X-8888"})
    assert own.status_code == 409
    assert (await client.post("/api/v1/admin/deposits", headers=th, json=body | {"transactionId": "X-7777"})).status_code == 403
    settled = await client.post(f"/api/v1/admin/deposits/{d['id']}/settle", headers=ah, json={"deducted": 4000, "reason": "Broken window glass replaced"})
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "settled" and settled.json()["refundRef"] == "manual-refund"
