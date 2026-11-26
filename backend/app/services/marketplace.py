from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.marketplace import Conversation, Listing, Message, utcnow
from app.models.user import User
from app.services.accounts import display_name, has_premium, iso
def early_access_hours_left(listing: Listing) -> int:
    if not listing.listed_at:
        return 0
    left = settings.EARLY_ACCESS_HOURS - (utcnow() - listing.listed_at).total_seconds() / 3600
    return max(0, int(-(-left // 1)))
def can_contact(listing: Listing, user: User) -> bool:
    return listing.owner_id == user.id or has_premium(user) or early_access_hours_left(listing) == 0
async def visit_confirmed(db: AsyncSession, listing_id: str, seeker_id: str) -> bool:
    stmt = (
        select(Message.id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.listing_id == listing_id, Conversation.seeker_id == seeker_id,
               Message.kind == "visit", Message.visit_status == "accepted")
        .limit(1)
    )
    return (await db.scalar(stmt)) is not None
def media_url(base: str, path: str) -> str:
    return path if path.startswith(("http://", "https://", "data:")) else f"{base.rstrip('/')}/media/{path}"
def listing_out(listing: Listing, owner: User | None, *, exact: bool, base_url: str) -> dict:
    reveal = exact or bool(listing.show_exact_location)
    owner_name = display_name(owner) if owner else "Owner"
    return {
        "id": listing.id,
        "title": listing.title,
        "city": listing.city,
        "locality": listing.locality,
        "pincode": listing.pincode,
        "lat": listing.lat if reveal else round(listing.lat, 2),
        "lng": listing.lng if reveal else round(listing.lng, 2),
        "address": listing.address if reveal else None,
        "show_exact_location": reveal,
        "rent": listing.rent,
        "deposit": listing.deposit,
        "bhk": listing.bhk,
        "furnishing": listing.furnishing,
        "area_sqft": listing.area_sqft or 0,
        "amenities": listing.amenities or [],
        "preferred_tenants": listing.preferred_tenants or ["any"],
        "available_from": listing.available_from,
        "min_months": listing.min_months,
        "max_months": listing.max_months,
        "description": listing.description,
        "about_owner": listing.about_owner,
        "photos": [media_url(base_url, p) for p in (listing.photos or [])],
        "status": listing.status,
        "admin_note": listing.admin_note,
        "listed_at": iso(listing.listed_at),
        "owner_id": listing.owner_id,
        "owner_name": owner_name,
        "landlord": {
            "name": owner_name,
            "verified": bool(owner and owner.is_verified),
            "tenancies_completed": listing.tenancies_completed or 0,
            "full_refunds": listing.full_refunds or 0,
            "disputes_lost": listing.disputes_lost or 0,
        },
    }
def conversation_out(c: Conversation, listing: Listing, seeker: User, owner: User) -> dict:
    last_read = {}
    if c.seeker_last_read:
        last_read[seeker.id] = iso(c.seeker_last_read)
    if c.owner_last_read:
        last_read[owner.id] = iso(c.owner_last_read)
    return {
        "id": c.id,
        "listingId": listing.id,
        "listingTitle": listing.title,
        "listingArea": f"{listing.locality}, {listing.city}",
        "seekerId": seeker.id,
        "seekerName": display_name(seeker),
        "ownerId": owner.id,
        "ownerName": display_name(owner),
        "createdAt": iso(c.created_at),
        "updatedAt": iso(c.updated_at),
        "lastRead": last_read,
    }
def message_out(m: Message, sender_name: str) -> dict:
    out = {
        "id": m.id,
        "conversationId": m.conversation_id,
        "senderId": m.sender_id,
        "senderName": sender_name,
        "kind": m.kind,
        "createdAt": iso(m.created_at),
    }
    if m.text:
        out["text"] = m.text
    if m.kind == "visit":
        out["visit"] = {"slots": m.visit_slots or [], "status": m.visit_status or "pending"}
        if m.accepted_slot:
            out["visit"]["acceptedSlot"] = m.accepted_slot
    return out
def redate_sample(listing: Listing) -> None:
    if listing.listed_days_ago is None:
        return
    hours = listing.listed_days_ago * 24 + (6 if listing.listed_days_ago == 0 else 0)
    listing.listed_at = utcnow() - timedelta(hours=hours)
