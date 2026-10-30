import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import field_error
from app.api.v1.admin import require_admin
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.deposits import Deposit, LedgerEntry, Payment
from app.models.marketplace import Listing, utcnow
from app.models.user import User
from app.services import payments
from app.services.accounts import display_name, iso, is_reviewer
from app.services.ledger import ledger_state, record_deposit, record_settlement, verify
router = APIRouter(tags=["Deposits"])
class ProposeIn(BaseModel):
    deducted: int = Field(ge=0)
    reason: str = Field(default="", max_length=1000)
class RespondIn(BaseModel):
    accept: bool
class RecordIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=255)
    listingId: str = Field(min_length=1, max_length=16)
    amount: int = Field(gt=0, le=5_000_000)
    transactionId: str = Field(min_length=4, max_length=64)
def _explorer(tx: str | None, network: str | None) -> str | None:
    if tx and network and network != "trustrent-ledger" and settings.CHAIN_EXPLORER_TX_URL:
        return settings.CHAIN_EXPLORER_TX_URL + tx
    return None
async def deposit_out(db: AsyncSession, d: Deposit, viewer: User, with_check: bool = False, state=None) -> dict:
    listing = await db.get(Listing, d.listing_id)
    party = viewer.id in (d.tenant_id, d.owner_id) or is_reviewer(viewer)
    out = {
        "id": d.id, "amount": d.amount, "currency": "INR", "status": d.status, "paidAt": iso(d.paid_at),
        "listing": {"id": d.listing_id, "title": listing.title if listing else "", "area": f"{listing.locality}, {listing.city}" if listing else ""},
        "deducted": d.deducted, "refunded": d.refunded, "reason": d.deduction_reason,
        "proposedAt": iso(d.proposed_at), "settledAt": iso(d.settled_at),
        "receipt": {"network": d.network, "recordHash": d.record_hash, "recordTx": d.record_tx,
                    "recordUrl": _explorer(d.record_tx, d.network), "settleHash": d.settle_hash,
                    "settleTx": d.settle_tx, "settleUrl": _explorer(d.settle_tx, d.network)},
        "role": "tenant" if viewer.id == d.tenant_id else "owner" if viewer.id == d.owner_id else "admin" if party else None,
    }
    if party:
        tenant, owner = await db.get(User, d.tenant_id), await db.get(User, d.owner_id)
        out["tenant"] = {"id": d.tenant_id, "name": display_name(tenant) if tenant else ""}
        out["owner"] = {"id": d.owner_id, "name": display_name(owner) if owner else ""}
        out["ownerPayout"] = d.owner_payout
        out["refundRef"] = d.refund_ref
        pay = await db.get(Payment, d.payment_id)
        if pay:
            out["payment"] = {"provider": pay.provider, "reference": pay.payment_id}
    if with_check:
        out["verification"] = await verify(db, d, state)
    return out
async def _load(db: AsyncSession, deposit_id: str) -> Deposit:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d
@router.get("/deposits")  # my deposits
async def my_deposits(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Deposit).where(or_(Deposit.tenant_id == user.id, Deposit.owner_id == user.id))
                            .order_by(Deposit.paid_at.desc()))
    state = await ledger_state(db)
    return [await deposit_out(db, d, user, with_check=True, state=state) for d in rows]
