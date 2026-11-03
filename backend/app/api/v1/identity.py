import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import MockVerifyRequest, VerificationResult
from app.services.hash_service import HashService
from app.api.v1.auth import get_current_user
router = APIRouter(prefix="/identity", tags=["Identity & Attestation"])
@router.post("/verify", response_model=VerificationResult)  # identity
async def verify_identity(
    request: MockVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Records an attestation hash only. Accounts become verified when an admin approves the
    # ID document uploaded at POST /users/me/identity, never from details the user typed in.
    if len(request.id_number.strip()) < 8:
        raise HTTPException(status_code=400, detail="Invalid government identification format")
    attestation_payload = f"{current_user.id}:{request.id_type}:{request.id_number}:{time.time()}"
    attestation_hash = HashService.hash_text(attestation_payload)
    current_user.attestation_hash = attestation_hash
    await db.commit()
    verified = bool(current_user.is_verified)
    return VerificationResult(
        verified=verified,
        attestation_hash=attestation_hash,
        transaction_hash=None,
        message="Identity already verified." if verified else
                "Attestation recorded. Upload your ID document; an admin must approve it before your account is verified."
    )
