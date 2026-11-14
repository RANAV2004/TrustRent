import json
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.marketplace import Conversation, Listing, Message, OwnerApplication, utcnow
from app.models.user import User
from app.core.ratelimit import enforce
from app.services.files import save_public
from app.services.images import clean_image, read_limited
from app.services.marketplace import listing_out, visit_confirmed
from app.services.reputation import owner_stats, record_for
from app.services.search import SORTS, Filters, matches, trust_score
router = APIRouter(tags=["Listings"])
FURNISHING = {"furnished", "semi-furnished", "unfurnished"}
TENANTS = {"family", "bachelor_male", "bachelor_female", "student", "any"}
AMENITIES = {"parking", "lift", "power_backup", "wifi", "ac", "gym", "security", "water_24x7",
             "balcony", "pets_allowed", "washing_machine", "near_metro"}
MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PAGE_SIZE = 100
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
def _csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _sort(rows: list, key: str, records: dict) -> list:
    if key == "rent-asc":
        return sorted(rows, key=lambda r: r.rent)
    if key == "rent-desc":
        return sorted(rows, key=lambda r: -r.rent)
    if key == "available":
        return sorted(rows, key=lambda r: r.available_from or "")
    if key == "trust":
        return sorted(rows, key=lambda r: -trust_score(records[r.id]))
    if key == "recommended":
        return sorted(rows, key=lambda r: (-(trust_score(records[r.id]) + (0.3 if r.rent and r.deposit / r.rent <= 2 else 0)), r.rent))
    return rows  # newest: already ordered


@router.get("/listings")  # listings + search
async def list_listings(
    request: Request, response: Response,
    q: str = "", budgetMin: int | None = None, budgetMax: int | None = None, bhk: str | None = None,
    furnishing: str | None = None, amenities: str | None = None, tenantType: str = "",
    depositWithinCap: bool = False, withHistory: bool = False, availableBy: str = "",
    sort: str = "newest", page: int | None = Query(default=None, ge=1), pageSize: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    if sort not in SORTS:
        raise field_error("Unknown sort order.", "sort")
    f = Filters.from_dict({"q": q, "budgetMin": budgetMin, "budgetMax": budgetMax, "bhk": _csv(bhk),
                           "furnishing": _csv(furnishing), "amenities": _csv(amenities), "tenantType": tenantType,
                           "depositWithinCap": depositWithinCap, "withHistory": withHistory, "availableBy": availableBy})
    rows = list(await db.scalars(select(Listing).where(Listing.status == "live").order_by(Listing.listed_at.desc())))
    owners = await _owners(db, {r.owner_id for r in rows})
    rows = [r for r in rows if not (owners.get(r.owner_id) and owners[r.owner_id].banned_at)]
    stats = await owner_stats(db, {r.owner_id for r in rows})
    records = {r.id: record_for(r, stats.get(r.owner_id)) for r in rows}
    rows = _sort([r for r in rows if matches(r, f, records[r.id]["tenancies_completed"])], sort, records)
    response.headers["X-Total-Count"] = str(len(rows))
    if page is not None:
        rows = rows[(page - 1) * pageSize: page * pageSize]
    confirmed = await _confirmed_listing_ids(db, user.id)
    base = str(request.base_url)
    return [listing_out(r, owners.get(r.owner_id), exact=r.owner_id == user.id or r.id in confirmed, base_url=base,
                        record=records[r.id]) for r in rows]


@router.get("/listings/{listing_id}")  # listing
async def get_listing(listing_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(Listing, listing_id)
    if not row or (row.status != "live" and row.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Listing not found")
    owner = await db.get(User, row.owner_id)
    if owner and owner.banned_at and row.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Listing not found")
    exact = row.owner_id == user.id or await visit_confirmed(db, row.id, user.id)
    stats = await owner_stats(db, {row.owner_id})
    return listing_out(row, owner, exact=exact, base_url=str(request.base_url), record=record_for(row, stats.get(row.owner_id)))
async def require_approved_owner(user: User, db: AsyncSession) -> OwnerApplication:
    app = await db.get(OwnerApplication, user.id)
    if not app or app.status != "approved":
        raise field_error("Get verified as an owner before listing a home.", None, status.HTTP_403_FORBIDDEN)
    return app


def address_matches(app: OwnerApplication, body: "ListingIn") -> bool:  # the verified property, or a new one to check
    proof = " ".join((app.property_address or "").lower().split())
    return body.pincode in proof
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
    app = await require_approved_owner(user, db)
    enforce(f"listing:user:{user.id}", 10, 86400, "You can add up to 10 homes a day.")
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
    cleaned = []
    for photo in photos:  # check every photo before saving any
        raw = await read_limited(photo, MAX_PHOTO_BYTES, "photos", photo.filename or "A photo")
        cleaned.append(clean_image(raw, "photos", max_side=1600))  # re-encoded: no EXIF/GPS, no disguised files
    for i, content in enumerate(cleaned):
        saved.append(save_public(f"listings/{listing_id}/{i + 1}.jpg", content, "image/jpeg"))
    verified_address = address_matches(app, body)
    row = Listing(id=listing_id, owner_id=user.id, photos=saved, status="live" if verified_address else "review",
                  admin_note=None if verified_address else "This address isn't on your verified property document, so "
                  "TrustRent is checking it before the home goes live.", listed_at=utcnow(), **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return listing_out(row, user, exact=True, base_url=str(request.base_url))
@router.patch("/owner/listings/{listing_id}")  # listing status
async def set_status(listing_id: str, body: StatusIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(Listing, listing_id)
    if not row or row.owner_id != user.id or row.status == "removed":
        raise HTTPException(status_code=404, detail="Listing not found")
    if row.status == "review":
        raise field_error("This home is waiting for a TrustRent check of its address. It goes live once approved.",
                          "status", status.HTTP_403_FORBIDDEN)
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
