import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.core.config import settings
from app.models.user import User, UserRole
from app.services.accounts import is_admin
from app.schemas.user import UserLoginRequest, TokenResponse, UserResponse
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
    user_id = payload.get("sub")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or int(payload.get("ver") or 0) != int(user.token_version or 0):  # signed out everywhere
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if user.banned_at or user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been suspended. Contact TrustRent support.")
    return user
@router.post("/login", response_model=TokenResponse)  # wallet login
async def login_or_register(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    if not (settings.DEMO_MODE and settings.ENABLE_LEGACY_API):  # demo wallet login only
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if is_admin(User(email=request.email)) or request.role == UserRole.ARBITRATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use the normal sign-in for this account")
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user and (user.password_hash or user.provider in ("google", "password") or user.role == UserRole.ARBITRATOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use the normal sign-in for this account")
    if request.smart_account_address:  # one wallet per account (unique column)
        owner = await db.scalar(select(User.id).where(User.wallet_address == request.smart_account_address))
        if owner and (not user or owner != user.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This wallet is linked to another account")
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=request.email,
            name=request.name,
            role=request.role,
            wallet_address=request.smart_account_address,
            is_verified=False
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif request.smart_account_address and user.wallet_address != request.smart_account_address:
        user.wallet_address = request.smart_account_address
        await db.commit()
        await db.refresh(user)
    token = create_access_token(subject=user.id, version=user.token_version or 0)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )
@router.get("/me", response_model=UserResponse)  # profile
async def get_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
