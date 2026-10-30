import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.tenancy import Tenancy, TenancyStateEnum
from app.schemas.tenancy import DraftTenancyResponse, TenancyResponse
from app.services.hash_service import HashService
from app.services.files import private_storage
from app.api.v1.auth import get_current_user
router = APIRouter(prefix="/tenancies", tags=["Tenancies"])
@router.post("/draft", response_model=DraftTenancyResponse)  # tenancy
async def draft_tenancy(
    property_address: str = Form(...),
    monthly_rent: Decimal = Form(...),
    deposit_amount: Decimal = Form(...),
    deduction_cap: Decimal = Form(...),
    claim_window_days: int = Form(7),
    tenant_email: str = Form(...),
    lease_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != UserRole.LANDLORD:
        raise HTTPException(status_code=403, detail="Only landlords can draft tenancies")
    if deduction_cap > deposit_amount:
        raise HTTPException(status_code=400, detail="Deduction cap cannot exceed deposit amount")
    stmt = select(User).where(User.email == tenant_email)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant with provided email not registered")
    content = await lease_file.read()
    lease_hash = HashService.hash_bytes(content)
    tenancy_id = str(uuid.uuid4())
    stored_path, iv_hex = private_storage().store(f"lease_{tenancy_id}", content)
    tenancy = Tenancy(
        id=tenancy_id,
        landlord_id=current_user.id,
        tenant_id=tenant.id,
        property_address=property_address,
        monthly_rent=monthly_rent,
        deposit_amount=deposit_amount,
        deduction_cap=deduction_cap,
        claim_window_days=claim_window_days,
        lease_hash=lease_hash,
        lease_storage_cid=stored_path,
        state=TenancyStateEnum.DRAFTED
    )
    db.add(tenancy)
    await db.commit()
    claim_window_seconds = claim_window_days * 86400
    return DraftTenancyResponse(
        tenancy_id=tenancy.id,
        lease_hash=lease_hash,
        storage_cid=stored_path,
        deposit_amount=deposit_amount,
        deduction_cap=deduction_cap,
        claim_window_seconds=claim_window_seconds,
        contract_deploy_params={
            "landlord": current_user.wallet_address or "",
            "tenant": tenant.wallet_address or "",
            "depositAmount": str(deposit_amount),
            "deductionCap": str(deduction_cap),
            "claimWindow": claim_window_seconds,
            "leaseHash": lease_hash
        }
    )
@router.get("/", response_model=list[TenancyResponse])  # tenancy
async def list_tenancies(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role == UserRole.LANDLORD:
        stmt = select(Tenancy).where(Tenancy.landlord_id == current_user.id)
    elif current_user.role == UserRole.TENANT:
        stmt = select(Tenancy).where(Tenancy.tenant_id == current_user.id)
    else:
        stmt = select(Tenancy)
    res = await db.execute(stmt)
    return res.scalars().all()