@router.get("/deposits/lookup")  # receipt lookup
async def lookup(q: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = q.strip()
    d = await db.get(Deposit, q.upper()) if q.upper().startswith("DEP-") else None
    if not d and q.startswith("0x"):
        d = await db.scalar(select(Deposit).where(or_(Deposit.record_tx == q, Deposit.settle_tx == q,
                                                      Deposit.record_hash == q, Deposit.settle_hash == q)))
        if not d:
            entry = await db.scalar(select(LedgerEntry).where(or_(LedgerEntry.entry_hash == q, LedgerEntry.chain_tx == q)))
            d = await db.get(Deposit, entry.deposit_id) if entry else None
    if not d:
        raise HTTPException(status_code=404, detail="No deposit matches that ID or hash")
    return await deposit_out(db, d, user, with_check=True)
@router.get("/deposits/{deposit_id}")  # deposit
async def get_deposit(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _load(db, deposit_id)
    if user.id not in (d.tenant_id, d.owner_id) and not is_reviewer(user):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return await deposit_out(db, d, user, with_check=True)
def _check_amount(d: Deposit, body: ProposeIn) -> None:
    if body.deducted > d.amount:
        raise field_error(f"The deduction can't be more than the deposit (₹{d.amount}).", "deducted")
    if body.deducted > 0 and len(body.reason.strip()) < 10:
        raise field_error("Explain the deduction in a sentence (what was damaged or unpaid).", "reason")
@router.post("/deposits/{deposit_id}/propose")  # settle propose
async def propose(deposit_id: str, body: ProposeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _load(db, deposit_id)
    if user.id != d.owner_id:
        raise HTTPException(status_code=403, detail="Only the owner proposes the settlement")
    if d.status not in ("held", "settlement_proposed"):
        raise field_error("This deposit can't be changed now.", None, status.HTTP_409_CONFLICT)
    _check_amount(d, body)
    d.deducted, d.refunded = body.deducted, d.amount - body.deducted
    d.deduction_reason = body.reason.strip() or None
    d.proposed_by, d.proposed_at, d.status = user.id, utcnow(), "settlement_proposed"
    await db.commit()
    return await deposit_out(db, d, user, with_check=True)
@router.post("/deposits/{deposit_id}/respond")  # settle reply
async def respond(deposit_id: str, body: RespondIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _load(db, deposit_id)
    if user.id != d.tenant_id:
        raise HTTPException(status_code=403, detail="Only the tenant answers the proposal")
    if d.status != "settlement_proposed":
        raise field_error("There's no settlement waiting for you.", None, status.HTTP_409_CONFLICT)
    if body.accept:
        await _settle(db, d, user)
    else:
        d.status = "disputed"
    await db.commit()
    return await deposit_out(db, d, user, with_check=True)
@router.post("/admin/deposits/{deposit_id}/settle")  # admin settle
async def admin_settle(deposit_id: str, body: ProposeIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    d = await _load(db, deposit_id)
    if d.status == "settled":
        raise field_error("Already settled.", None, status.HTTP_409_CONFLICT)
    _check_amount(d, body)
    d.deducted, d.refunded = body.deducted, d.amount - body.deducted
    d.deduction_reason = body.reason.strip() or None
    await _settle(db, d, admin)
    await db.commit()
    return await deposit_out(db, d, admin, with_check=True)
@router.post("/admin/deposits", status_code=201)  # admin receipt
async def record_offline_deposit(body: RecordIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    who = body.tenant.strip().lstrip("@").lower()
    tenant = await db.scalar(select(User).where(or_(User.id == body.tenant.strip(), func.lower(User.username) == who,
                                                    func.lower(User.email) == who)))
    if not tenant or tenant.deleted_at:
        raise field_error("No TrustRent account has that username, user ID or email.", "tenant", status.HTTP_404_NOT_FOUND)
    if tenant.banned_at:
        raise field_error("That account is banned. Unban it first.", "tenant", status.HTTP_409_CONFLICT)
    listing = await db.get(Listing, body.listingId.strip().upper())
    if not listing or listing.status == "removed":
        raise field_error("No home has that ID. Use the ID shown on the listing, e.g. IND-VN-101.", "listingId", status.HTTP_404_NOT_FOUND)
    if listing.owner_id == tenant.id:
        raise field_error("The tenant can't be the owner of this home.", "tenant", status.HTTP_409_CONFLICT)
    ref = body.transactionId.strip()
    if await db.scalar(select(Payment.id).where(Payment.payment_id == ref)):
        raise field_error("A receipt already exists for this transaction ID.", "transactionId", status.HTTP_409_CONFLICT)
    open_dep = await db.scalar(select(Deposit.id).where(Deposit.tenant_id == tenant.id, Deposit.listing_id == listing.id,
                                                        Deposit.status != "settled"))
    if open_dep:
        raise field_error(f"This tenant already has an open deposit for this home ({open_dep}).", "listingId", status.HTTP_409_CONFLICT)
    now = utcnow()
    pay = Payment(id=str(uuid.uuid4()), user_id=tenant.id, purpose="deposit", ref=listing.id, amount=body.amount,
                  provider="manual", order_id=f"manual_{uuid.uuid4().hex[:20]}", payment_id=ref, status="paid", paid_at=now)
    db.add(pay)
    d = Deposit(id=f"DEP-{uuid.uuid4().hex[:8].upper()}", listing_id=listing.id, tenant_id=tenant.id, owner_id=listing.owner_id,
                amount=body.amount, payment_id=pay.id, status="held", paid_at=now)
    db.add(d)
    await db.flush()
    await record_deposit(db, d)
    await db.commit()
    return await deposit_out(db, d, admin, with_check=True)
@router.get("/admin/deposits")  # admin deposits
async def all_deposits(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Deposit).order_by(Deposit.paid_at.desc()))
    state = await ledger_state(db)
    return [await deposit_out(db, d, admin, with_check=True, state=state) for d in rows]
@router.post("/admin/deposits/{deposit_id}/owner-paid")  # owner payout
async def owner_paid(deposit_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    d = await _load(db, deposit_id)
    if d.owner_payout != "due":
        raise field_error("Nothing is due to the owner.", None, status.HTTP_409_CONFLICT)
    d.owner_payout = "paid"
    await db.commit()
    return await deposit_out(db, d, admin, with_check=True)
async def _settle(db: AsyncSession, d: Deposit, by: User) -> None:
    pay = await db.get(Payment, d.payment_id)
    if d.refunded and pay and pay.provider == "razorpay" and pay.payment_id:
        try:
            r = await payments.refund(pay.payment_id, d.refunded)
        except payments.PaymentError as e:
            raise field_error(str(e), None, status.HTTP_502_BAD_GATEWAY) from None
        d.refund_ref = r.get("id")
    elif d.refunded and pay and pay.provider == "manual":
        d.refund_ref = "manual-refund"
    elif d.refunded:
        d.refund_ref = "demo-refund"
    d.owner_payout = "due" if d.deducted else None
    d.settled_at, d.settled_by, d.status = utcnow(), by.id, "settled"
    await record_settlement(db, d)
