import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import PLANS, field_error
from app.api.v1.admin import require_admin
from app.core.database import get_db
from app.models.deposits import Deposit, Payment
from app.models.marketplace import (
    Conversation, EmailVerification, IdentitySubmission, Listing, Message, OwnerApplication, utcnow,
)
from app.models.user import User, UserRole
from app.services.accounts import account_type, display_name, has_premium, is_admin, iso
from app.services.ledger import GENESIS, ledger_state
from app.services.marketplace import message_out
from app.services import chain
from app.services.register import try_rebuild_register
router = APIRouter(prefix="/admin", tags=["Admin console"])
PLAN_LABEL = {"week": "1 week", "month": "1 month", "quarter": "3 months"}
class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=300)
def require_full_admin(user: User = Depends(require_admin)) -> User:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admins only")
    return user
async def _target(db: AsyncSession, user_id: str, admin: User) -> User:
    u = await db.get(User, user_id)
    if not u or u.deleted_at:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == admin.id or is_admin(u):
        raise field_error("Admin accounts can't be changed here.", None, status.HTTP_403_FORBIDDEN)
    return u
def _premium(u: User) -> dict | None:
    if not u.premium_plan:
        return None
    return {"planId": u.premium_plan, "plan": PLAN_LABEL.get(u.premium_plan, u.premium_plan),
            "until": iso(u.premium_until), "active": has_premium(u)}
def user_row(u: User, listings: int = 0, deposits: int = 0) -> dict:
    return {
        "id": u.id, "name": display_name(u), "username": u.username or "", "email": u.email, "phone": u.phone or "",
        "accountType": account_type(u), "role": u.role.value if u.role else "tenant", "provider": u.provider or "",
        "verified": bool(u.is_verified), "isAdmin": is_admin(u), "isDemo": bool(u.is_demo),
        "premium": _premium(u), "createdAt": iso(u.created_at),
        "banned": {"at": iso(u.banned_at), "reason": u.ban_reason} if u.banned_at and not u.deleted_at else None,
        "deletedAt": iso(u.deleted_at), "listings": listings, "deposits": deposits,
    }
async def _counts(db: AsyncSession, column) -> dict[str, int]:
    return dict((await db.execute(select(column, func.count()).group_by(column))).all())
@router.get("/overview")  # admin overview
async def overview(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    users = list(await db.scalars(select(User)))
    live = [u for u in users if not u.deleted_at]
    listings = await _counts(db, Listing.status)
    deposits = list(await db.scalars(select(Deposit)))
    premium_paid = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0))
                                   .where(Payment.purpose == "premium", Payment.status == "paid"))
    pending_ids = await db.scalar(select(func.count()).select_from(IdentitySubmission).where(IdentitySubmission.status == "pending"))
    pending_owners = await db.scalar(select(func.count()).select_from(OwnerApplication).where(OwnerApplication.status == "submitted"))
    return {
        "users": {
            "total": len(live),
            "seekers": sum(1 for u in live if u.role != UserRole.LANDLORD),
            "owners": sum(1 for u in live if u.role == UserRole.LANDLORD),
            "verified": sum(1 for u in live if u.is_verified),
            "banned": sum(1 for u in live if u.banned_at),
            "deleted": sum(1 for u in users if u.deleted_at),
            "premium": sum(1 for u in live if has_premium(u)),
        },
        "listings": {"live": listings.get("live", 0), "paused": listings.get("paused", 0),
                     "unlisted": listings.get("blocked", 0), "removed": listings.get("removed", 0)},
        "deposits": {
            "count": len(deposits),
            "held": sum(d.amount for d in deposits if d.status != "settled"),
            "open": sum(1 for d in deposits if d.status != "settled"),
            "disputed": sum(1 for d in deposits if d.status == "disputed"),
            "refunded": sum(d.refunded or 0 for d in deposits if d.status == "settled"),
        },
        "conversations": await db.scalar(select(func.count()).select_from(Conversation)),
        "messages": await db.scalar(select(func.count()).select_from(Message)),
        "premiumRevenue": int(premium_paid or 0),
        "pendingVerifications": int(pending_ids or 0) + int(pending_owners or 0),
    }
