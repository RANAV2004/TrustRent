import uuid
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
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
router = APIRouter(tags=["Payments"])
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
    return listing
@router.post("/payments/order")  # payment order
async def create_order(body: OrderIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
    if pay.status != "paid":
        if pay.provider == "razorpay":
            if not (body.paymentId and body.signature and payments.verify_signature(pay.order_id, body.paymentId, body.signature)):
                pay.status = "failed"
                await db.commit()
                raise field_error("We couldn't confirm this payment. If money was taken, it will be refunded.",
                                  None, status.HTTP_400_BAD_REQUEST)
            pay.payment_id = body.paymentId
        elif not settings.DEMO_MODE:
            raise HTTPException(status_code=400, detail="Demo payments are switched off")
        else:
            pay.payment_id = f"demo_pay_{uuid.uuid4().hex[:12]}"
        pay.status, pay.paid_at = "paid", utcnow()
        await _fulfil(db, pay, user)
        await db.commit()
    await db.refresh(user)
    out = {"user": user_out(user), "payment": {"id": pay.id, "status": pay.status, "purpose": pay.purpose}}
    if pay.purpose == "deposit":
        dep = await db.scalar(select(Deposit).where(Deposit.payment_id == pay.id))
        out["depositId"] = dep.id if dep else None
    return out
async def _fulfil(db: AsyncSession, pay: Payment, user: User) -> None:
    if pay.purpose == "premium":
        days = PLANS[pay.ref][0]
        start = user.premium_until if has_premium(user) else utcnow()
        user.premium_plan, user.premium_until = pay.ref, start + timedelta(days=days)
        return
    listing = await db.get(Listing, pay.ref)
    dep = Deposit(id=f"DEP-{uuid.uuid4().hex[:8].upper()}", listing_id=listing.id, tenant_id=user.id,
                  owner_id=listing.owner_id, amount=pay.amount, payment_id=pay.id, status="held", paid_at=pay.paid_at)
    db.add(dep)
    await db.flush()
    await record_deposit(db, dep)
