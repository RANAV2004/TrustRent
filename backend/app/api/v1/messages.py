import asyncio
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.models.marketplace import Conversation, Listing, Message, utcnow
from app.models.user import User
from app.services.accounts import display_name
from app.services.marketplace import can_contact, conversation_out, message_out
router = APIRouter(tags=["Messages"])
DEMO_REPLY_DELAY_SECONDS = 1.5
class OpenIn(BaseModel):
    listingId: str
class MessageIn(BaseModel):
    kind: str = "text"
    text: str | None = Field(default=None, max_length=2000)
    slots: list[str] = Field(default_factory=list, max_length=3)
class VisitResponseIn(BaseModel):
    accept: bool
    slot: str | None = None
def _parse_slot(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise field_error("Visit times must be ISO dates.", "slots") from None
async def _conversation_for(db: AsyncSession, cid: str, user: User) -> Conversation:
    c = await db.get(Conversation, cid)
    if not c or user.id not in (c.seeker_id, c.owner_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return c
def _touch(c: Conversation, sender_id: str, at: datetime) -> None:
    c.updated_at = at
    if sender_id == c.seeker_id:
        c.seeker_last_read = at
    else:
        c.owner_last_read = at
@router.get("/inbox")  # inbox
async def inbox(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    convs = list(await db.scalars(
        select(Conversation).where(or_(Conversation.seeker_id == user.id, Conversation.owner_id == user.id))
        .order_by(Conversation.updated_at.desc())
    ))
    if not convs:
        return {"conversations": [], "messages": []}
    listing_ids = {c.listing_id for c in convs}
    user_ids = {c.seeker_id for c in convs} | {c.owner_id for c in convs}
    listings = {x.id: x for x in await db.scalars(select(Listing).where(Listing.id.in_(listing_ids)))}
    users = {x.id: x for x in await db.scalars(select(User).where(User.id.in_(user_ids)))}
    msgs = await db.scalars(
        select(Message).where(Message.conversation_id.in_([c.id for c in convs])).order_by(Message.created_at)
    )
    return {
        "conversations": [conversation_out(c, listings[c.listing_id], users[c.seeker_id], users[c.owner_id]) for c in convs],
        "messages": [message_out(m, display_name(users[m.sender_id])) for m in msgs],
    }
@router.post("/conversations")  # open chat
async def open_conversation(body: OpenIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, body.listingId)
    if not listing or listing.status != "live":
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id == user.id:
        raise field_error("This is your own listing.", None)
    if not can_contact(listing, user):
        raise field_error(
            f"This home is new: Premium members can contact the owner for the first {settings.EARLY_ACCESS_HOURS} hours.",
            None, status.HTTP_403_FORBIDDEN,
        )
    c = await db.scalar(select(Conversation).where(Conversation.listing_id == listing.id, Conversation.seeker_id == user.id))
    if not c:
        now = utcnow()
        c = Conversation(id=str(uuid.uuid4()), listing_id=listing.id, seeker_id=user.id, owner_id=listing.owner_id,
                         created_at=now, updated_at=now)
        db.add(c)
        await db.commit()
        await db.refresh(c)
    owner = await db.get(User, c.owner_id)
    return conversation_out(c, listing, user, owner)
@router.post("/conversations/{cid}/messages", status_code=201)  # send message
async def send_message(cid: str, body: MessageIn, background: BackgroundTasks,
                       user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _conversation_for(db, cid, user)
    text = (body.text or "").strip() or None
    now = utcnow()
    if body.kind == "text":
        if not text:
            raise field_error("Write a message.", "text")
        m = Message(id=str(uuid.uuid4()), conversation_id=c.id, sender_id=user.id, kind="text", text=text, created_at=now)
    elif body.kind == "visit":
        if user.id != c.seeker_id:
            raise field_error("Only the person looking for a home can request a visit.", None, status.HTTP_403_FORBIDDEN)
        if not body.slots:
            raise field_error("Pick at least one time.", "slots")
        if any(_parse_slot(s).timestamp() < datetime.now(timezone.utc).timestamp() for s in body.slots):
            raise field_error("Times must be in the future.", "slots")
        m = Message(id=str(uuid.uuid4()), conversation_id=c.id, sender_id=user.id, kind="visit", text=text,
                    visit_slots=body.slots, visit_status="pending", created_at=now)
    else:
        raise field_error("Unknown message kind.", "kind")
    db.add(m)
    _touch(c, user.id, now)
    await db.commit()
    owner = await db.get(User, c.owner_id)
    if settings.DEMO_MODE and owner and owner.is_demo and user.id == c.seeker_id:
        background.add_task(demo_owner_reply, c.id, m.id)
    return message_out(m, display_name(user))
@router.post("/messages/{mid}/visit-response")  # visit reply
async def respond_to_visit(mid: str, body: VisitResponseIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    m = await db.get(Message, mid)
    if not m or m.kind != "visit":
        raise HTTPException(status_code=404, detail="Visit request not found")
    c = await _conversation_for(db, m.conversation_id, user)
    return message_out(*await _respond(db, c, m, user, body.accept, body.slot))
async def _respond(db: AsyncSession, c: Conversation, m: Message, owner: User, accept: bool, slot: str | None):
    if owner.id != c.owner_id:
        raise field_error("Only the owner can answer a visit request.", None, status.HTTP_403_FORBIDDEN)
    if m.visit_status != "pending":
        raise field_error("This request was already answered.", None, status.HTTP_409_CONFLICT)
    if accept and slot not in (m.visit_slots or []):
        raise field_error("Pick one of the proposed times.", "slot")
    m.visit_status = "accepted" if accept else "declined"
    m.accepted_slot = slot if accept else None
    now = utcnow()
    when = ""
    if accept and slot:
        dt = _parse_slot(slot)
        dt = (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(ZoneInfo("Asia/Kolkata"))
        when = f"{dt:%a, %d %b}, {dt.hour % 12 or 12}:{dt:%M} {'AM' if dt.hour < 12 else 'PM'} IST"
    reply = Message(
        id=str(uuid.uuid4()), conversation_id=c.id, sender_id=owner.id, kind="text", created_at=now,
        text=f"Visit confirmed for {when}. See you then." if accept else "Sorry, those times don't work for me. Could you suggest others?",
    )
    db.add(reply)
    _touch(c, owner.id, now)
    await db.commit()
    return m, display_name(await db.get(User, m.sender_id))
@router.post("/conversations/{cid}/read")  # mark read
async def mark_read(cid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await _conversation_for(db, cid, user)
    if user.id == c.seeker_id:
        c.seeker_last_read = utcnow()
    else:
        c.owner_last_read = utcnow()
    await db.commit()
    return {"ok": True}
async def demo_owner_reply(cid: str, mid: str) -> None:
    await asyncio.sleep(DEMO_REPLY_DELAY_SECONDS)
    async with AsyncSessionLocal() as db:
        c = await db.get(Conversation, cid)
        m = await db.get(Message, mid)
        owner = await db.get(User, c.owner_id) if c else None
        if not (c and m and owner):
            return
        if m.kind == "visit" and m.visit_status == "pending":
            await _respond(db, c, m, owner, True, (m.visit_slots or [None])[0])
            return
        already = await db.scalar(select(Message.id).where(Message.conversation_id == c.id, Message.sender_id == owner.id).limit(1))
        if already:
            return
        listing = await db.get(Listing, c.listing_id)
        now = utcnow()
        db.add(Message(
            id=str(uuid.uuid4()), conversation_id=c.id, sender_id=owner.id, kind="text", created_at=now,
            text=f"Hi! Thanks for your interest in {listing.title if listing else 'my home'}. It's still available. "
                 "Send me a visit request with a few times that suit you.",
        ))
        _touch(c, owner.id, now)
        await db.commit()
