import json
import logging
import uuid
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.accounts import PLANS, field_error
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.deposits import Deposit, Payment
from app.models.marketplace import Listing, utcnow
from app.models.user import User
from app.services import chain, payments
from app.services.accounts import display_name, has_premium, user_out
from app.services.ledger import record_deposit
from app.services.marketplace import visit_confirmed
from app.services.mailer import email_enabled
from app.services.monitoring import alert
from app.services.notify import notify, rupees
router = APIRouter(tags=["Payments"])
log = logging.getLogger(__name__)
class OrderIn(BaseModel):
    purpose: str
    planId: str | None = None
    listingId: str | None = None
class VerifyIn(BaseModel):
    orderId: str
    paymentId: str | None = None
    signature: str | None = None
@router.get("/config")  # config
async def public_config():
    return {
        "demoMode": settings.DEMO_MODE,
        "payments": "razorpay" if payments.razorpay_enabled() else ("demo" if settings.DEMO_MODE else "off"),
        "razorpayKeyId": settings.RAZORPAY_KEY_ID if payments.razorpay_enabled() else None,
        "emailCodes": "smtp" if email_enabled() else ("demo" if settings.DEMO_MODE else "off"),
        "depositNetwork": chain.network_name() if chain.enabled() else "trustrent-ledger",
        "explorerTxUrl": settings.CHAIN_EXPLORER_TX_URL if chain.enabled() else None,
    }
async def _deposit_listing(db: AsyncSession, user: User, listing_id: str | None) -> Listing:
    listing = await db.get(Listing, listing_id or "")
    if not listing or listing.status != "live":
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id == user.id:
        raise field_error("You can't pay a deposit on your own home.")
    if not await visit_confirmed(db, listing.id, user.id):
        raise field_error("Visit the home first: the deposit unlocks once the owner confirms your visit.",
                          None, status.HTTP_403_FORBIDDEN)
    open_dep = await db.scalar(select(Deposit.id).where(Deposit.listing_id == listing.id, Deposit.tenant_id == user.id,
                                                       Deposit.status != "settled"))
    if open_dep:
        raise field_error(f"You already have an active deposit for this home ({open_dep}).", None, status.HTTP_409_CONFLICT)
    if (listing.deposit or 0) <= 0:
        raise field_error("This home asks for no security deposit, so there's nothing to pay.")
    return listing