@router.get("/users")  # admin users
async def users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(User).order_by(User.created_at.desc())))
    listing_counts = await _counts(db, Listing.owner_id)
    tenant = await _counts(db, Deposit.tenant_id)
    owner = await _counts(db, Deposit.owner_id)
    return [user_row(u, listing_counts.get(u.id, 0), tenant.get(u.id, 0) + owner.get(u.id, 0)) for u in rows]
@router.post("/users/{user_id}/ban")  # ban user
async def ban(user_id: str, body: ReasonIn, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    u = await _target(db, user_id, admin)
    u.banned_at, u.ban_reason = utcnow(), body.reason.strip() or "Broke the TrustRent terms of use"
    await db.commit()
    return {"user": user_row(u)}
@router.post("/users/{user_id}/unban")  # unban user
async def unban(user_id: str, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    u = await _target(db, user_id, admin)
    u.banned_at, u.ban_reason = None, None
    await db.commit()
    return {"user": user_row(u)}
def _remove_local_file(path: str | None) -> None:
    if path and not path.startswith("s3://") and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
@router.delete("/users/{user_id}")  # delete user
async def delete_user(user_id: str, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    u = await _target(db, user_id, admin)
    open_deposit = await db.scalar(select(Deposit.id).where(
        or_(Deposit.tenant_id == u.id, Deposit.owner_id == u.id), Deposit.status != "settled").limit(1))
    if open_deposit:
        raise field_error(f"Settle deposit {open_deposit} before deleting this account.", None, status.HTTP_409_CONFLICT)
    for s in await db.scalars(select(IdentitySubmission).where(IdentitySubmission.user_id == u.id)):
        _remove_local_file(s.file_path)
        await db.delete(s)
    app = await db.get(OwnerApplication, u.id)
    if app:
        _remove_local_file(app.id_file_path)
        _remove_local_file(app.property_file_path)
        await db.delete(app)
    code = await db.get(EmailVerification, (u.email or "").lower())
    if code:
        await db.delete(code)
    for listing in await db.scalars(select(Listing).where(Listing.owner_id == u.id)):
        listing.status, listing.admin_note = "removed", "Owner account deleted"
    now = utcnow()
    u.email = f"deleted-{u.id[:8]}@deleted.trustrent.in"
    u.name, u.first_name, u.last_name = "Deleted user", "Deleted", "user"
    u.username = u.phone = u.country = u.password_hash = u.wallet_address = u.attestation_hash = None
    u.premium_plan = u.premium_until = None
    u.is_verified, u.provider = False, "deleted"
    u.deleted_at, u.banned_at, u.ban_reason = now, now, "Account deleted by admin"
    await db.commit()
    await try_rebuild_register(db)
    return {"ok": True}
def listing_row(x: Listing, owner: User | None, chats: int) -> dict:
    return {
        "id": x.id, "title": x.title, "area": f"{x.locality}, {x.city} {x.pincode}", "rent": x.rent, "deposit": x.deposit,
        "bhk": x.bhk, "status": x.status, "adminNote": x.admin_note, "listedAt": iso(x.listed_at),
        "sample": x.listed_days_ago is not None, "conversations": chats,
        "owner": {"id": x.owner_id, "name": display_name(owner) if owner else "", "email": owner.email if owner else "",
                  "banned": bool(owner and owner.banned_at)},
    }
@router.get("/listings")  # admin listings
async def listings(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(Listing).order_by(Listing.listed_at.desc())))
    owners = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({r.owner_id for r in rows})))}
    chats = await _counts(db, Conversation.listing_id)
    return [listing_row(x, owners.get(x.owner_id), chats.get(x.id, 0)) for x in rows]
async def _listing(db: AsyncSession, listing_id: str) -> Listing:
    x = await db.get(Listing, listing_id)
    if not x or x.status == "removed":
        raise HTTPException(status_code=404, detail="Listing not found")
    return x
