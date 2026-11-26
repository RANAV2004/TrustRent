"""Help & support: users raise a query (with screenshots) and get a ticket number; admins reply and close it."""
import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error, read_limited
from app.api.v1.admin import require_admin
from app.api.v1.auth import get_current_user
from app.api.v1.condition import clean_image
from app.core.database import get_db
from app.core.ratelimit import TICKETS_PER_USER
from app.models.marketplace import utcnow
from app.models.support import SupportTicket, TicketAttachment, TicketMessage
from app.models.user import User
from app.services.accounts import account_type, admin_unlocked, display_name, iso
from app.services.files import private_storage, read_private
from app.services.hash_service import HashService
from app.services.notify import notify, notify_admins, snippet

router = APIRouter(tags=["Help and support"])

CATEGORIES = [
    "Account and sign-in", "Payments and Premium", "Deposits and refunds", "Listings and messages",
    "Verification", "Lawyers and agreements", "Something isn't working", "Other",
]
STATUSES = ("open", "in_progress", "closed")
STATUS_LABEL = {"open": "Open", "in_progress": "In progress", "closed": "Closed"}
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024
TICKET_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I/L: easy to read out on the phone
NOT_FOUND = "No ticket of yours has that number. Check it and try again."


def normalise_ticket_no(raw: str) -> str:
    s = "".join(c for c in raw.upper() if c.isalnum())
    if s.startswith("TKT"):
        s = s[3:]
    return f"TKT-{s[:6]}-{s[6:]}" if len(s) == 10 else raw.strip().upper()


async def _new_ticket_no(db: AsyncSession) -> str:
    day = datetime.now(timezone.utc).strftime("%y%m%d")
    while True:
        candidate = f"TKT-{day}-{''.join(secrets.choice(TICKET_ALPHABET) for _ in range(4))}"
        if not await db.get(SupportTicket, candidate):
            return candidate


async def _images(files: list[UploadFile] | None) -> list[tuple[str, bytes]]:
    files = [f for f in (files or []) if f and f.filename]
    if len(files) > MAX_IMAGES:
        raise field_error(f"Add up to {MAX_IMAGES} screenshots.", "images")
    out = []
    for f in files:
        raw = await read_limited(f, MAX_IMAGE_BYTES, "images", f"{f.filename} is larger than 5 MB.")
        try:
            content = clean_image(raw)  # must really be a picture; also removes location data
        except HTTPException:
            raise field_error(f"{f.filename} isn't an image. Add screenshots as JPG, PNG or WebP.", "images") from None
        name = "".join(c for c in f.filename if c.isalnum() or c in "._- ")[:80] or "screenshot"
        out.append((name.rsplit(".", 1)[0] + ".jpg", content))
    return out


def _store(db: AsyncSession, ticket_id: str, user: User, images: list[tuple[str, bytes]], message_id: str | None) -> None:
    store = private_storage()
    for name, content in images:
        aid = str(uuid.uuid4())
        path, iv = store.store(f"ticket_{ticket_id}_{aid[:8]}", content)
        db.add(TicketAttachment(id=aid, ticket_id=ticket_id, message_id=message_id, uploaded_by=user.id, file_name=name,
                                file_path=path, file_iv=iv, file_hash=HashService.hash_bytes(content), size=len(content),
                                created_at=utcnow()))


