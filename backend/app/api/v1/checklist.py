import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.auth import get_current_user
from app.api.v1.condition import OPEN_FOR, STAGES
from app.core.database import get_db
from app.core.errors import field_error
from app.models.deposits import ConditionPhoto, Deposit
from app.models.marketplace import Listing, utcnow
from app.models.trust import ChecklistMark
from app.models.user import User
from app.services.accounts import iso, is_reviewer
from app.services.ledger import record_event
from app.services.notify import notify

router = APIRouter(tags=["Move-in checklist"])
TIPS = {
    "Entrance and doors": "Main door, locks, door frame and the number plate.",
    "Hall / living room": "Walls, floor, switches, fans and lights, windows.",
    "Kitchen": "Counter, sink and tap, cabinets, chimney or exhaust, gas point.",
    "Bathroom 1": "Tiles, tap and shower, geyser, toilet, mirror.",
    "Bathroom 2": "Tiles, tap and shower, geyser, toilet, mirror.",
    "Balcony": "Railing, floor, drain, any fixtures.",
}


def expected_rooms(listing: Listing | None) -> list[str]:
    bhk = listing.bhk if listing else 1
    rooms = ["Entrance and doors", "Hall / living room", "Kitchen"]
    rooms += [f"Bedroom {i}" for i in range(1, min(max(bhk, 0), 3) + 1)]
    rooms += ["Bathroom 1"] + (["Bathroom 2"] if bhk >= 2 else [])
    if listing and "balcony" in (listing.amenities or []):
        rooms.append("Balcony")
    return rooms


async def checklist_state(db: AsyncSession, d: Deposit) -> dict:
    rooms = expected_rooms(await db.get(Listing, d.listing_id))
    photos = list(await db.scalars(select(ConditionPhoto).where(ConditionPhoto.deposit_id == d.id)))
    marks = {(m.side, m.stage): m for m in await db.scalars(select(ChecklistMark).where(ChecklistMark.deposit_id == d.id))}
    out = {}
    for stage in STAGES:
        out[stage] = {}
        for side in ("tenant", "owner"):
            covered = {p.room for p in photos if p.stage == stage and p.side == side}
            mark = marks.get((side, stage))
            out[stage][side] = {"done": [r for r in rooms if r in covered], "missing": [r for r in rooms if r not in covered],
                                "completedAt": iso(mark.completed_at) if mark else None}
    return {"rooms": [{"name": r, "tip": TIPS.get(r, "Walls, floor, windows, wardrobe, fan and lights.")} for r in rooms], "stages": out}


async def _deposit(db: AsyncSession, deposit_id: str, user: User) -> Deposit:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d or (user.id not in (d.tenant_id, d.owner_id) and not is_reviewer(user)):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d


@router.get("/deposits/{deposit_id}/checklist")  # what's photographed so far
async def get_checklist(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    state = await checklist_state(db, d)
    side = "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else None
    state["side"] = side
    state["open"] = {s: bool(side) and d.status in OPEN_FOR[s] for s in STAGES}
    if side:  # each side sees the other's progress, not their rooms
        other = "owner" if side == "tenant" else "tenant"
        for s in STAGES:
            st = state["stages"][s][other]
            state["stages"][s][other] = {"completedAt": st["completedAt"], "rooms": len(st["done"])}
    return state


@router.post("/deposits/{deposit_id}/checklist/{stage}/complete")  # mark my side done
async def complete(deposit_id: str, stage: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    side = "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else None
    if not side:
        raise HTTPException(status_code=403, detail="Only the tenant or the owner completes a checklist")
    if stage not in STAGES:
        raise HTTPException(status_code=404, detail="Unknown stage")
    if d.status not in OPEN_FOR[stage]:
        raise field_error("This checklist is closed.", None, status.HTTP_409_CONFLICT)
    if await db.scalar(select(ChecklistMark.id).where(ChecklistMark.deposit_id == d.id, ChecklistMark.side == side,
                                                    ChecklistMark.stage == stage)):
        raise field_error("You already completed this checklist.", None, status.HTTP_409_CONFLICT)
    mine = (await checklist_state(db, d))["stages"][stage][side]
    if mine["missing"]:
        raise field_error("Add at least one photo of: " + ", ".join(mine["missing"]) + ".", "rooms")
    now = utcnow()
    mark = ChecklistMark(id=str(uuid.uuid4()), deposit_id=d.id, side=side, stage=stage, rooms=mine["done"], completed_at=now)
    db.add(mark)
    await db.flush()
    mark.record_tx = (await record_event(db, d.id, "checklist", {"depositId": d.id, "side": side, "stage": stage,
                                                                 "rooms": mine["done"], "at": iso(now)})).entry_hash
    await db.commit()
    other = await db.get(User, d.owner_id if side == "tenant" else d.tenant_id)
    label = "move-in" if stage == "move_in" else "move-out"
    notify(other, f"The {side} finished the {label} photos ({d.id})",
           [f"They photographed every room. Add your own {label} photos too, so both sides have a record."], "/deposits")
    return await get_checklist(deposit_id, user, db)
