import asyncio
from datetime import timedelta
import pytest
from app.core.config import settings
from app.core.security import create_access_token
from app.services import totp
from app.services.seed import seed_demo_admin
from app.core.database import AsyncSessionLocal
from tests.mailbox import MAILS
from tests.test_live_features import verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing

ADMIN_LOGIN = {"identifier": "admin", "password": "test-admin-password"}


@pytest.fixture(autouse=True)
def required(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TWO_FACTOR", "required")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def code(secret: str, ahead: int = 0) -> str:
    return totp.code_at(secret, totp.current_step() + ahead)


async def fresh_admin() -> None:  # tests share one database: start each from "no authenticator yet"
    from sqlalchemy import update
    from app.models.user import User
    async with AsyncSessionLocal() as db:
        await seed_demo_admin(db)
        await db.execute(update(User).where(User.email == settings.ADMIN_EMAILS[0]).values(
            totp_secret=None, totp_pending=None, totp_enabled_at=None, totp_last_step=None, recovery_codes=None,
            password_hash=None))
        await db.commit()
        await seed_demo_admin(db)  # puts the known password back


async def admin_with_authenticator(client) -> tuple[str, dict, list[str]]:
    await fresh_admin()
    first = (await client.post("/api/v1/auth/password-login", json=ADMIN_LOGIN)).json()
    plain = bearer(first["access_token"])
    setup = (await client.post("/api/v1/auth/2fa/setup", headers=plain)).json()
    on = (await client.post("/api/v1/auth/2fa/enable", headers=plain, json={"code": code(setup["secret"])})).json()
    return setup["secret"], bearer(on["access_token"]), on["recoveryCodes"]


async def test_admin_must_set_up_two_step_sign_in(client):
    await fresh_admin()
    res = (await client.post("/api/v1/auth/password-login", json=ADMIN_LOGIN)).json()
    assert res["user"]["twoFactor"] == {"enabled": False, "required": True, "verified": False}
    h = bearer(res["access_token"])
    blocked = await client.get("/api/v1/admin/overview", headers=h)
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "2fa_setup_required"
    setup = (await client.post("/api/v1/auth/2fa/setup", headers=h)).json()
    assert setup["qrSvg"].lstrip().startswith("<?xml") and "<svg" in setup["qrSvg"]
    assert setup["otpauthUri"].startswith("otpauth://totp/TrustRent%3Aadmin%40trustrent.in?secret=")
    wrong = await client.post("/api/v1/auth/2fa/enable", headers=h, json={"code": "000000"})
    assert wrong.status_code == 400
    on = await client.post("/api/v1/auth/2fa/enable", headers=h, json={"code": code(setup["secret"])})
    body = on.json()
    assert on.status_code == 200 and len(body["recoveryCodes"]) == 8 and body["user"]["twoFactor"]["verified"] is True
    assert (await client.get("/api/v1/admin/overview", headers=bearer(body["access_token"]))).status_code == 200
    old = await client.get("/api/v1/admin/overview", headers=h)  # the session from before the code
    assert old.status_code == 403 and old.json()["detail"]["code"] == "2fa_required"
    assert (await client.post("/api/v1/auth/2fa/setup", headers=bearer(body["access_token"]))).status_code == 409


async def test_sign_in_needs_the_code(client):
    secret, _, _ = await admin_with_authenticator(client)
    first = (await client.post("/api/v1/auth/password-login", json=ADMIN_LOGIN)).json()
    assert first["twoFactorRequired"] is True and "access_token" not in first
    assert (await client.get("/api/v1/users/me", headers=bearer(first["challenge"]))).status_code == 401  # not a session
    for _ in range(5):
        bad = await client.post("/api/v1/auth/2fa/verify", json={"challenge": first["challenge"], "code": "123456"})
        assert bad.status_code == 400
    locked = await client.post("/api/v1/auth/2fa/verify", json={"challenge": first["challenge"], "code": code(secret, 1)})
    assert locked.status_code == 429
    from app.core.ratelimit import TWO_FACTOR_FAILURES
    TWO_FACTOR_FAILURES.reset()
    ok = await client.post("/api/v1/auth/2fa/verify", json={"challenge": first["challenge"], "code": code(secret, 1)})
    assert ok.status_code == 200
    assert (await client.get("/api/v1/admin/users", headers=bearer(ok.json()["access_token"]))).status_code == 200
    again = await client.post("/api/v1/auth/2fa/verify", json={"challenge": first["challenge"], "code": code(secret, 1)})
    assert again.status_code == 400  # the same code can't be used twice
    expired = create_access_token(subject=ok.json()["user"]["id"], expires_delta=timedelta(seconds=-1), claims={"purpose": "2fa"})
    assert (await client.post("/api/v1/auth/2fa/verify", json={"challenge": expired, "code": code(secret)})).status_code == 401


async def test_recovery_codes_work_once_and_alert(client):
    _, h, codes = await admin_with_authenticator(client)
    MAILS.clear()
    first = (await client.post("/api/v1/auth/password-login", json=ADMIN_LOGIN)).json()
    ok = await client.post("/api/v1/auth/2fa/verify", json={"challenge": first["challenge"], "code": codes[0].upper().replace("-", " ")})
    assert ok.status_code == 200
    for _ in range(10):
        await asyncio.sleep(0)
    assert any(m["subject"] == "[TrustRent alert] Admin recovery code used" for m in MAILS)
    second = (await client.post("/api/v1/auth/password-login", json=ADMIN_LOGIN)).json()
    reuse = await client.post("/api/v1/auth/2fa/verify", json={"challenge": second["challenge"], "code": codes[0]})
    assert reuse.status_code == 400
    fresh = (await client.post("/api/v1/auth/2fa/recovery-codes", headers=h)).json()["recoveryCodes"]
    assert len(fresh) == 8 and not set(fresh) & set(codes)


async def test_no_side_doors(client):
    secret, h, _ = await admin_with_authenticator(client)
    admin_id = (await client.get("/api/v1/users/me", headers=h)).json()["user"]["id"]
    # a password reset still needs the authenticator code
    from tests.mailbox import OUTBOX
    await client.post("/api/v1/auth/password/forgot", json={"email": settings.ADMIN_EMAILS[0]})
    reset = await client.post("/api/v1/auth/password/reset", json={
        "email": settings.ADMIN_EMAILS[0], "code": OUTBOX[f"reset:{settings.ADMIN_EMAILS[0]}"], "password": "NewAdmin123"})
    assert reset.json()["twoFactorRequired"] is True and "access_token" not in reset.json()
    assert (await client.get("/api/v1/admin/users", headers=h)).status_code == 401  # the reset signed out old sessions
    ok = await client.post("/api/v1/auth/2fa/verify", json={"challenge": reset.json()["challenge"], "code": code(secret, 1)})
    h = bearer(ok.json()["access_token"])
    # an admin session without the code can't see documents or deposits through non-admin pages either
    no_code = bearer(create_access_token(subject=admin_id))
    owner, oh, listing = await owner_with_listing(client)
    tenant, th = await verified_tenant_with_visit(client, listing, oh)
    order = await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})
    dep = (await client.post("/api/v1/payments/verify", headers=th, json={"orderId": order.json()["orderId"]})).json()["depositId"]
    assert (await client.get(f"/api/v1/deposits/{dep}", headers=no_code)).status_code == 404
    assert (await client.post(f"/api/v1/owner/application/{owner['id']}/review", headers=no_code, json={"approve": False})).status_code == 403
    assert (await client.get("/api/v1/lawyers", headers=no_code)).status_code == 403
    assert (await client.get(f"/api/v1/deposits/{dep}", headers=h)).status_code == 200


async def test_operator_reset_script(client):
    import importlib.util
    from pathlib import Path
    await admin_with_authenticator(client)
    spec = importlib.util.spec_from_file_location("reset_2fa", Path(__file__).resolve().parents[1] / "scripts" / "reset_admin_2fa.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert await mod.main(settings.ADMIN_EMAILS[0]) == 0
    res = (await client.post("/api/v1/auth/password-login", json=ADMIN_LOGIN)).json()
    assert "access_token" in res and res["user"]["twoFactor"]["enabled"] is False
    assert await mod.main("nobody@example.com") == 1
