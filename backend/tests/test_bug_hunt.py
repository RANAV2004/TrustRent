"""Regression tests for the second bug hunt."""
import io
import json
from pathlib import Path
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.services.seed import seed_demo_admin
from tests.test_lawyers import approved_lawyer
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import PNG, owner_with_listing, signup
from tests.test_support import QUERY, png


# 1. A server error must still reach the website with CORS headers, or the browser hides the message.
async def test_server_error_keeps_cors_headers(monkeypatch):
    origin = settings.CORS_ORIGINS[0]

    def crash():
        raise RuntimeError("boom")
    monkeypatch.setattr("app.services.payments.razorpay_enabled", crash)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as ac:
        res = await ac.get("/api/v1/config", headers={"Origin": origin})
    assert res.status_code == 500 and res.headers.get("access-control-allow-origin") == origin
    assert "Something went wrong on our side" in res.json()["detail"]["message"]


# 3. Deleting a lawyer also takes their public photo offline.
async def test_deleted_lawyer_photo_is_removed(client):
    ah = await admin_headers(client)
    lawyer, _, _, _ = await approved_lawyer(client, ah)
    photo = Path(settings.MEDIA_DIR) / "lawyers" / f"{lawyer['id']}.jpg"
    assert photo.is_file()
    assert (await client.delete(f"/api/v1/admin/users/{lawyer['id']}", headers=ah)).status_code == 200
    assert not photo.exists()


# 4. A query rejected for a bad screenshot doesn't use up the daily allowance.
async def test_bad_screenshot_does_not_use_up_queries(client):
    _, uh = await signup(client)
    bad = [("images", ("x.png", io.BytesIO(b"not an image"), "image/png"))]
    for _ in range(12):
        assert (await client.post("/api/v1/support/tickets", headers=uh, data=QUERY, files=bad)).status_code == 400
    ok = await client.post("/api/v1/support/tickets", headers=uh, data=QUERY,
                           files=[("images", ("ok.png", io.BytesIO(png()), "image/png"))])
    assert ok.status_code == 201


# 5. A home with no deposit can't be "paid".
async def test_no_payment_for_a_zero_deposit(client):
    owner, oh, listing = await owner_with_listing(client)
    data = {k: listing[k] for k in ("title", "locality", "city", "pincode", "lat", "lng", "rent", "bhk", "furnishing",
                                     "area_sqft", "amenities", "preferred_tenants", "available_from", "min_months",
                                     "max_months", "description", "about_owner")}
    free = await client.post("/api/v1/owner/listings", headers=oh, data={"data": json.dumps(data | {"deposit": 0, "address": "Flat 9, Shanti Residency"})},
                             files=[("photos", ("1.png", io.BytesIO(PNG), "image/png"))])
    assert free.status_code == 201
    tenant, th = await verified_tenant_with_visit(client, free.json(), oh)
    res = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": free.json()["id"]})
    assert res.status_code == 400 and "no security deposit" in res.json()["detail"]["message"]


# 6. The admin password in the server settings must not undo a password the admin changed themselves.
async def test_settings_password_does_not_undo_a_reset(client):
    from tests.mailbox import OUTBOX
    admin = settings.ADMIN_EMAILS[0]
    async with AsyncSessionLocal() as db:
        await seed_demo_admin(db)
        await db.execute(update(User).where(User.email == admin).values(password_changed_at=None, totp_enabled_at=None,
                                                                            totp_secret=None, recovery_codes=None))
        await db.commit()
        await seed_demo_admin(db)
    await client.post("/api/v1/auth/password/forgot", json={"email": admin})
    reset = await client.post("/api/v1/auth/password/reset", json={"email": admin, "code": OUTBOX[f"reset:{admin}"], "password": "MyOwnPass123"})
    assert reset.status_code == 200
    async with AsyncSessionLocal() as db:  # a server restart
        await seed_demo_admin(db)
    login = lambda pw: client.post("/api/v1/auth/password-login", json={"identifier": "admin", "password": pw})  # noqa: E731
    assert (await login("MyOwnPass123")).status_code == 200
    assert (await login(settings.DEMO_ADMIN_PASSWORD)).status_code == 401
    async with AsyncSessionLocal() as db:  # put the test password back for the other tests
        await db.execute(update(User).where(User.email == admin).values(password_changed_at=None))
        await db.commit()
        await seed_demo_admin(db)
