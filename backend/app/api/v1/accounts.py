import secrets
import uuid
from datetime import timedelta
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, Field, ValidationError, TypeAdapter
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.marketplace import EmailVerification, IdentitySubmission, utcnow
from app.models.deposits import Payment
from app.models.user import User
from app.services.accounts import (
    USERNAME_RE, has_premium, hash_secret, normalise_phone, role_for, user_out,
    verify_secret,
)
from app.services.hash_service import HashService
from app.services.mailer import EmailError, email_enabled, send_code_email
from app.services.register import try_rebuild_register
from app.services.files import private_storage
router = APIRouter(tags=["Accounts (web app)"])
_email = TypeAdapter(EmailStr)
PLANS = {"week": (7, 99), "month": (30, 299), "quarter": (90, 699)}
ID_DOC_TYPES = {"Masked Aadhaar card", "PAN card", "Passport", "Voter ID", "Driving licence"}
MAX_DOC_BYTES = 10 * 1024 * 1024
def field_error(message: str, field: str | None = None, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail={"message": message, "field": field})
def session(user: User) -> dict:
    if user.banned_at or user.deleted_at:
        raise field_error("This account has been suspended. Contact TrustRent support.", None, status.HTTP_403_FORBIDDEN)
    return {"access_token": create_access_token(subject=user.id), "token_type": "bearer", "user": user_out(user)}
class ProfileIn(BaseModel):
    firstName: str = Field(max_length=80)
    lastName: str = Field(max_length=80)
    username: str
    email: str
    phone: str
    country: str = Field(max_length=60)
class SignUpIn(ProfileIn):
    password: str
    accountType: str = "seeker"
    emailCode: str = ""
class PasswordLoginIn(BaseModel):
    identifier: str
    password: str
class GoogleIn(BaseModel):
    credential: str | None = None
    email: str | None = None
class ForgotIn(BaseModel):
    email: str
class AccountTypeIn(BaseModel):
    accountType: str
class SubscriptionIn(BaseModel):
    planId: str
async def validate_profile(p: ProfileIn, db: AsyncSession, me: User | None = None) -> tuple[str, str]:
    if not p.firstName.strip():
        raise field_error("Enter your first name.", "firstName")
    if not p.lastName.strip():
        raise field_error("Enter your surname.", "lastName")
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
@router.post("/auth/signup/email-code")  # signup code
async def sign_up_email_code(body: SignUpIn, db: AsyncSession = Depends(get_db)):
    email, _ = await validate_sign_up(body, db)
    if not email_enabled():
        raise field_error("Sign-up is paused: email verification isn't set up on this server.", "email",
                          status.HTTP_503_SERVICE_UNAVAILABLE)
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
    try:
        await send_code_email(email, code, EMAIL_CODE_MINUTES)
    except EmailError as e:
        await db.delete(row)
        await db.commit()
        raise field_error(str(e), "email", status.HTTP_502_BAD_GATEWAY) from None
    return {"sent": True, "email": email}
async def check_email_code(db: AsyncSession, email: str, code: str) -> None:
    row = await db.get(EmailVerification, email)
    if not row or row.expires_at < utcnow():
        raise field_error("The code has expired. Ask for a new one.", "emailCode")
    row.attempts += 1
    if row.attempts > 5:
        await db.commit()
        raise field_error("Too many attempts. Ask for a new code.", "emailCode", status.HTTP_429_TOO_MANY_REQUESTS)
    if not verify_secret(code.strip(), row.code_hash):
        await db.commit()
        raise field_error("That code isn't right. Check the email and try again.", "emailCode")
    await db.delete(row)
@router.post("/auth/signup", status_code=201)  # sign up
async def sign_up(body: SignUpIn, db: AsyncSession = Depends(get_db)):
    email, phone = await validate_sign_up(body, db)
    await check_email_code(db, email, body.emailCode)
    user = User(id=str(uuid.uuid4()), role=role_for(body.accountType), provider="password",
                password_hash=hash_secret(body.password), is_verified=False)
    apply_profile(user, body, email, phone)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return session(user)
@router.post("/auth/password-login")  # user login
async def password_login(body: PasswordLoginIn, db: AsyncSession = Depends(get_db)):
    ident = body.identifier.strip().lower()
    user = await db.scalar(select(User).where(or_(func.lower(User.email) == ident, func.lower(User.username) == ident)))
    if not user or not verify_secret(body.password, user.password_hash):
        raise field_error("That username/email and password don't match.", None, status.HTTP_401_UNAUTHORIZED)
    return session(user)
@router.post("/auth/google")  # google login
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
@router.post("/auth/password/forgot")  # forgot password
async def forgot_password(body: ForgotIn):
    return {"ok": True, "message": "If an account uses that email, a reset link is on its way."}
@router.get("/users/me")  # profile
async def me(user: User = Depends(get_current_user)):
    return {"user": user_out(user)}
@router.put("/users/me")  # edit profile
async def update_me(body: ProfileIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    email, phone = await validate_profile(body, db, me=user)
    apply_profile(user, body, email, phone)
    await db.commit()
    await db.refresh(user)
    return {"user": user_out(user)}
@router.put("/users/me/account-type")  # account type
async def set_account_type(body: AccountTypeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.accountType not in ("seeker", "owner"):
        raise field_error("Unknown account type.", "accountType")
    if user.role.value == "arbitrator":
        raise field_error("Arbitrator accounts can't switch type.", "accountType", status.HTTP_403_FORBIDDEN)
    user.role = role_for(body.accountType)
    await db.commit()
    await db.refresh(user)
    return {"user": user_out(user)}
@router.post("/users/me/identity")  # id upload
async def upload_identity(
    docType: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if docType not in ID_DOC_TYPES:
        raise field_error("Choose a supported ID document.", "docType")
    content = await file.read()
    if not content:
        raise field_error("Upload a photo or scan of the document.", "file")
    if len(content) > MAX_DOC_BYTES:
        raise field_error("The file is larger than 10 MB.", "file")
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
    return {"user": user_out(user), "pendingReview": not user.is_verified}
@router.post("/subscriptions")  # premium
async def subscribe(body: SubscriptionIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.planId not in PLANS:
        raise field_error("Unknown plan.", "planId")
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
@router.get("/subscriptions/plans")  # premium plans
async def plans():
    return [{"id": k, "days": d, "price": p} for k, (d, p) in PLANS.items()]
