from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error, session
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.ratelimit import TWO_FACTOR_FAILURES
from app.core.security import decode_access_token
from app.models.marketplace import utcnow
from app.models.user import User
from app.services import totp
from app.services.accounts import admin_unlocked, hash_secret, is_admin, verify_secret
from app.services.monitoring import alert

router = APIRouter(prefix="/auth/2fa", tags=["Two-step sign-in"])

class VerifyIn(BaseModel):
    challenge: str = Field(max_length=2000)
    code: str = Field(max_length=20)

class CodeIn(BaseModel):
    code: str = Field(max_length=20)

def _admin(user: User) -> User:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admins only")
    return user

def _use_recovery_code(user: User, code: str) -> bool:
    wanted = totp.normalise_recovery(code)
    if not wanted:
        return False
    for stored in user.recovery_codes or []:
        if verify_secret(wanted, stored):
            user.recovery_codes = [c for c in user.recovery_codes if c != stored]
            return True
    return False

def _issue_recovery_codes(user: User) -> list[str]:
    codes = totp.new_recovery_codes()
    user.recovery_codes = [hash_secret(c) for c in codes]
    return codes

@router.post("/verify")
async def verify(body: VerifyIn, db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(body.challenge)
    if not payload or payload.get("purpose") != "2fa":
        raise field_error("This sign-in has expired. Enter your password again.", "challenge", status.HTTP_401_UNAUTHORIZED)
    user = await db.get(User, payload.get("sub"))
    if not user or not user.totp_secret or user.banned_at or user.deleted_at:
        raise field_error("This sign-in has expired. Enter your password again.", "challenge", status.HTTP_401_UNAUTHORIZED)
    if TWO_FACTOR_FAILURES.blocked(user.id):
        raise field_error("Too many wrong codes. Wait 15 minutes and sign in again.", "code", status.HTTP_429_TOO_MANY_REQUESTS)
    step = totp.verify(totp.unseal(user.totp_secret), body.code, user.totp_last_step)
    if step is not None:
        user.totp_last_step = step
    elif _use_recovery_code(user, body.code):
        alert(f"recovery:{user.id}", "Admin recovery code used",
              f"{user.email} signed in with a one-time recovery code ({len(user.recovery_codes or [])} left). "
              "If this wasn't them, change their password and reset their two-step sign-in.")
    else:
        TWO_FACTOR_FAILURES.hit(user.id)
        raise field_error("That code isn't right. Check your authenticator app and try again.", "code")
    TWO_FACTOR_FAILURES.reset(user.id)
    await db.commit()
    await db.refresh(user)
    return session(user, mfa=True)

@router.post("/setup")
async def setup(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _admin(user)
    if user.totp_enabled_at:
        raise field_error("Two-step sign-in is already on.", None, status.HTTP_409_CONFLICT)
    secret = totp.new_secret()
    user.totp_pending = totp.seal(secret)
    await db.commit()
    uri = totp.otpauth_uri(secret, user.email)
    return {"secret": secret, "otpauthUri": uri, "qrSvg": totp.qr_svg(uri)}

@router.post("/enable")
async def enable(body: CodeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _admin(user)
    if user.totp_enabled_at:
        raise field_error("Two-step sign-in is already on.", None, status.HTTP_409_CONFLICT)
    if not user.totp_pending:
        raise field_error("Start again: scan a new QR code.", "code")
    secret = totp.unseal(user.totp_pending)
    step = totp.verify(secret, body.code, None)
    if step is None:
        raise field_error("That code isn't right. Make sure your phone's time is set automatically, then try again.", "code")
    user.totp_secret, user.totp_pending, user.totp_last_step, user.totp_enabled_at = totp.seal(secret), None, step, utcnow()
    codes = _issue_recovery_codes(user)
    await db.commit()
    await db.refresh(user)
    return session(user, mfa=True) | {"recoveryCodes": codes}

@router.post("/recovery-codes")
async def new_recovery_codes(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _admin(user)
    if not user.totp_enabled_at or not admin_unlocked(user):
        raise field_error("Sign in with your authenticator code first.", None, status.HTTP_403_FORBIDDEN)
    codes = _issue_recovery_codes(user)
    await db.commit()
    return {"recoveryCodes": codes}
