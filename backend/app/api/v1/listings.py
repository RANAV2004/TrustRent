import json
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.marketplace import Conversation, Listing, Message, OwnerApplication, utcnow
from app.models.user import User
from app.services.files import save_public
from app.services.marketplace import listing_out, visit_confirmed
router = APIRouter(tags=["Listings"])
FURNISHING = {"furnished", "semi-furnished", "unfurnished"}
TENANTS = {"family", "bachelor_male", "bachelor_female", "student", "any"}
AMENITIES = {"parking", "lift", "power_backup", "wifi", "ac", "gym", "security", "water_24x7",
             "balcony", "pets_allowed", "washing_machine", "near_metro"}
MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
class ListingIn(BaseModel):
    title: str = Field(min_length=8, max_length=120)
    address: str = Field(min_length=3, max_length=300)
    locality: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=60)
    pincode: str = Field(pattern=r"^\d{6}$")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    show_exact_location: bool = False
    rent: int = Field(ge=1000, le=10_000_000)
    deposit: int = Field(ge=0, le=100_000_000)
    bhk: int = Field(ge=0, le=10)
    furnishing: str
    area_sqft: int = Field(default=0, ge=0, le=100_000)
    amenities: list[str] = []
    preferred_tenants: list[str] = ["any"]
    available_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    min_months: int = Field(ge=1, le=60)
    max_months: int = Field(ge=1, le=60)
    description: str = Field(min_length=30, max_length=5000)
    about_owner: str = Field(default="", max_length=2000)
class StatusIn(BaseModel):
    status: str
async def _owners(db: AsyncSession, ids: set[str]) -> dict[str, User]:
    if not ids:
        return {}
    rows = await db.scalars(select(User).where(User.id.in_(ids)))
    return {u.id: u for u in rows}
async def _confirmed_listing_ids(db: AsyncSession, seeker_id: str) -> set[str]:
    stmt = (
        select(Conversation.listing_id)
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.seeker_id == seeker_id, Message.kind == "visit", Message.visit_status == "accepted")
    )
    return set(await db.scalars(stmt))
@router.get("/listings")  # listings
async def list_listings(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(Listing).where(Listing.status == "live").order_by(Listing.listed_at.desc())))
    owners = await _owners(db, {r.owner_id for r in rows})
    rows = [r for r in rows if not (owners.get(r.owner_id) and owners[r.owner_id].banned_at)]
    confirmed = await _confirmed_listing_ids(db, user.id)
    base = str(request.base_url)
    return [listing_out(r, owners.get(r.owner_id), exact=r.owner_id == user.id or r.id in confirmed, base_url=base) for r in rows]
@router.get("/listings/{listing_id}")  # listing
async def get_listing(listing_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(Listing, listing_id)
    if not row or (row.status != "live" and row.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Listing not found")
    owner = await db.get(User, row.owner_id)
    if owner and owner.banned_at and row.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Listing not found")
    exact = row.owner_id == user.id or await visit_confirmed(db, row.id, user.id)
    return listing_out(row, owner, exact=exact, base_url=str(request.base_url))
async def require_approved_owner(user: User, db: AsyncSession) -> None:
    app = await db.get(OwnerApplication, user.id)
    if not app or app.status != "approved":
        raise field_error("Get verified as an owner before listing a home.", None, status.HTTP_403_FORBIDDEN)
@router.get("/owner/listings")  # my listings
async def my_listings(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Listing).where(Listing.owner_id == user.id, Listing.status != "removed").order_by(Listing.listed_at.desc()))
    return [listing_out(r, user, exact=True, base_url=str(request.base_url)) for r in rows]
@router.post("/owner/listings", status_code=201)  # add listing
async def create_listing(
    request: Request,
    data: str = Form(..., description="ListingIn as JSON"),
    photos: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_approved_owner(user, db)
    try:
        body = ListingIn.model_validate(json.loads(data))
    except (ValueError, ValidationError) as e:
        first = e.errors()[0] if isinstance(e, ValidationError) else None
        field = str(first["loc"][0]) if first and first.get("loc") else None
        raise field_error(f"Check the {field or 'listing'} field." if field else "Listing data is not valid JSON.", field) from None
    if body.furnishing not in FURNISHING:
        raise field_error("Unknown furnishing.", "furnishing")
    if body.max_months < body.min_months:
        raise field_error("Maximum stay must be at least the minimum stay.", "max_months")
    if set(body.amenities) - AMENITIES or set(body.preferred_tenants) - TENANTS:
        raise field_error("Unknown facility or tenant type.", "amenities")
    if not photos or len(photos) > MAX_PHOTOS:
        raise field_error(f"Add between 1 and {MAX_PHOTOS} photos.", "photos")
    listing_id = f"TR-{uuid.uuid4().hex[:8].upper()}"
    saved: list[str] = []
    for i, photo in enumerate(photos):
        ext = PHOTO_TYPES.get(photo.content_type or "")
        content = await photo.read()
        if not ext:
            raise field_error(f"{photo.filename} is not a JPEG, PNG or WebP image.", "photos")
        if len(content) > MAX_PHOTO_BYTES:
            raise field_error(f"{photo.filename} is larger than 5 MB.", "photos")
        saved.append(save_public(f"listings/{listing_id}/{i + 1}{ext}", content, photo.content_type or "image/jpeg"))
    row = Listing(id=listing_id, owner_id=user.id, photos=saved, status="live", listed_at=utcnow(),
                  **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return listing_out(row, user, exact=True, base_url=str(request.base_url))
@router.patch("/owner/listings/{listing_id}")  # listing status
async def set_status(listing_id: str, body: StatusIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(Listing, listing_id)
    if not row or row.owner_id != user.id or row.status == "removed":
        raise HTTPException(status_code=404, detail="Listing not found")
    if row.status == "blocked":
        raise field_error(f"TrustRent unlisted this home: {row.admin_note or 'it breaks the listing rules'}. Contact support to relist it.",
                          "status", status.HTTP_403_FORBIDDEN)
    if body.status not in ("live", "paused"):
        raise field_error("Status must be live or paused.", "status")
    row.status = body.status
    await db.commit()
    return listing_out(row, user, exact=True, base_url=str(request.base_url))
@router.delete("/owner/listings/{listing_id}", status_code=204)  # delete listing
async def delete_listing(listing_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(Listing, listing_id)
    if not row or row.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Listing not found")
    has_chats = await db.scalar(select(Conversation.id).where(Conversation.listing_id == listing_id).limit(1))
    if has_chats:
        row.status = "removed"
    else:
        await db.delete(row)
    await db.commit()
