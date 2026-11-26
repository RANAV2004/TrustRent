import secrets
import unicodedata
import uuid
from datetime import timedelta
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, EmailStr, Field, ValidationError, TypeAdapter
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import (
    EMAILS_PER_IP, LOGIN_FAILURES_PER_ACCOUNT, LOGIN_FAILURES_PER_IP, RESET_CODES_PER_EMAIL, SIGNUP_CODES_PER_EMAIL,
    client_ip,
)
from app.core.security import create_access_token
from app.models.marketplace import EmailVerification, IdentitySubmission, utcnow
from app.models.deposits import Payment
from app.models.user import User
from app.services.accounts import (
    USERNAME_RE, has_premium, hash_secret, is_admin, normalise_phone, role_for, user_out,
    verify_secret,
)
from app.services.hash_service import HashService
from app.services.mailer import EmailError, email_enabled, send_code_email, send_reset_email
from app.services.register import try_rebuild_register
from app.services.notify import notify_admins
from app.services.files import private_storage
router = APIRouter(tags=["Accounts (web app)"])
_email = TypeAdapter(EmailStr)
PLANS = {"week": (7, 99), "month": (30, 299), "quarter": (90, 699)}
ID_DOC_TYPES = {"Masked Aadhaar card", "PAN card", "Passport", "Voter ID", "Driving licence"}
MAX_DOC_BYTES = 10 * 1024 * 1024
def field_error(message: str, field: str | None = None, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail={"message": message, "field": field})
def valid_name(name: str) -> bool:
    return any(c.isalpha() for c in name) and all(
        c.isalpha() or unicodedata.category(c).startswith("M") or c in " .'-" for c in name)
DOC_HINT = "Upload a photo (JPG, PNG, WebP, HEIC) or a PDF of the document."
def is_document(content: bytes) -> bool:
    head = content[:16]
    return (head.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"%PDF-", b"GIF87a", b"GIF89a"))
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
            or (head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"heif", b"mif1", b"msf1", b"hevc")))
async def read_limited(upload: UploadFile, max_bytes: int, field: str, too_big: str) -> bytes:
    chunks, total = [], 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise field_error(too_big, field)
        chunks.append(chunk)
    return b"".join(chunks)
def session(user: User, mfa: bool = False) -> dict:
    if user.banned_at or user.deleted_at:
        raise field_error("This account has been suspended. Contact TrustRent support.", None, status.HTTP_403_FORBIDDEN)
    if is_admin(user) and user.totp_enabled_at and not mfa:
        challenge = create_access_token(subject=user.id, expires_delta=timedelta(minutes=5), claims={"purpose": "2fa"})
        return {"twoFactorRequired": True, "challenge": challenge}
    user._mfa = mfa
    claims = {"mfa": True} if mfa else None
    return {"access_token": create_access_token(subject=user.id, claims=claims), "token_type": "bearer", "user": user_out(user)}
class ProfileIn(BaseModel):
    firstName: str = Field(max_length=80)
    lastName: str = Field(max_length=80)
    username: str
    email: str
    phone: str
    country: str = Field(max_length=60)
class SignUpIn(ProfileIn):
    password: str = Field(max_length=200)
    accountType: str = "seeker"
    emailCode: str = ""
class PasswordLoginIn(BaseModel):
    identifier: str = Field(max_length=255)
    password: str = Field(max_length=200)
class GoogleIn(BaseModel):
    credential: str | None = None
    email: str | None = None
class ForgotIn(BaseModel):
    email: str
class ResetIn(BaseModel):
    email: str
    code: str = Field(max_length=12)
    password: str = Field(max_length=200)
class ChangePasswordIn(BaseModel):
    currentPassword: str = Field(default="", max_length=200)
    newPassword: str = Field(max_length=200)
class AccountTypeIn(BaseModel):
    accountType: str
class SubscriptionIn(BaseModel):
    planId: str