@router.post("/listings/{listing_id}/unlist")  # unlist home
async def unlist(listing_id: str, body: ReasonIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    x = await _listing(db, listing_id)
    x.status, x.admin_note = "blocked", body.reason.strip() or "it breaks the TrustRent listing rules"
    await db.commit()
    return listing_row(x, await db.get(User, x.owner_id), 0)
@router.post("/listings/{listing_id}/relist")  # relist home
async def relist(listing_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    x = await _listing(db, listing_id)
    x.status, x.admin_note = "live", None
    await db.commit()
    return listing_row(x, await db.get(User, x.owner_id), 0)
@router.get("/conversations")  # admin chats
async def conversations(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    convs = list(await db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())))
    ids = {c.seeker_id for c in convs} | {c.owner_id for c in convs}
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))}
    homes = {x.id: x for x in await db.scalars(select(Listing).where(Listing.id.in_({c.listing_id for c in convs})))}
    counts = await _counts(db, Message.conversation_id)
    out = []
    for c in convs:
        last = await db.scalar(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at.desc()).limit(1))
        home = homes.get(c.listing_id)
        out.append({
            "id": c.id, "listing": {"id": c.listing_id, "title": home.title if home else ""},
            "seeker": {"id": c.seeker_id, "name": display_name(people[c.seeker_id]) if c.seeker_id in people else ""},
            "owner": {"id": c.owner_id, "name": display_name(people[c.owner_id]) if c.owner_id in people else ""},
            "messages": counts.get(c.id, 0), "updatedAt": iso(c.updated_at),
            "last": (last.text or ("Visit request" if last.kind == "visit" else "")) if last else "",
        })
    return out
@router.get("/conversations/{cid}/messages")  # chat messages
async def conversation_messages(cid: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    c = await db.get(Conversation, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = list(await db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.created_at)))
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({c.seeker_id, c.owner_id})))}
    return [message_out(m, display_name(people[m.sender_id]) if m.sender_id in people else "") | {
        "from": "seeker" if m.sender_id == c.seeker_id else "owner"} for m in rows]
@router.get("/premium")  # admin premium
async def premium(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    members = list(await db.scalars(select(User).where(User.premium_plan.is_not(None), User.deleted_at.is_(None))
                                    .order_by(User.premium_until.desc())))
    pays = list(await db.scalars(select(Payment).where(Payment.purpose == "premium", Payment.status == "paid")
                                 .order_by(Payment.paid_at.desc())))
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({p.user_id for p in pays})))}
    spent: dict[str, int] = {}
    for p in pays:
        spent[p.user_id] = spent.get(p.user_id, 0) + p.amount
    return {
        "plans": [{"id": k, "label": PLAN_LABEL.get(k, k), "days": d, "price": p} for k, (d, p) in PLANS.items()],
        "members": [user_row(u) | {"paid": spent.get(u.id, 0)} for u in members],
        "payments": [{
            "id": p.id, "user": {"id": p.user_id, "name": display_name(people[p.user_id]) if p.user_id in people else ""},
            "plan": PLAN_LABEL.get(p.ref, p.ref), "amount": p.amount, "provider": p.provider, "paidAt": iso(p.paid_at),
        } for p in pays],
    }
@router.post("/premium/{user_id}/revoke")  # revoke premium
async def revoke_premium(user_id: str, admin: User = Depends(require_full_admin), db: AsyncSession = Depends(get_db)):
    u = await _target(db, user_id, admin)
    if not has_premium(u):
        raise field_error("This account doesn't have active Premium.", None, status.HTTP_409_CONFLICT)
    u.premium_until = utcnow()
    await db.commit()
    return {"user": user_row(u)}
@router.get("/ledger")  # ledger
async def ledger(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    entries, intact = await ledger_state(db)
    return {
        "intact": intact, "genesis": GENESIS,
        "network": chain.network_name() if chain.enabled() else "trustrent-ledger",
        "blocks": [{"seq": e.seq, "depositId": e.deposit_id, "kind": e.kind, "amounts": e.amounts, "dataHash": e.data_hash,
                    "prevHash": e.prev_hash, "hash": e.entry_hash, "chainTx": e.chain_tx, "at": iso(e.created_at)} for e in entries],
    }
