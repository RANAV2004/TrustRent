from sqlalchemy import update
from app.core import totp
from app.core.database import AsyncSessionLocal
from app.models.user import User


async def finish_mfa(client, res) -> dict:
    """Completes the staff two-step sign-in in tests. Returns the session body."""
    body = res.json()
    if not body.get("mfaRequired"):
        return body
    from app.core.security import decode_mfa_token
    uid = decode_mfa_token(body["mfaToken"])["sub"]
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uid)
        secret = user.totp_secret
        await db.execute(update(User).where(User.id == uid).values(totp_last_step=None))  # allow several logins per 30 s
        await db.commit()
    done = await client.post("/api/v1/auth/mfa/verify", json={"mfaToken": body["mfaToken"], "code": totp.code_at(secret)})
    assert done.status_code == 200, done.text
    return done.json()
