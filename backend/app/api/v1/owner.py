from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import ID_DOC_TYPES, MAX_DOC_BYTES, field_error
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.marketplace import OwnerApplication, utcnow
from app.models.user import User
from app.services.accounts import iso, is_reviewer
from app.services.hash_service import HashService
from app.services.files import private_storage
from app.services.register import try_rebuild_register
router = APIRouter(tags=["Owner verification"])
RELATIONS = {"owner", "co-owner", "authorised"}
PROPERTY_DOC_TYPES = {"Sale deed / title deed", "Latest property tax receipt", "Electricity bill in owner's name",
                      "Society share certificate", "Registered rent authorisation"}
class ReviewIn(BaseModel):
    approve: bool
    note: str | None = None
def application_out(a: OwnerApplication) -> dict:
    return {
        "userId": a.user_id,
        "status": a.status,
        "relation": a.relation,
        "idDocType": a.id_doc_type,
        "idFileName": a.id_file_name,
        "propertyDocType": a.property_doc_type,
        "propertyFileName": a.property_file_name,
        "propertyAddress": a.property_address,
        "submittedAt": iso(a.submitted_at),
        "reviewedAt": iso(a.reviewed_at),
        "reviewNote": a.review_note,
        "idFileHash": a.id_file_hash,
        "propertyFileHash": a.property_file_hash,
    }
async def _read_doc(upload: UploadFile, field: str) -> bytes:
    content = await upload.read()
    if not content:
        raise field_error("Upload a photo or scan of the document.", field)
    if len(content) > MAX_DOC_BYTES:
        raise field_error("The file is larger than 10 MB.", field)
    return content
@router.get("/owner/application")  # owner verify
async def get_application(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    app = await db.get(OwnerApplication, user.id)
    return {"application": application_out(app) if app else None}
@router.post("/owner/application", status_code=201)  # owner verify
async def submit_application(
    relation: str = Form(...),
    idDocType: str = Form(...),
    propertyDocType: str = Form(...),
    propertyAddress: str = Form(...),
    idFile: UploadFile = File(...),
    propertyFile: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if relation not in RELATIONS:
        raise field_error("Choose your relation to the property.", "relation")
    if idDocType not in ID_DOC_TYPES:
        raise field_error("Choose a supported ID document.", "idDocType")
    if propertyDocType not in PROPERTY_DOC_TYPES:
        raise field_error("Choose a supported property document.", "propertyDocType")
    if len(propertyAddress.strip()) < 10:
        raise field_error("Enter the full address of the property.", "propertyAddress")
    existing = await db.get(OwnerApplication, user.id)
    if existing and existing.status == "approved":
        raise field_error("You're already verified.", None, status.HTTP_409_CONFLICT)
    id_bytes = await _read_doc(idFile, "idFile")
    prop_bytes = await _read_doc(propertyFile, "propertyFile")
    store = private_storage()
    id_path, id_iv = store.store(f"owner_id_{user.id}", id_bytes)
    prop_path, prop_iv = store.store(f"owner_property_{user.id}", prop_bytes)
    app = existing or OwnerApplication(user_id=user.id)
    app.status = "submitted"
    app.relation = relation
    app.id_doc_type, app.id_file_name = idDocType, idFile.filename or "id-document"
    app.id_file_path, app.id_file_iv, app.id_file_hash = id_path, id_iv, HashService.hash_bytes(id_bytes)
    app.property_doc_type, app.property_file_name = propertyDocType, propertyFile.filename or "property-document"
    app.property_file_path, app.property_file_iv = prop_path, prop_iv
    app.property_file_hash = HashService.hash_bytes(prop_bytes)
    app.property_address = propertyAddress.strip()
    app.submitted_at, app.reviewed_at, app.reviewed_by, app.review_note = utcnow(), None, None, None
    if not existing:
        db.add(app)
    await db.commit()
    await db.refresh(app)
    await try_rebuild_register(db)
    return {"application": application_out(app)}
@router.post("/owner/application/{user_id}/review")  # owner review
async def review_application(user_id: str, body: ReviewIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    self_demo = settings.DEMO_MODE and user.id == user_id
    if not (is_reviewer(user) or self_demo):
        raise HTTPException(status_code=403, detail="Admins only")
    app = await db.get(OwnerApplication, user_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app.status = "approved" if body.approve else "rejected"
    app.reviewed_at, app.reviewed_by = utcnow(), user.id
    app.review_note = None if body.approve else (body.note or "The property document was unclear. Upload a sharper photo of every page.")
    await db.commit()
    await db.refresh(app)
    await try_rebuild_register(db)
    return {"application": application_out(app)}