async def validate_profile(p: ProfileIn, db: AsyncSession, me: User | None = None) -> tuple[str, str]:
    if not p.firstName.strip():
        raise field_error("Enter your first name.", "firstName")
    if not p.lastName.strip():
        raise field_error("Enter your surname.", "lastName")
    for value, field in ((p.firstName, "firstName"), (p.lastName, "lastName")):
        if not valid_name(value.strip()):
            raise field_error("Use letters only (spaces, dots, hyphens and apostrophes are fine).", field)
    if not USERNAME_RE.match(p.username):
        raise field_error("Use 3 to 20 lowercase letters, numbers or underscores.", "username")
    try:
        email = str(_email.validate_python(p.email.strip())).lower()
    except ValidationError:
        raise field_error("Enter a valid email address.", "email") from None
    phone = normalise_phone(p.phone)
    if not 11 <= len(phone) <= 16:
        raise field_error("Enter a valid phone number with country code.", "phone")
    if not p.country.strip():
        raise field_error("Choose your country.", "country")
    me_id = me.id if me else ""
    if email in {e.lower() for e in settings.ADMIN_EMAILS} and (me is None or (me.email or "").lower() != email):
        raise field_error("An account with this email already exists. Sign in instead.", "email", status.HTTP_409_CONFLICT)
    for column, value, field, msg in (
        (User.username, p.username, "username", "That username is taken."),
        (User.email, email, "email", "An account with this email already exists. Sign in instead."),
        (User.phone, phone, "phone", "This phone number is already registered."),
    ):
        taken = await db.scalar(select(User.id).where(func.lower(column) == value.lower(), User.id != me_id))
        if taken:
            raise field_error(msg, field, status.HTTP_409_CONFLICT)
    return email, phone
def validate_password(pw: str) -> None:
    if len(pw) < 8 or not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        raise field_error("Use at least 8 characters, with a letter and a number.", "password")
def apply_profile(user: User, p: ProfileIn, email: str, phone: str) -> None:
    user.first_name = p.firstName.strip()
    user.last_name = p.lastName.strip()
    user.name = f"{user.first_name} {user.last_name}"
    user.username = p.username
    user.email = email
    user.phone = phone
    user.country = p.country.strip()
EMAIL_CODE_MINUTES = 10
async def validate_sign_up(body: SignUpIn, db: AsyncSession) -> tuple[str, str]:
    email, phone = await validate_profile(body, db)
    validate_password(body.password)
    if body.accountType not in ("seeker", "owner"):
        raise field_error("Choose whether you're looking for a home or renting one out.", "accountType")
    return email, phone
TOO_MANY_EMAILS = "Too many codes were requested from your network. Try again in an hour."
@router.post("/auth/signup/email-code")
async def sign_up_email_code(body: SignUpIn, request: Request, db: AsyncSession = Depends(get_db)):
    email, _ = await validate_sign_up(body, db)
    if not email_enabled():
        raise field_error("Sign-up is paused: email verification isn't set up on this server.", "email",
                          status.HTTP_503_SERVICE_UNAVAILABLE)
    if EMAILS_PER_IP.blocked(client_ip(request)):
        raise field_error(TOO_MANY_EMAILS, "email", status.HTTP_429_TOO_MANY_REQUESTS)
    if SIGNUP_CODES_PER_EMAIL.blocked(email):
        raise field_error("Too many codes were sent to this email today. Try again tomorrow.", "email",
                          status.HTTP_429_TOO_MANY_REQUESTS)
    code = f"{secrets.randbelow(10**6):06d}"
    row = await db.get(EmailVerification, email)
    if row is None:
        row = EmailVerification(email=email)
        db.add(row)
    elif row.expires_at and row.expires_at - timedelta(minutes=EMAIL_CODE_MINUTES - 1) > utcnow():
        raise field_error("Please wait a minute before asking for another code.", "email", status.HTTP_429_TOO_MANY_REQUESTS)
    row.code_hash = hash_secret(code)
    row.expires_at = utcnow() + timedelta(minutes=EMAIL_CODE_MINUTES)
    row.attempts = 0
    await db.commit()
    EMAILS_PER_IP.hit(client_ip(request))
    SIGNUP_CODES_PER_EMAIL.hit(email)
    try:
        await send_code_email(email, code, EMAIL_CODE_MINUTES)
    except EmailError as e:
        await db.delete(row)
        await db.commit()
        raise field_error(str(e), "email", status.HTTP_502_BAD_GATEWAY) from None
    return {"sent": True, "email": email}
async def check_email_code(db: AsyncSession, email: str, code: str, field: str = "emailCode", key: str | None = None) -> None:
    row = await db.get(EmailVerification, key or email)
    if not row or row.expires_at < utcnow():
        raise field_error("The code has expired. Ask for a new one.", field)
    row.attempts += 1
    if row.attempts > 5:
        await db.commit()
        raise field_error("Too many attempts. Ask for a new code.", field, status.HTTP_429_TOO_MANY_REQUESTS)
    if not verify_secret(code.strip(), row.code_hash):
        await db.commit()
        raise field_error("That code isn't right. Check the email and try again.", field)
    await db.delete(row)
