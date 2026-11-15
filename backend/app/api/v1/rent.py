from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.admin import require_admin
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.errors import field_error
from app.models.deposits import Deposit
from app.models.marketplace import utcnow
from app.models.trust import RentInvoice
from app.models.user import User
from app.services.accounts import is_reviewer
from app.services.audit import audit
from app.services.notify import notify
from app.services.rent import invoice_out, mark_paid, receipt_html, statement_html

router = APIRouter(tags=["Rent"])
HTML_HEADERS = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "Cache-Control": "no-store"}


class OfflineIn(BaseModel):
    method: str = Field(pattern=r"^(cash|upi|bank|cheque)$")
    reference: str = Field(default="", max_length=60)


async def _deposit(db: AsyncSession, deposit_id: str, user: User) -> Deposit:
    d = await db.get(Deposit, deposit_id.strip().upper())
    if not d or (user.id not in (d.tenant_id, d.owner_id) and not is_reviewer(user)):
        raise HTTPException(status_code=404, detail="Deposit not found")
    return d


async def _invoice(db: AsyncSession, invoice_id: str, user: User) -> tuple[RentInvoice, Deposit]:
    r = await db.get(RentInvoice, invoice_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rent invoice not found")
    return r, await _deposit(db, r.deposit_id, user)


@router.get("/deposits/{deposit_id}/rent")  # rent schedule
async def rent_schedule(deposit_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    rows = list(await db.scalars(select(RentInvoice).where(RentInvoice.deposit_id == d.id).order_by(RentInvoice.period)))
    out = [invoice_out(r) for r in rows]
    paid = [r for r in rows if r.status == "paid"]
    years = sorted({int(r.period[:4]) - (1 if int(r.period[5:]) < 4 else 0) for r in paid})
    return {"invoices": out, "role": "tenant" if user.id == d.tenant_id else "owner" if user.id == d.owner_id else "admin",
            "paidTotal": sum(r.amount for r in paid), "financialYears": years}


@router.post("/rent/{invoice_id}/mark-paid")  # owner records cash / UPI / bank rent
async def mark_paid_offline(invoice_id: str, body: OfflineIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    r, d = await _invoice(db, invoice_id, user)
    if user.id != d.owner_id:
        raise HTTPException(status_code=403, detail="Only the owner records rent paid outside TrustRent")
    if r.status != "due":
        raise field_error("This month is already paid or cancelled.", None, status.HTTP_409_CONFLICT)
    await mark_paid(db, r, "offline", reference=f"{body.method}:{body.reference.strip()}" if body.reference.strip() else body.method)
    await db.commit()
    notify(await db.get(User, d.tenant_id), f"Rent receipt for {r.period}", [f"The owner recorded ₹{r.amount:,} as paid ({body.method}). Your receipt is ready."], "/deposits")
    return invoice_out(r)


@router.get("/rent/{invoice_id}/receipt")  # HRA receipt
async def receipt(invoice_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    r, d = await _invoice(db, invoice_id, user)
    if r.status != "paid":
        raise HTTPException(status_code=404, detail="No receipt: this month isn't paid")
    return Response(await receipt_html(db, r), media_type="text/html", headers=HTML_HEADERS)


@router.get("/deposits/{deposit_id}/rent/statement")  # yearly statement for HRA
async def statement(deposit_id: str, fy: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _deposit(db, deposit_id, user)
    if not 2000 <= fy <= 2100:
        raise field_error("Unknown financial year.", "fy")
    return Response(await statement_html(db, d, fy), media_type="text/html", headers=HTML_HEADERS)


@router.post("/admin/rent/{invoice_id}/payout-paid")  # manual owner payout
async def rent_payout_paid(invoice_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(RentInvoice, invoice_id)
    if not r or r.payout_status != "due":
        raise field_error("Nothing is due to the owner for this month.", None, status.HTTP_409_CONFLICT)
    r.payout_status = "paid"
    audit(db, admin, "payout.marked_paid", "rent", r.id, amount=r.amount, at=utcnow().isoformat())
    await db.commit()
    return invoice_out(r)
