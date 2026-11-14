from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import jwt
from jwt.exceptions import PyJWTError
from app.core.config import settings
MFA_TOKEN_MINUTES = 5


def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None, version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"exp": expire, "sub": str(subject), "ver": int(version or 0), "typ": "access"}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_mfa_token(subject: str, version: int = 0) -> str:  # proves the password step only
    expire = datetime.now(timezone.utc) + timedelta(minutes=MFA_TOKEN_MINUTES)
    return jwt.encode({"exp": expire, "sub": str(subject), "ver": int(version or 0), "typ": "mfa"},
                      settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except PyJWTError:
        return None


def decode_access_token(token: str) -> Optional[dict]:
    payload = _decode(token)
    if not payload or payload.get("typ", "access") != "access":
        return None
    return payload


def decode_mfa_token(token: str) -> Optional[dict]:
    payload = _decode(token)
    if not payload or payload.get("typ") != "mfa":
        return None
    return payload
