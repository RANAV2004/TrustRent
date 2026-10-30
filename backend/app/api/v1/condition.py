import io
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.deposits import ConditionPhoto, Deposit, LedgerEntry
from app.models.user import User
from app.services.accounts import display_name, iso, is_reviewer
from app.services.files import private_storage, read_private
from app.services.hash_service import HashService
from app.services.ledger import fingerprint, photo_details, record_photo
router = APIRouter(tags=["Condition photos"])
ROOMS = ["Hall / living room", "Bedroom 1", "Bedroom 2", "Bedroom 3", "Kitchen", "Bathroom 1", "Bathroom 2",
         "Balcony", "Entrance and doors", "Other"]
STAGES = ("move_in", "move_out")
OPEN_FOR = {"move_in": ("held",), "move_out": ("held", "settlement_proposed", "disputed")}
MAX_BYTES = 10 * 1024 * 1024
MAX_PER_STAGE = 30
MAX_SIDE = 2000
async def _deposit_for(db: AsyncSession, deposit_id: str, user: User) -> Deposit:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d or (user.id not in (d.tenant_id, d.owner_id) and not is_reviewer(user)):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d
def _side(d: Deposit, user: User) -> str | None:
    return "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else None
def clean_image(raw: bytes) -> bytes:  # strip location
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError):
        raise field_error("That file isn't a photo we can read. Use JPG, PNG or WebP.", "file") from None
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()
def photo_out(p: ConditionPhoto, names: dict[str, str], ledger: dict[str, str]) -> dict:
    recorded = ledger.get(p.record_tx or "")
    return {
        "id": p.id, "side": p.side, "stage": p.stage, "room": p.room, "note": p.note,
        "uploadedBy": names.get(p.uploader_id, ""), "uploadedAt": iso(p.created_at),
        "fileHash": p.file_hash, "receipt": p.record_tx,
        "verified": recorded is not None and recorded == p.record_hash == fingerprint(photo_details(p)),
    }
@router.get("/deposits/{deposit_id}/photos")  # photo list
async def list_photos(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit_for(db, deposit_id, user)
    side = _side(d, user)
    admin = is_reviewer(user)
    q = select(ConditionPhoto).where(ConditionPhoto.deposit_id == d.id)
    if not admin:
        q = q.where(ConditionPhoto.side == side)  # own photos only
    rows = list(await db.scalars(q.order_by(ConditionPhoto.created_at)))
    names = {}
    for uid in {r.uploader_id for r in rows}:
        u = await db.get(User, uid)
        names[uid] = display_name(u) if u else ""
    txs = [r.record_tx for r in rows if r.record_tx]
    ledger = {e.entry_hash: e.data_hash for e in await db.scalars(select(LedgerEntry).where(LedgerEntry.entry_hash.in_(txs)))} if txs else {}
    return {
        "rooms": ROOMS,
        "side": side,
        "compare": admin,
        "canUpload": {s: bool(side) and d.status in OPEN_FOR[s] for s in STAGES},
        "photos": [photo_out(r, names, ledger) for r in rows],
    }
@router.post("/deposits/{deposit_id}/photos", status_code=201)  # photo upload
async def upload_photo(
    deposit_id: str,
    stage: str = Form(...),
    room: str = Form(...),
    note: str = Form(default=""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    d = await _deposit_for(db, deposit_id, user)
    side = _side(d, user)
    if not side:
        raise HTTPException(status_code=403, detail="Only the tenant or the owner can add photos")
    if stage not in STAGES:
        raise field_error("Choose move-in or move-out.", "stage")
    if d.status not in OPEN_FOR[stage]:
        msg = "Move-in photos are closed once the move-out settlement starts." if stage == "move_in" else "This deposit is settled, so photos are closed."
        raise field_error(msg, "stage", status.HTTP_409_CONFLICT)
    if room not in ROOMS:
        raise field_error("Choose a room from the list.", "room")
    count = await db.scalar(select(func.count()).select_from(ConditionPhoto).where(
        ConditionPhoto.deposit_id == d.id, ConditionPhoto.side == side, ConditionPhoto.stage == stage))
    if count >= MAX_PER_STAGE:
        raise field_error(f"You can add up to {MAX_PER_STAGE} photos for each stage.", "file", status.HTTP_409_CONFLICT)
    raw = await file.read()
    if not raw:
        raise field_error("Choose a photo to upload.", "file")
    if len(raw) > MAX_BYTES:
        raise field_error("The photo is larger than 10 MB.", "file")
    content = clean_image(raw)
    pid = str(uuid.uuid4())
    path, iv = private_storage().store(f"condition_{d.id}_{pid[:8]}", content)
    p = ConditionPhoto(id=pid, deposit_id=d.id, uploader_id=user.id, side=side, stage=stage, room=room,
                       note=note.strip()[:200] or None, file_path=path, file_iv=iv,
                       file_hash=HashService.hash_bytes(content), record_hash="")
    db.add(p)
    await db.flush()
    await record_photo(db, p)
    await db.commit()
    return photo_out(p, {user.id: display_name(user)}, {p.record_tx: p.record_hash})
@router.get("/deposits/{deposit_id}/photos/{photo_id}/file")  # photo file
async def photo_file(deposit_id: str, photo_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit_for(db, deposit_id, user)
    p = await db.get(ConditionPhoto, photo_id)
    if not p or p.deposit_id != d.id or (not is_reviewer(user) and p.side != _side(d, user)):
        raise HTTPException(status_code=404, detail="Photo not found")
    try:
        content = read_private(p.file_path, p.file_iv)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="This photo's file is no longer stored on the server") from None
    return Response(content=content, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})