import logging
from datetime import timedelta
from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.errors import field_error
from app.models.deposits import Deposit, Payment
from app.models.marketplace import utcnow
from app.models.user import User
from app.services import payments
from app.services.ledger import record_settlement
from app.services.notify import notify

log = logging.getLogger(__name__)
SYSTEM = "system"


def respond_by(d: Deposit):
    return d.proposed_at + timedelta(days=settings.SETTLEMENT_RESPONSE_DAYS) if d.status == "settlement_proposed" and d.proposed_at else None


def claim_by(d: Deposit):
    return d.moved_out_at + timedelta(days=settings.MOVE_OUT_CLAIM_DAYS) if d.status == "held" and d.moved_out_at else None


async def settle(db: AsyncSession, d: Deposit, by_id: str, deducted: int, reason: str | None) -> Deposit:
    """Two-phase: claim the deposit (status -> settling), refund, then record. A deposit is settled once only."""
    previous = d.status
    if previous == "settling" and (d.refund_ref or not d.refunded):  # refund done, recording was interrupted: finish it
        return await _finish(db, d, by_id)
    if previous in ("settled", "settling"):
        raise field_error("Already settled." if previous == "settled" else
                          "This settlement is in progress. Check the refund in Razorpay before retrying.",
                          None, status.HTTP_409_CONFLICT)
    if not 0 <= deducted <= d.amount:
        raise field_error(f"The deduction can't be more than the deposit (₹{d.amount}).", "deducted")
    claimed = await db.execute(update(Deposit).where(Deposit.id == d.id, Deposit.status == previous)
                               .values(status="settling", deducted=deducted, refunded=d.amount - deducted,
                                       deduction_reason=(reason or "").strip() or None)
                               .execution_options(synchronize_session=False))
    await db.commit()
    await db.refresh(d)
    if claimed.rowcount != 1:
        raise field_error("Someone else just changed this deposit. Reload and try again.", None, status.HTTP_409_CONFLICT)
    pay = await db.get(Payment, d.payment_id)
    try:
        if d.refunded and pay and pay.provider == "razorpay" and pay.payment_id:
            r = await payments.refund(pay.payment_id, d.refunded)
            d.refund_ref = r.get("id") or "razorpay-refund"
            await db.commit()  # keep the refund id even if a later step fails, so it's never sent twice
        elif d.refunded and pay and pay.provider == "manual":
            d.refund_ref = "manual-refund"
        elif d.refunded:
            d.refund_ref = "demo-refund"
    except payments.PaymentError as e:
        d.status = previous
        await db.commit()
        raise field_error(str(e), None, status.HTTP_502_BAD_GATEWAY) from None
    return await _finish(db, d, by_id)


async def _finish(db: AsyncSession, d: Deposit, by_id: str) -> Deposit:
    d.owner_payout = "due" if d.deducted else None
    d.settled_at, d.settled_by, d.status = utcnow(), by_id, "settled"
    await record_settlement(db, d)
    await db.commit()
    await db.refresh(d)
    tenant, owner = await db.get(User, d.tenant_id), await db.get(User, d.owner_id)
    msg = [f"Deposit {d.id} is settled: ₹{d.refunded:,} refunded to the tenant and ₹{d.deducted:,} to the owner."]
    if by_id == SYSTEM:
        msg.append("It was settled automatically because the deadline passed.")
    for u in (tenant, owner):
        notify(u, f"Deposit {d.id} settled", msg, "/deposits")
    return d


async def sweep_deadlines(db: AsyncSession) -> dict:
    """Auto-accept proposals the tenant ignored; fully refund when the owner never proposed after move-out."""
    now = utcnow()
    accepted = refunded = 0
    cutoff = now - timedelta(days=settings.SETTLEMENT_RESPONSE_DAYS)
    for d in list(await db.scalars(select(Deposit).where(Deposit.status == "settlement_proposed", Deposit.proposed_at <= cutoff))):
        try:
            await settle(db, d, SYSTEM, d.deducted or 0, d.deduction_reason)
            accepted += 1
        except Exception as e:  # noqa: BLE001
            log.warning("Auto-accept of %s failed: %s", d.id, e)
            await db.rollback()
    cutoff = now - timedelta(days=settings.MOVE_OUT_CLAIM_DAYS)
    for d in list(await db.scalars(select(Deposit).where(Deposit.status == "held", Deposit.moved_out_at.is_not(None),
                                                       Deposit.moved_out_at <= cutoff))):
        try:
            await settle(db, d, SYSTEM, 0, "No deduction was claimed in time after move-out")
            refunded += 1
        except Exception as e:  # noqa: BLE001
            log.warning("Auto-refund of %s failed: %s", d.id, e)
            await db.rollback()
    return {"autoAccepted": accepted, "autoRefunded": refunded}
