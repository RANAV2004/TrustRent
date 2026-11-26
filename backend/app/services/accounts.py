import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from app.core.config import settings
from app.models.marketplace import utcnow
from app.models.user import User, UserRole
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
def hash_secret(secret: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"
def verify_secret(secret: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(secret.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)
def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="milliseconds") + "Z"
def account_type(user: User) -> str:
    if user.is_lawyer:
        return "lawyer"
    return "owner" if user.role == UserRole.LANDLORD else "seeker"
def role_for(account: str) -> UserRole:
    return UserRole.LANDLORD if account == "owner" else UserRole.TENANT
def display_name(user: User) -> str:
    if user.first_name:
        return f"{user.first_name} {user.last_name or ''}".strip()
    return user.name
def is_admin(user: User) -> bool:
    return (user.email or "").lower() in {e.lower() for e in settings.ADMIN_EMAILS}
def two_factor_required() -> bool:
    return settings.ADMIN_TWO_FACTOR != "optional"
def admin_unlocked(user: User) -> bool:  # an admin whose sign-in meets the two-step rules
    if not is_admin(user):
        return False
    if user.totp_enabled_at:
        return bool(getattr(user, "_mfa", False))
    return not two_factor_required()
def is_reviewer(user: User) -> bool:
    return admin_unlocked(user) or user.role == UserRole.ARBITRATOR
def has_premium(user: User) -> bool:
    return bool(user.premium_until and user.premium_until > utcnow())
def user_out(user: User) -> dict:
    first = user.first_name
    last = user.last_name
    if first is None:
        parts = (user.name or "").split(" ", 1)
        first, last = parts[0], parts[1] if len(parts) > 1 else ""
    email = user.email
    return {
        "id": user.id,
        "firstName": first or "",
        "lastName": last or "",
        "username": user.username or "",
        "email": email,
        "phone": user.phone or "",
        "country": user.country or "",
        "provider": user.provider or "password",
        "accountType": account_type(user),
        "role": user.role.value if user.role else "tenant",
        "idVerified": bool(user.is_verified),
        "isAdmin": is_admin(user),
        "mustChangePassword": bool(user.must_change_password),
        "twoFactor": {"enabled": bool(user.totp_enabled_at), "required": two_factor_required(),
                      "verified": bool(getattr(user, "_mfa", False))} if is_admin(user) else None,
        "premium": {"planId": user.premium_plan, "until": iso(user.premium_until)} if has_premium(user) else None,
        "createdAt": iso(user.created_at) or "",
    }
def normalise_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw or "")
    return digits if digits.startswith("+") else f"+{digits}"