@router.post("/auth/signup", status_code=201)
async def sign_up(body: SignUpIn, db: AsyncSession = Depends(get_db)):
    email, phone = await validate_sign_up(body, db)
    await check_email_code(db, email, body.emailCode)
    user = User(id=str(uuid.uuid4()), role=role_for(body.accountType), provider="password",
                password_hash=hash_secret(body.password), is_verified=False)
    apply_profile(user, body, email, phone)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise field_error("That username, email or phone was just registered. Try another.", None,
                          status.HTTP_409_CONFLICT) from None
    await db.refresh(user)
    return session(user)
@router.post("/auth/password-login")
async def password_login(body: PasswordLoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    ident = body.identifier.strip().lower()
    ip = client_ip(request)
    if LOGIN_FAILURES_PER_ACCOUNT.blocked(ident) or LOGIN_FAILURES_PER_IP.blocked(ip):
        raise field_error("Too many wrong passwords. Wait 15 minutes or reset your password.", None,
                          status.HTTP_429_TOO_MANY_REQUESTS)
    user = await db.scalar(select(User).where(or_(func.lower(User.email) == ident, func.lower(User.username) == ident)))
    if not user or not verify_secret(body.password, user.password_hash):
        LOGIN_FAILURES_PER_ACCOUNT.hit(ident)
        LOGIN_FAILURES_PER_IP.hit(ip)
        raise field_error("That username/email and password don't match.", None, status.HTTP_401_UNAUTHORIZED)
    LOGIN_FAILURES_PER_ACCOUNT.reset(ident)
    return session(user)
@router.post("/auth/google")
async def google_sign_in(body: GoogleIn, db: AsyncSession = Depends(get_db)):
    if body.credential and settings.GOOGLE_CLIENT_ID:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": body.credential})
        info = res.json() if res.status_code == 200 else {}
        if info.get("aud") != settings.GOOGLE_CLIENT_ID or info.get("email_verified") not in ("true", True):
            raise field_error("Google sign-in failed. Try again.", None, status.HTTP_401_UNAUTHORIZED)
        email, first, last = info["email"].lower(), info.get("given_name", ""), info.get("family_name", "")
    elif body.email and settings.DEMO_MODE:
        try:
            email = str(_email.validate_python(body.email.strip())).lower()
        except ValidationError:
            raise field_error("Enter a valid Google email.", "email") from None
        first, last = "", ""
        existing = await db.scalar(select(User).where(func.lower(User.email) == email))
        reserved = email in {e.lower() for e in settings.ADMIN_EMAILS}
        if reserved or (existing and (existing.provider != "google" or existing.password_hash)):
            raise field_error("Sign in with your password for this account.", "email", status.HTTP_403_FORBIDDEN)
    else:
        raise field_error("Google sign-in is not configured on this server.", None, status.HTTP_501_NOT_IMPLEMENTED)
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not user:
        user = User(id=str(uuid.uuid4()), email=email, name=f"{first} {last}".strip() or email.split("@")[0],
                    first_name=first or None, last_name=last or None, provider="google",
                    role=role_for("seeker"), is_verified=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return session(user)
RESET_SENT = "If an account uses that email, a reset code is on its way."
def _reset_key(email: str) -> str:
    return f"reset:{email}"
@router.post("/auth/password/forgot")
async def forgot_password(body: ForgotIn, request: Request, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    if not email_enabled():
        raise field_error("Password reset isn't available: email isn't set up on this server.", "email",
                          status.HTTP_503_SERVICE_UNAVAILABLE)
    if not EMAILS_PER_IP.allow(client_ip(request)):
        raise field_error(TOO_MANY_EMAILS, "email", status.HTTP_429_TOO_MANY_REQUESTS)
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or user.deleted_at or user.banned_at or user.is_demo:
        return {"ok": True, "message": RESET_SENT}
    row = await db.get(EmailVerification, _reset_key(email))
    if row and row.expires_at - timedelta(minutes=EMAIL_CODE_MINUTES - 1) > utcnow():
        return {"ok": True, "message": RESET_SENT}
    if not RESET_CODES_PER_EMAIL.allow(email):
        return {"ok": True, "message": RESET_SENT}
    if row is None:
        row = EmailVerification(email=_reset_key(email))
        db.add(row)
    code = f"{secrets.randbelow(10**6):06d}"
    row.code_hash, row.expires_at, row.attempts = hash_secret(code), utcnow() + timedelta(minutes=EMAIL_CODE_MINUTES), 0
    await db.commit()
    try:
        await send_reset_email(email, code, EMAIL_CODE_MINUTES)
    except EmailError as e:
        await db.delete(row)
        await db.commit()
        raise field_error(str(e), "email", status.HTTP_502_BAD_GATEWAY) from None
    return {"ok": True, "message": RESET_SENT}
@router.post("/auth/password/reset")
async def reset_password(body: ResetIn, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    validate_password(body.password)
    await check_email_code(db, email, body.code, field="code", key=_reset_key(email))
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or user.deleted_at:
        raise field_error("The code has expired. Ask for a new one.", "code")
    user.password_hash = hash_secret(body.password)
    user.password_changed_at = utcnow()
    await db.commit()
    await db.refresh(user)
    LOGIN_FAILURES_PER_ACCOUNT.reset(email)
    LOGIN_FAILURES_PER_ACCOUNT.reset((user.username or "").lower())
    return session(user)
@router.get("/users/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": user_out(user)}
@router.put("/users/me")
async def update_me(body: ProfileIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    email, phone = await validate_profile(body, db, me=user)
    if user.email and email != user.email.lower():
        raise field_error("Your email can't be changed here. Contact TrustRent support to change it.", "email")
    apply_profile(user, body, email, phone)
    await db.commit()
    await db.refresh(user)
    return {"user": user_out(user)}
@router.put("/users/me/password")
async def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.password_hash and not verify_secret(body.currentPassword, user.password_hash):
        raise field_error("Your current password isn't right.", "currentPassword")
    validate_password(body.newPassword)
    if user.password_hash and verify_secret(body.newPassword, user.password_hash):
        raise field_error("Choose a password different from the current one.", "newPassword")
    user.password_hash = hash_secret(body.newPassword)
    user.password_changed_at, user.must_change_password = utcnow(), False
    await db.commit()
    await db.refresh(user)
    return session(user)
@router.put("/users/me/account-type")
async def set_account_type(body: AccountTypeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.accountType not in ("seeker", "owner"):
        raise field_error("Unknown account type.", "accountType")
    if user.role.value == "arbitrator" or user.is_lawyer:
        raise field_error("This account can't switch type.", "accountType", status.HTTP_403_FORBIDDEN)
    user.role = role_for(body.accountType)
    await db.commit()
    await db.refresh(user)
    return {"user": user_out(user)}
@router.post("/users/me/identity")
async def upload_identity(
    docType: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if docType not in ID_DOC_TYPES:
        raise field_error("Choose a supported ID document.", "docType")
    content = await read_limited(file, MAX_DOC_BYTES, "file", "The file is larger than 10 MB.")
    if not content:
        raise field_error("Upload a photo or scan of the document.", "file")
    if not is_document(content):
        raise field_error(DOC_HINT, "file")
    sub_id = str(uuid.uuid4())
    path, iv = private_storage().store(f"identity_{user.id}_{sub_id[:8]}", content)
    doc_hash = HashService.hash_bytes(content)
    sub = IdentitySubmission(id=sub_id, user_id=user.id, doc_type=docType, file_name=file.filename or "id-document",
                             file_path=path, file_iv=iv, file_hash=doc_hash, status="pending")
    db.add(sub)
    user.attestation_hash = HashService.hash_text(f"{user.id}:{docType}:{doc_hash}")
    if settings.DEMO_MODE:
        sub.status, sub.reviewed_at, sub.reviewed_by = "approved", utcnow(), "Auto-approved (demo mode)"
        user.is_verified = True
    await db.commit()
    await db.refresh(user)
    await try_rebuild_register(db)
    if not user.is_verified:
        notify_admins("id-submission", "ID verification waiting", [
            "Someone uploaded an ID document. Review it on the Verifications page."], "/admin/verifications")
    return {"user": user_out(user), "pendingReview": not user.is_verified}
@router.post("/subscriptions")
async def subscribe(body: SubscriptionIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.planId not in PLANS:
        raise field_error("Unknown plan.", "planId")
    if user.is_lawyer:
        raise field_error("Lawyer accounts can't buy Premium.", None, status.HTTP_403_FORBIDDEN)
    if not user.is_verified:
        raise field_error("Verify your identity before buying Premium.", None, status.HTTP_403_FORBIDDEN)
    if not settings.DEMO_MODE:
        raise field_error("Payments are not configured on this server.", None, status.HTTP_402_PAYMENT_REQUIRED)
    days, price = PLANS[body.planId]
    start = user.premium_until if has_premium(user) else utcnow()
    user.premium_plan = body.planId
    user.premium_until = start + timedelta(days=days)
    db.add(Payment(id=str(uuid.uuid4()), user_id=user.id, purpose="premium", ref=body.planId, amount=price,
                   provider="demo", order_id=f"demo_{uuid.uuid4().hex[:16]}", status="paid", paid_at=utcnow()))
    await db.commit()
    await db.refresh(user)
    return {"user": user_out(user)}
@router.get("/subscriptions/plans")
async def plans():
    return [{"id": k, "days": d, "price": p} for k, (d, p) in PLANS.items()]
