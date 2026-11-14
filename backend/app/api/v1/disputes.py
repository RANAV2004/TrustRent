import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.admin import require_reviewer
from app.api.v1.auth import get_current_user
from app.api.v1.condition import ROOMS
from app.api.v1.deposits import deposit_out
from app.core.database import get_db
from app.core.errors import field_error
from app.core.ratelimit import enforce
from app.models.deposits import ConditionPhoto, Deposit, LedgerEntry, Payment
from app.models.extras import Agreement, AgreementSignature, DisputeNote
from app.models.marketplace import Conversation, Message, utcnow
from app.models.user import User
from app.services.accounts import display_name, iso, is_reviewer
from app.services.notify import notify

router = APIRouter(tags=["Disputes"])
NOTE_OPEN = ("held", "settlement_proposed", "disputed")


class NoteIn(BaseModel):
    text: str = Field(min_length=5, max_length=2000)


async def _deposit(db: AsyncSession, deposit_id: str, user: User) -> Deposit:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d or (user.id not in (d.tenant_id, d.owner_id) and not is_reviewer(user)):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d


def _role(d: Deposit, user: User) -> str:
    return "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else "admin"


async def _notes(db: AsyncSession, d: Deposit) -> list[dict]:
    rows = list(await db.scalars(select(DisputeNote).where(DisputeNote.deposit_id == d.id).order_by(DisputeNote.created_at)))
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({r.author_id for r in rows})))} if rows else {}
    return [{"id": n.id, "role": n.role, "author": display_name(people[n.author_id]) if n.author_id in people else "",
             "text": n.text, "at": iso(n.created_at)} for n in rows]


@router.get("/deposits/{deposit_id}/notes")  # dispute statements
async def list_notes(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    return {"notes": await _notes(db, d), "canAdd": d.status in NOTE_OPEN}


@router.post("/deposits/{deposit_id}/notes", status_code=201)  # add statement
async def add_note(deposit_id: str, body: NoteIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    if d.status not in NOTE_OPEN:
        raise field_error("This deposit is settled, so statements are closed.", "text", status.HTTP_409_CONFLICT)
    enforce(f"note:user:{user.id}", 20, 3600, "Too many statements in an hour.")
    role = _role(d, user)
    db.add(DisputeNote(id=str(uuid.uuid4()), deposit_id=d.id, author_id=user.id, role=role, text=body.text.strip(),
                       created_at=utcnow()))
    await db.commit()
    for uid, who in ((d.tenant_id, "tenant"), (d.owner_id, "owner")):
        if uid != user.id:
            notify(await db.get(User, uid), f"New statement on deposit {d.id}",
                   [f"The {role if role != 'admin' else 'TrustRent reviewer'} added a statement:", body.text.strip()[:400]],
                   "/deposits")
    return {"notes": await _notes(db, d)}


async def _photos(db: AsyncSession, d: Deposit) -> dict:
    grid: dict[str, dict] = {}
    for p in await db.scalars(select(ConditionPhoto).where(ConditionPhoto.deposit_id == d.id).order_by(ConditionPhoto.created_at)):
        cell = grid.setdefault(p.room, {"move_in": {"tenant": [], "owner": []}, "move_out": {"tenant": [], "owner": []}})
        cell[p.stage][p.side].append({"id": p.id, "note": p.note, "at": iso(p.created_at), "fileHash": p.file_hash,
                                      "url": f"/deposits/{d.id}/photos/{p.id}/file"})
    order = {r: i for i, r in enumerate(ROOMS)}
    return dict(sorted(grid.items(), key=lambda kv: order.get(kv[0], 99)))


async def _timeline(db: AsyncSession, d: Deposit, notes: list[dict]) -> list[dict]:
    ev = [{"at": iso(d.paid_at), "kind": "paid", "text": f"Deposit of ₹{d.amount:,} paid"}]
    ag = await db.scalar(select(Agreement).where(Agreement.deposit_id == d.id))
    if ag:
        ev.append({"at": iso(ag.created_at), "kind": "agreement", "text": "Rent agreement drafted by the owner"})
        for sig in await db.scalars(select(AgreementSignature).where(AgreementSignature.agreement_id == ag.id)):
            ev.append({"at": iso(sig.signed_at), "kind": "signed", "text": f"Agreement signed by the {sig.role} ({sig.typed_name})"})
    if d.moved_out_at:
        ev.append({"at": iso(d.moved_out_at), "kind": "moved_out", "text": "Move-out recorded"})
    if d.proposed_at:
        ask = d.proposed_deducted if d.proposed_deducted is not None else d.deducted
        ev.append({"at": iso(d.proposed_at), "kind": "proposed", "text": f"Owner proposed keeping ₹{(ask or 0):,}"})
    if d.disputed_at:
        ev.append({"at": iso(d.disputed_at), "kind": "disputed", "text": "Tenant disputed the proposal"})
    for n in notes:
        ev.append({"at": n["at"], "kind": "note", "text": f"Statement by the {n['role']}: {n['text'][:120]}"})
    if d.settled_at:
        by = "automatically (deadline passed)" if d.settled_by == "system" else "by TrustRent" if d.settled_by not in (d.tenant_id, d.owner_id) else "by agreement"
        ev.append({"at": iso(d.settled_at), "kind": "settled", "text": f"Settled {by}: ₹{d.refunded or 0:,} refunded, ₹{d.deducted or 0:,} kept"})
    return sorted(ev, key=lambda e: e["at"] or "")


@router.get("/admin/deposits/{deposit_id}/workspace")  # dispute workspace
async def workspace(deposit_id: str, user: User = Depends(require_reviewer), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    tenant, owner = await db.get(User, d.tenant_id), await db.get(User, d.owner_id)
    notes = await _notes(db, d)
    conv = await db.scalar(select(Conversation).where(Conversation.listing_id == d.listing_id, Conversation.seeker_id == d.tenant_id))
    chat = []
    if conv:
        for m in await db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).limit(200)):
            chat.append({"from": "tenant" if m.sender_id == d.tenant_id else "owner", "text": m.text or "Visit request",
                         "at": iso(m.created_at)})
        chat.reverse()
    entries = list(await db.scalars(select(LedgerEntry).where(LedgerEntry.deposit_id == d.id).order_by(LedgerEntry.seq)))
    pay = await db.get(Payment, d.payment_id)

    def person(u):
        return {"id": u.id, "name": display_name(u), "email": u.email, "phone": u.phone or "", "verified": bool(u.is_verified)} if u else None
    return {
        "deposit": await deposit_out(db, d, user, with_check=True),
        "tenant": person(tenant), "owner": person(owner),
        "ownerAsked": d.proposed_deducted if d.proposed_deducted is not None else d.deducted,
        "payment": {"provider": pay.provider, "reference": pay.payment_id} if pay else None,
        "notes": notes, "photos": await _photos(db, d), "chat": chat,
        "timeline": await _timeline(db, d, notes),
        "ledger": [{"seq": e.seq, "kind": e.kind, "hash": e.entry_hash, "at": iso(e.created_at)} for e in entries],
        "canDecide": d.status not in ("settled", "settling"),
    }