async def _ticket_for(db: AsyncSession, ticket_no: str, user: User) -> SupportTicket:
    t = await db.get(SupportTicket, normalise_ticket_no(ticket_no))
    if not t or (t.user_id != user.id and not admin_unlocked(user)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return t


def summary(t: SupportTicket, owner: User | None = None) -> dict:
    out = {"ticketNo": t.id, "category": t.category, "subject": t.subject, "status": t.status,
           "statusLabel": STATUS_LABEL.get(t.status, t.status), "createdAt": iso(t.created_at), "updatedAt": iso(t.updated_at),
           "closedAt": iso(t.closed_at)}
    if owner is not None:
        out["user"] = {"id": owner.id, "name": display_name(owner), "email": owner.email,
                       "username": owner.username or "", "accountType": account_type(owner)}
    return out


async def ticket_out(db: AsyncSession, t: SupportTicket, viewer: User) -> dict:
    owner = await db.get(User, t.user_id)
    msgs = list(await db.scalars(select(TicketMessage).where(TicketMessage.ticket_id == t.id).order_by(TicketMessage.created_at)))
    files = list(await db.scalars(select(TicketAttachment).where(TicketAttachment.ticket_id == t.id).order_by(TicketAttachment.created_at)))
    names = {u.id: display_name(u) for u in await db.scalars(select(User).where(User.id.in_({m.author_id for m in msgs} | {t.user_id})))}
    att = lambda a: {"id": a.id, "fileName": a.file_name, "size": a.size}  # noqa: E731
    return summary(t, owner if admin_unlocked(viewer) else None) | {
        "description": t.description, "pageUrl": t.page_url, "resolution": t.resolution,
        "canReply": t.status != "closed" or admin_unlocked(viewer), "isSupport": admin_unlocked(viewer),
        "images": [att(a) for a in files if a.message_id is None],
        "timeline": [{"id": m.id, "kind": m.kind, "fromSupport": bool(m.from_support), "statusTo": m.status_to,
                      "statusLabel": STATUS_LABEL.get(m.status_to or "", None), "text": m.text, "createdAt": iso(m.created_at),
                      "author": "TrustRent support" if m.from_support else names.get(m.author_id, ""),
                      "images": [att(a) for a in files if a.message_id == m.id]} for m in msgs],
    }


@router.get("/support/categories")  # query types
async def categories():
    return {"categories": CATEGORIES, "maxImages": MAX_IMAGES}


@router.post("/support/tickets", status_code=201)  # raise a query
async def raise_ticket(
    category: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    pageUrl: str = Form(""),
    images: list[UploadFile] | None = File(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if category not in CATEGORIES:
        raise field_error("Choose what your query is about.", "category")
    subj = " ".join(subject.split())
    if not 5 <= len(subj) <= 120:
        raise field_error("Give your query a short title (5 to 120 characters).", "subject")
    desc = description.strip()
    if not 20 <= len(desc) <= 4000:
        raise field_error("Describe the problem in at least 20 characters (up to 4000).", "description")
    if not TICKETS_PER_USER.allow(user.id):
        raise field_error("You've raised a lot of queries today. Add to an open ticket instead, or try tomorrow.", None,
                          status.HTTP_429_TOO_MANY_REQUESTS)
    pics = await _images(images)
    now = utcnow()
    t = SupportTicket(id=await _new_ticket_no(db), user_id=user.id, category=category, subject=subj, description=desc,
                      page_url=pageUrl.strip()[:300] or None, status="open", created_at=now, updated_at=now)
    db.add(t)
    await db.flush()
    _store(db, t.id, user, pics, None)
    await db.commit()
    notify(user, f"We got your query {t.id}", [
        f'Your ticket number is {t.id} for "{t.subject}".',
        "We usually reply within one working day. Keep the number to check progress under Help & support."],
        f"/help/{t.id}")
    notify_admins("support-ticket", "New support query", [f"{t.id}: {t.category}, \"{t.subject}\"."], "/admin/queries")
    return await ticket_out(db, t, user)


@router.get("/support/tickets")  # my queries
async def my_tickets(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(SupportTicket.created_at.desc()))
    return [summary(t) for t in rows]


@router.get("/support/tickets/{ticket_no}")  # find a ticket
async def get_ticket(ticket_no: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await ticket_out(db, await _ticket_for(db, ticket_no, user), user)


@router.post("/support/tickets/{ticket_no}/messages", status_code=201)  # reply on a ticket
async def reply(
    ticket_no: str,
    text: str = Form(...),
    images: list[UploadFile] | None = File(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t = await _ticket_for(db, ticket_no, user)
    support = admin_unlocked(user)
    if t.status == "closed" and not support:
        raise field_error("This ticket is closed. Raise a new query if you still need help.", None, status.HTTP_409_CONFLICT)
    body = text.strip()
    if not 1 <= len(body) <= 4000:
        raise field_error("Write a message (up to 4000 characters).", "text")
    pics = await _images(images)
    now = utcnow()
    m = TicketMessage(id=str(uuid.uuid4()), ticket_id=t.id, author_id=user.id, from_support=support, kind="message",
                      text=body, created_at=now)
    db.add(m)
    await db.flush()
    _store(db, t.id, user, pics, m.id)
    t.updated_at = now
    if support and t.status == "open":  # a reply from support means someone is on it
        t.status = "in_progress"
    await db.commit()
    if support:
        notify(await db.get(User, t.user_id), f"TrustRent support replied to {t.id}", [
            f'About "{t.subject}":', f'"{snippet(body, 400)}"', "Reply on the ticket page if you need to add anything."],
            f"/help/{t.id}")
    else:
        notify_admins(f"ticket-reply:{t.id}", f"Reply on {t.id}", [f'The user added a message to "{t.subject}".'], f"/help/{t.id}")
    return await ticket_out(db, t, user)


@router.get("/support/tickets/{ticket_no}/images/{image_id}")  # screenshot
async def ticket_image(ticket_no: str, image_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t = await _ticket_for(db, ticket_no, user)
    a = await db.get(TicketAttachment, image_id)
    if not a or a.ticket_id != t.id:
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        content = read_private(a.file_path, a.file_iv)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="This image is no longer stored") from None
    return Response(content=content, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


# ---------- admin ----------

class StatusIn(BaseModel):
    status: str
    note: str = Field(default="", max_length=2000)


@router.get("/admin/support")  # admin queries
async def admin_tickets(status_filter: str = Query("", alias="status"), q: str = Query("", max_length=100), admin: User = Depends(require_admin),
                        db: AsyncSession = Depends(get_db)):
    stmt = select(SupportTicket, User).join(User, User.id == SupportTicket.user_id)
    if status_filter in STATUSES:
        stmt = stmt.where(SupportTicket.status == status_filter)
    term = q.strip()
    if term:
        like = f"%{term.lower()}%"
        stmt = stmt.where(or_(SupportTicket.id == normalise_ticket_no(term), func.lower(SupportTicket.subject).like(like),
                              func.lower(User.email).like(like), func.lower(User.username).like(like)))
    rows = (await db.execute(stmt.order_by(SupportTicket.updated_at.desc()).limit(500))).all()
    counts = dict((await db.execute(select(SupportTicket.status, func.count()).group_by(SupportTicket.status))).all())
    return {"tickets": [summary(t, u) for t, u in rows], "counts": {s: int(counts.get(s, 0)) for s in STATUSES}}


@router.post("/admin/support/{ticket_no}/status")  # change status / close
async def set_status(ticket_no: str, body: StatusIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    t = await _ticket_for(db, ticket_no, admin)
    if body.status not in STATUSES:
        raise field_error("Unknown status.", "status")
    if body.status == t.status:
        raise field_error(f"The ticket is already {STATUS_LABEL[t.status].lower()}.", "status", status.HTTP_409_CONFLICT)
    note = body.note.strip()
    if body.status == "closed" and len(note) < 5:
        raise field_error("Say how it was resolved (the user sees this).", "note")
    now = utcnow()
    db.add(TicketMessage(id=str(uuid.uuid4()), ticket_id=t.id, author_id=admin.id, from_support=True, kind="status",
                         status_to=body.status, text=note or None, created_at=now))
    t.status, t.updated_at = body.status, now
    if body.status == "closed":
        t.closed_at, t.closed_by, t.resolution = now, admin.id, note
    else:
        t.closed_at = t.closed_by = t.resolution = None
    await db.commit()
    owner = await db.get(User, t.user_id)
    if body.status == "closed":
        notify(owner, f"Your query {t.id} is resolved", [f'About "{t.subject}":', f"Resolution: {note}",
               "If the problem comes back, raise a new query from Help & support."], f"/help/{t.id}")
    else:
        notify(owner, f"Update on your query {t.id}", [f'"{t.subject}" is now {STATUS_LABEL[body.status].lower()}.',
               *([f'"{snippet(note, 400)}"'] if note else [])], f"/help/{t.id}")
    return await ticket_out(db, t, admin)
