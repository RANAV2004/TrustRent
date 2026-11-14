import mimetypes
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.api.v1.owner import application_out
from app.core.database import get_db
from app.models.marketplace import IdentitySubmission, OwnerApplication, utcnow
from app.models.user import User
from app.services.accounts import display_name, iso, is_admin, is_reviewer
from app.services.notify import notify
from app.services.files import read_private
from app.services.register import rebuild_register, try_rebuild_register
router = APIRouter(prefix="/admin", tags=["Admin"])
class DecisionIn(BaseModel):
    approve: bool
    note: str | None = None
def require_admin(user: User = Depends(get_current_user)) -> User:  # admin console: ADMIN_EMAILS only
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admins only")
    return user
require_full_admin = require_admin  # documents, users and approvals: ADMIN_EMAILS only


def require_reviewer(user: User = Depends(get_current_user)) -> User:  # deposits and disputes: admins and arbitrators
    if not is_reviewer(user):
        raise HTTPException(status_code=403, detail="Admins and arbitrators only")
    return user
SAFE_INLINE = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
def _person(u: User | None) -> dict:
    if not u:
        return {"name": "", "email": "", "phone": "", "username": ""}
    return {"name": display_name(u), "email": u.email, "phone": u.phone or "", "username": u.username or ""}
def identity_out(s: IdentitySubmission) -> dict:
    return {
        "id": s.id, "userId": s.user_id, "docType": s.doc_type, "fileName": s.file_name, "fileHash": s.file_hash,
        "status": s.status, "submittedAt": iso(s.submitted_at), "reviewedAt": iso(s.reviewed_at),
        "reviewNote": s.review_note,
    }
@router.get("/verifications")  # admin verify
async def verifications(admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    users = {u.id: u for u in await db.scalars(select(User))}
    owners = await db.scalars(select(OwnerApplication).order_by(OwnerApplication.submitted_at.desc()))
    ids = await db.scalars(select(IdentitySubmission).order_by(IdentitySubmission.submitted_at.desc()))
    return {
        "owners": [{**application_out(a), "applicant": _person(users.get(a.user_id))} for a in owners],
        "identities": [{**identity_out(s), "applicant": _person(users.get(s.user_id))} for s in ids],
    }
def _file_response(content: bytes, name: str) -> Response:
    media = mimetypes.guess_type(name or "")[0] or "application/octet-stream"
    safe = "".join(c for c in (name or "document") if c.isalnum() or c in "._- ")[:100] or "document"
    inline = media in SAFE_INLINE  # never render uploaded HTML or SVG in the admin's browser
    return Response(content=content, media_type=media if inline else "application/octet-stream", headers={
        "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{safe}"',
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    })
@router.get("/owner-applications/{user_id}/{doc}")  # owner docs
async def owner_document(user_id: str, doc: str, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    app = await db.get(OwnerApplication, user_id)
    if not app or doc not in ("id", "property"):
        raise HTTPException(status_code=404, detail="Not found")
    path, iv, name = ((app.id_file_path, app.id_file_iv, app.id_file_name) if doc == "id"
                      else (app.property_file_path, app.property_file_iv, app.property_file_name))
    return _file_response(read_private(path, iv), name)
@router.get("/identity/{submission_id}/file")  # id doc
async def identity_document(submission_id: str, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    s = await db.get(IdentitySubmission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    return _file_response(read_private(s.file_path, s.file_iv), s.file_name)
@router.post("/identity/{submission_id}/review")  # id review
async def review_identity(submission_id: str, body: DecisionIn, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    s = await db.get(IdentitySubmission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    s.status = "approved" if body.approve else "rejected"
    s.reviewed_at, s.reviewed_by = utcnow(), admin.id
    s.review_note = None if body.approve else (body.note or "The document was unclear. Upload a sharper photo.")
    user = await db.get(User, s.user_id)
    if user:
        if body.approve:
            user.is_verified = True
        else:  # keep verified if another document of theirs was approved
            other = await db.scalar(select(IdentitySubmission.id).where(
                IdentitySubmission.user_id == user.id, IdentitySubmission.id != s.id,
                IdentitySubmission.status == "approved").limit(1))
            user.is_verified = other is not None
    await db.commit()
    await try_rebuild_register(db)
    notify(user, "ID " + ("verified" if body.approve else "needs another look"),
           ["Your ID is verified. You can now pay deposits and buy Premium."] if body.approve
           else [f"We couldn't verify your ID: {s.review_note}", "Upload a clearer photo on the Premium page."], "/premium")
    return {"submission": identity_out(s)}
@router.get("/verification-register.xlsx")  # excel register
async def download_register(admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    path = await rebuild_register(db)
    return FileResponse(path, filename="TrustRent_verification_register.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Cache-Control": "no-store"})
