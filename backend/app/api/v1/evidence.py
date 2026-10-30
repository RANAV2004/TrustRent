import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.tenancy import Tenancy
from app.models.evidence import Evidence, EvidenceType
from app.services.hash_service import HashService
from app.services.files import private_storage, read_private
from app.api.v1.auth import get_current_user
router = APIRouter(prefix="/evidence", tags=["Condition Evidence"])
@router.post("/upload")  # evidence
async def upload_evidence(
    tenancy_id: str = Form(...),
    evidence_type: EvidenceType = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Tenancy).where(Tenancy.id == tenancy_id)
    res = await db.execute(stmt)
    tenancy = res.scalar_one_or_none()
    if not tenancy:
        raise HTTPException(status_code=404, detail="Tenancy not found")
    if current_user.id != tenancy.landlord_id and current_user.id != tenancy.tenant_id:
        raise HTTPException(status_code=403, detail="Only tenancy parties can submit evidence")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds maximum 10 MB limit")
    file_hash = HashService.hash_bytes(content)
    evidence_id = str(uuid.uuid4())
    stored_path, iv_hex = private_storage().store(f"evidence_{evidence_id}", content)
    manifest_hash = HashService.combine_manifest([file_hash])
    evidence = Evidence(
        id=evidence_id,
        tenancy_id=tenancy_id,
        submitted_by_id=current_user.id,
        evidence_type=evidence_type,
        file_name=file.filename or "evidence_file",
        mime_type=file.content_type or "application/octet-stream",
        file_hash=file_hash,
        manifest_hash=manifest_hash,
        storage_path=stored_path,
        encryption_iv=iv_hex
    )
    db.add(evidence)
    await db.commit()
    return {
        "evidence_id": evidence.id,
        "file_hash": file_hash,
        "manifest_hash": manifest_hash,
        "message": "Evidence securely encrypted and stored. Anchoring hash ready for on-chain submission."
    }
@router.get("/{evidence_id}/verify")  # evidence
async def verify_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Evidence).where(Evidence.id == evidence_id)
    res = await db.execute(stmt)
    evidence = res.scalar_one_or_none()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    try:
        decrypted_bytes = read_private(evidence.storage_path, evidence.encryption_iv)
        recomputed_hash = HashService.hash_bytes(decrypted_bytes)
        matches = (recomputed_hash == evidence.file_hash)
        return {
            "evidence_id": evidence.id,
            "recorded_hash": evidence.file_hash,
            "computed_hash": recomputed_hash,
            "matches": matches,
            "status": "VALID_TAMPER_FREE" if matches else "HASH_MISMATCH_TAMPERED"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evidence verification failed: {str(e)}")
@router.get("/{evidence_id}/download")  # evidence
async def download_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Evidence).where(Evidence.id == evidence_id)
    res = await db.execute(stmt)
    evidence = res.scalar_one_or_none()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    stmt_tenancy = select(Tenancy).where(Tenancy.id == evidence.tenancy_id)
    res_tenancy = await db.execute(stmt_tenancy)
    tenancy = res_tenancy.scalar_one_or_none()
    is_party = tenancy and (current_user.id in [tenancy.landlord_id, tenancy.tenant_id])
    is_arbitrator = (current_user.role == UserRole.ARBITRATOR)
    if not (is_party or is_arbitrator):
        raise HTTPException(status_code=403, detail="Unauthorized access to confidential evidence")
    decrypted_bytes = read_private(evidence.storage_path, evidence.encryption_iv)
    return Response(
        content=decrypted_bytes,
        media_type=evidence.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{evidence.file_name}"'}
    )