@router.post("/payments/order")  # payment order
async def create_order(body: OrderIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.is_lawyer:
        raise field_error("Lawyer accounts can't make payments here.", None, status.HTTP_403_FORBIDDEN)
    if not user.is_verified:
        raise field_error("Verify your identity first (Premium page, step 1).", None, status.HTTP_403_FORBIDDEN)
    if body.purpose == "premium":
        if body.planId not in PLANS:
            raise field_error("Unknown plan.", "planId")
        ref, amount, description = body.planId, PLANS[body.planId][1], f"TrustRent Premium for {PLANS[body.planId][0]} days"
    elif body.purpose == "deposit":
        listing = await _deposit_listing(db, user, body.listingId)
        ref, amount, description = listing.id, listing.deposit, f"Security deposit for {listing.title}"
    else:
        raise field_error("Unknown payment.", "purpose")
    pay = Payment(id=str(uuid.uuid4()), user_id=user.id, purpose=body.purpose, ref=ref, amount=amount, provider="demo",
                  order_id="")
    if payments.razorpay_enabled():
        try:
            order = await payments.create_order(amount, pay.id, {"purpose": body.purpose, "ref": ref, "user": user.id})
        except payments.PaymentError as e:
            raise field_error(str(e), None, status.HTTP_502_BAD_GATEWAY) from None
        pay.provider, pay.order_id = "razorpay", order["id"]
    elif settings.DEMO_MODE:
        pay.order_id = f"demo_{uuid.uuid4().hex[:16]}"
    else:
        raise field_error("Payments aren't set up on this server yet.", None, status.HTTP_503_SERVICE_UNAVAILABLE)
    db.add(pay)
    await db.commit()
    return {
        "orderId": pay.order_id, "provider": pay.provider, "keyId": settings.RAZORPAY_KEY_ID or None,
        "amount": amount, "currency": "INR", "description": description,
        "prefill": {"name": display_name(user), "email": user.email, "contact": user.phone or ""},
    }
@router.post("/payments/verify")  # payment verify
async def verify_payment(body: VerifyIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pay = await db.scalar(select(Payment).where(Payment.order_id == body.orderId, Payment.user_id == user.id))
    if not pay:
        raise HTTPException(status_code=404, detail="Order not found")
    if pay.status in ("created", "failed"):
        if pay.provider == "razorpay":
            if not (body.paymentId and body.signature and payments.verify_signature(pay.order_id, body.paymentId, body.signature)):
                pay.status = "failed"
                await db.commit()
                raise field_error("We couldn't confirm this payment. If money was taken, it will be refunded.",
                                  None, status.HTTP_400_BAD_REQUEST)
            payment_id = body.paymentId
        elif not settings.DEMO_MODE:
            raise HTTPException(status_code=400, detail="Demo payments are switched off")
        else:
            payment_id = f"demo_pay_{uuid.uuid4().hex[:12]}"
        problem = await complete_payment(db, pay, user, payment_id)
        if problem:
            raise field_error(problem, None, status.HTTP_409_CONFLICT)
    elif pay.status in ("refund_due", "cancelled"):
        raise field_error("This payment couldn't be used and will be refunded.", None, status.HTTP_409_CONFLICT)
    await db.refresh(user)
    await db.refresh(pay)
    out = {"user": user_out(user), "payment": {"id": pay.id, "status": pay.status, "purpose": pay.purpose}}
    if pay.purpose == "deposit":
        dep = await db.scalar(select(Deposit).where(Deposit.payment_id == pay.id))
        out["depositId"] = dep.id if dep else None
    return out
async def complete_payment(db: AsyncSession, pay: Payment, user: User, payment_id: str | None) -> str | None:
    """Mark the order paid exactly once and give the customer what they bought.

    The browser callback and Razorpay's webhook can arrive together, or a customer can click twice: the
    conditional UPDATE lets only one of them through, so Premium or a deposit is never granted twice.
    Returns a message when the money can't be used (the payment is flagged for a refund).
    """
    now = utcnow()
    claimed = await db.execute(
        update(Payment).where(Payment.id == pay.id, Payment.status.in_(("created", "failed")))
        .values(status="paid", paid_at=now, payment_id=payment_id).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:  # someone else already completed it
        await db.rollback()
        return None
    pay.status, pay.paid_at, pay.payment_id = "paid", now, payment_id
    problem = await _fulfil(db, pay, user)
    if problem:  # money taken but nothing delivered: flag it for refund
        pay.status = "refund_due" if pay.provider == "razorpay" else "cancelled"
    await db.commit()
    if not problem:
        await _notify_paid(db, pay, user)
    if problem and pay.provider == "razorpay":
        alert(f"refund:{pay.id}", "A payment needs a refund",
              f"Razorpay payment {payment_id} (order {pay.order_id}, Rs {pay.amount}) was taken but couldn't be used: "
              f"{problem} Refund it from the Razorpay dashboard.")
    return problem
@router.post("/payments/razorpay/webhook", include_in_schema=False)  # razorpay webhook
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Completes payments when the customer closed the window before the browser could confirm them.

    In the Razorpay dashboard add a webhook to https://<backend>/api/v1/payments/razorpay/webhook for the
    events payment.captured and order.paid, and put its secret in RAZORPAY_WEBHOOK_SECRET.
    """
    raw = await request.body()
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=404, detail="Not Found")
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not payments.verify_webhook_signature(raw, sig, secret):
        raise HTTPException(status_code=400, detail="Bad signature")
    try:
        event = json.loads(raw)
        entity = event["payload"]["payment"]["entity"]
        order_id, payment_id = entity["order_id"], entity["id"]
    except (ValueError, KeyError, TypeError):
        return {"ok": True, "ignored": True}
    if event.get("event") not in ("payment.captured", "order.paid"):
        return {"ok": True, "ignored": True}
    pay = await db.scalar(select(Payment).where(Payment.order_id == order_id, Payment.provider == "razorpay"))
    if not pay or pay.status not in ("created", "failed"):
        return {"ok": True}
    user = await db.get(User, pay.user_id)
    if not user:
        return {"ok": True}
    problem = await complete_payment(db, pay, user, payment_id)
    if problem:
        log.warning("Webhook payment %s for order %s needs a refund: %s", payment_id, order_id, problem)
    return {"ok": True}
async def _notify_paid(db: AsyncSession, pay: Payment, user: User) -> None:
    if pay.purpose == "premium":
        notify(user, "Your TrustRent Premium is active", [
            f"We received {rupees(pay.amount)} for Premium ({PLANS[pay.ref][0]} days).",
            f"Payment reference: {pay.payment_id}."], "/premium")
        return
    dep = await db.scalar(select(Deposit).where(Deposit.payment_id == pay.id))
    listing = await db.get(Listing, dep.listing_id) if dep else None
    if not dep or not listing:
        return
    notify(user, f"Deposit receipt {dep.id}", [
        f"You paid a security deposit of {rupees(dep.amount)} for {listing.title}.",
        f"Your receipt ID is {dep.id}. Anyone can check it on TrustRent's receipt lookup."], "/deposits")
    notify(await db.get(User, dep.owner_id), f"Deposit received for {listing.title}", [
        f"{display_name(user)} paid a security deposit of {rupees(dep.amount)} (receipt {dep.id}).",
        "TrustRent holds it until the tenancy ends and you propose the settlement."], "/deposits")
async def _fulfil(db: AsyncSession, pay: Payment, user: User) -> str | None:
    if pay.purpose == "premium":
        days = PLANS[pay.ref][0]
        start = user.premium_until if has_premium(user) else utcnow()
        user.premium_plan, user.premium_until = pay.ref, start + timedelta(days=days)
        return None
    listing = await db.get(Listing, pay.ref)
    if not listing:
        return "This home is no longer listed, so no deposit was taken. Any amount charged will be refunded."
    open_dep = await db.scalar(select(Deposit.id).where(Deposit.listing_id == listing.id, Deposit.tenant_id == user.id,
                                                       Deposit.status != "settled"))
    if open_dep:  # second order paid for the same home
        return f"You already have an active deposit for this home ({open_dep}). This payment will be refunded."
    dep = Deposit(id=f"DEP-{uuid.uuid4().hex[:8].upper()}", listing_id=listing.id, tenant_id=user.id,
                  owner_id=listing.owner_id, amount=pay.amount, payment_id=pay.id, status="held", paid_at=pay.paid_at)
    db.add(dep)
    await db.flush()
    await record_deposit(db, dep)
    return None
