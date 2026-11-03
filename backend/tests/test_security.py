"""Regression tests for the account-takeover and self-verification holes."""
import io
from sqlalchemy import func, select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services.seed import seed_demo_admin
from tests.test_api_edge_cases import make_arbitrator
from tests.test_live_features import admin_headers
from tests.test_marketplace import profile, signup, tag
ADMIN = "admin@trustrent.in"
def legacy(email: str, role: str = "tenant") -> dict:
    return {"email": email, "name": "Someone", "role": role}
async def test_legacy_login_cannot_take_over_admin_or_real_accounts(client):
    await admin_headers(client)  # the admin account exists
    for email in (ADMIN, ADMIN.upper()):
        res = await client.post("/api/v1/auth/login", json=legacy(email))
        assert res.status_code == 403 and "access_token" not in res.text
    user, _ = await signup(client)  # a normal password account
    res = await client.post("/api/v1/auth/login", json=legacy(user["email"]))
    assert res.status_code == 403 and "access_token" not in res.text
    google = (await client.post("/api/v1/auth/google", json={"email": f"g_{tag()}@gmail.com"})).json()["user"]
    assert (await client.post("/api/v1/auth/login", json=legacy(google["email"]))).status_code == 403
    arb, _ = await make_arbitrator()
    assert (await client.post("/api/v1/auth/login", json=legacy(arb.email))).status_code == 403
async def test_admin_email_cannot_be_registered_before_admin_exists(client, monkeypatch):
    spare = f"boss_{tag()}@trustrent.in"
    monkeypatch.setattr(settings, "ADMIN_EMAILS", [ADMIN, spare])
    assert (await client.post("/api/v1/auth/login", json=legacy(spare))).status_code == 403
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(User.id).where(func.lower(User.email) == spare)) is None
async def test_nobody_can_self_register_as_arbitrator(client):
    res = await client.post("/api/v1/auth/login", json=legacy(f"arb_{tag()}@example.com", "arbitrator"))
    assert res.status_code == 403 and "access_token" not in res.text
async def test_legacy_login_is_off_outside_demo_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert (await client.post("/api/v1/auth/login", json=legacy(f"t_{tag()}@example.com"))).status_code == 404
async def test_identity_verify_endpoint_does_not_verify(client):
    _, h = await signup(client)
    res = await client.post("/api/v1/identity/verify", headers=h, json={
        "full_name": "Riya", "id_type": "AADHAAR", "id_number": "1234-5678-9012", "phone": "+919876543210"})
    assert res.status_code == 200 and res.json()["verified"] is False
    assert (await client.get("/api/v1/users/me", headers=h)).json()["user"]["idVerified"] is False
async def test_only_a_real_admin_reviews_documents(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)  # no auto-approval
    user, uh = await signup(client)
    owner, oh = await signup(client, "owner")
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("pan.jpg", io.BytesIO(b"pan"), "image/jpeg")})
    await client.post("/api/v1/owner/application", headers=oh,
                      data={"relation": "owner", "idDocType": "PAN card", "propertyDocType": "Sale deed / title deed",
                            "propertyAddress": "Flat 9, Lotus Court, Indore 452001"},
                      files={"idFile": ("id.jpg", io.BytesIO(b"id"), "image/jpeg"),
                             "propertyFile": ("deed.pdf", io.BytesIO(b"deed"), "application/pdf")})
    ah = await admin_headers(client)
    sub = next(s for s in (await client.get("/api/v1/admin/verifications", headers=ah)).json()["identities"]
               if s["userId"] == user["id"])
    _, arh = await make_arbitrator()
    for h in (uh, arh):  # neither the user nor an arbitrator can approve
        assert (await client.post(f"/api/v1/admin/identity/{sub['id']}/review", headers=h, json={"approve": True})).status_code == 403
        assert (await client.get(f"/api/v1/admin/identity/{sub['id']}/file", headers=h)).status_code == 403
        assert (await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=h, json={"approve": True})).status_code == 403
        assert (await client.get(f"/api/v1/admin/owner-applications/{owner['id']}/id", headers=h)).status_code == 403
    assert (await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=oh, json={"approve": True})).status_code == 403
    assert (await client.get("/api/v1/users/me", headers=uh)).json()["user"]["idVerified"] is False
    ok = await client.post(f"/api/v1/admin/identity/{sub['id']}/review", headers=ah, json={"approve": True})
    assert ok.status_code == 200
    assert (await client.get("/api/v1/users/me", headers=uh)).json()["user"]["idVerified"] is True
async def test_cannot_become_admin_by_changing_email(client, monkeypatch):
    spare = f"boss_{tag()}@trustrent.in"
    monkeypatch.setattr(settings, "ADMIN_EMAILS", [ADMIN, spare])
    user, h = await signup(client)
    for email in (spare, spare.upper(), ADMIN):
        res = await client.put("/api/v1/users/me", headers=h, json=profile(user["username"][5:]) | {
            "username": user["username"], "phone": user["phone"], "email": email})
        assert res.status_code in (403, 409), res.text
    me = (await client.get("/api/v1/users/me", headers=h)).json()["user"]
    assert me["isAdmin"] is False and me["email"] == user["email"]
    assert (await client.get("/api/v1/admin/users", headers=h)).status_code == 403
async def test_demo_google_shortcut_refuses_admin_email(client):
    await admin_headers(client)
    res = await client.post("/api/v1/auth/google", json={"email": ADMIN})
    assert res.status_code == 403 and "access_token" not in res.text
async def test_admin_account_is_kept_outside_demo_mode(client, monkeypatch):
    await admin_headers(client)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "DEMO_ADMIN_PASSWORD", "Production-only-pass-42")
    async with AsyncSessionLocal() as db:
        await seed_demo_admin(db)  # used to be skipped entirely when DEMO_MODE was off
    res = await client.post("/api/v1/auth/password-login", json={"identifier": "admin", "password": "Production-only-pass-42"})
    assert res.status_code == 200 and res.json()["user"]["isAdmin"] is True
async def test_uploaded_documents_cannot_run_in_admin_browser(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    user, uh = await signup(client)
    evil = b"<script>alert(document.cookie)</script>"
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("id.html", io.BytesIO(evil), "text/html")})
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "Passport"},
                      files={"file": ("passport.jpg", io.BytesIO(b"jpg"), "image/jpeg")})
    ah = await admin_headers(client)
    subs = {s["fileName"]: s for s in (await client.get("/api/v1/admin/verifications", headers=ah)).json()["identities"]
            if s["userId"] == user["id"]}
    html_id = subs["id.html"]["id"]
    html = await client.get(f"/api/v1/admin/identity/{html_id}/file", headers=ah)
    assert html.content == evil  # still downloadable for review...
    assert html.headers["content-type"] == "application/octet-stream"  # ...but never rendered
    assert html.headers["content-disposition"] == 'attachment; filename="id.html"'
    assert html.headers["x-content-type-options"] == "nosniff" and "sandbox" in html.headers["content-security-policy"]
    jpg = await client.get(f"/api/v1/admin/identity/{subs['passport.jpg']['id']}/file", headers=ah)
    assert jpg.headers["content-type"] == "image/jpeg" and jpg.headers["content-disposition"].startswith("inline")
