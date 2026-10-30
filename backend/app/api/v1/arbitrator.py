from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.tenancy import Tenancy, TenancyStateEnum
from app.schemas.tenancy import TenancyResponse
from app.api.v1.auth import get_current_user
router = APIRouter(prefix="/arbitrator", tags=["Arbitrator Operations"])
@router.get("/disputes", response_model=list[TenancyResponse])  # arbitrator
async def list_assigned_disputes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != UserRole.ARBITRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to approved arbitrators"
        )
    stmt = select(Tenancy).where(Tenancy.state == TenancyStateEnum.DISPUTED)
    res = await db.execute(stmt)
    return res.scalars().all()
@router.get("/disputes/{tenancy_id}", response_model=TenancyResponse)  # arbitrator
async def get_dispute_details(
    tenancy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != UserRole.ARBITRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to approved arbitrators"
        )
    stmt = select(Tenancy).where(Tenancy.id == tenancy_id)
    res = await db.execute(stmt)
    tenancy = res.scalar_one_or_none()
    if not tenancy:
        raise HTTPException(status_code=404, detail="Disputed tenancy not found")
    return tenancy
