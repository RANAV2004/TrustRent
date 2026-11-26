from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("purpose"):  # a half-finished sign-in (waiting for the authenticator code) is not a session
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    changed = user.password_changed_at
    if changed and float(payload.get("iat", 0)) < changed.replace(tzinfo=timezone.utc).timestamp():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your password was changed. Sign in again.")
    user._mfa = bool(payload.get("mfa"))  # this sign-in passed the authenticator check
    if user.banned_at or user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been suspended. Contact TrustRent support.")
    return user
