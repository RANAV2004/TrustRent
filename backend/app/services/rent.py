import html
import secrets
import uuid
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.deposits import Deposit, Payment
from app.models.extras import Agreement
from app.models.marketplace import Listing, utcnow
from app.models.trust import PayoutAccount, RentInvoice
from app.models.user import User
from app.services.accounts import display_name, iso
from app.services.ledger import record_event
from app.services.notify import notify
from app.services.payouts import pay_owner
from app.services.secrets_box import open_sealed

HRA_PAN_LIMIT = 100_000  # yearly rent above this: the tenant needs the landlord's PAN for an HRA claim
ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return ONES[n] if n < 20 else (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))


def _three(n: int) -> str:
    h, rest = divmod(n, 100)
    return " ".join(x for x in ((ONES[h] + " Hundred") if h else "", _two(rest) if rest else "") if x)


def rupees_in_words(n: int) -> str:  # Indian system: crore, lakh, thousand
    if n == 0:
        return "Zero Rupees Only"
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        q, n = divmod(n, size)
        if q:
            parts.append(f"{rupees_in_words(q).removesuffix(' Rupees Only') if q >= 100 else _two(q)} {name}")
    if n:
        parts.append(_three(n))
    return " ".join(parts) + " Rupees Only"


def _add_months(d: date, k: int) -> date:
    y, m = divmod(d.month - 1 + k, 12)
    return date(d.year + y, m + 1, 1)


async def create_schedule(db: AsyncSession, a: Agreement, d: Deposit) -> int:
    """One invoice per month of the agreement. Safe to call again."""
    t = a.terms or {}
    try:
        start = date.fromisoformat(t["startDate"])
    except (KeyError, ValueError):
        return 0
    have = set(await db.scalars(select(RentInvoice.period).where(RentInvoice.deposit_id == d.id)))
    made = 0
    for i in range(int(t.get("months") or 0)):
        first = _add_months(start.replace(day=1), i)
        period = f"{first.year:04d}-{first.month:02d}"
        if period in have:
            continue
        due = first.replace(day=min(int(t.get("rentDueDay") or 5), 28))
        if i == 0 and due < start:
            due = start
        db.add(RentInvoice(id=str(uuid.uuid4()), deposit_id=d.id, agreement_id=a.id, period=period,
                           amount=int(t.get("monthlyRent") or 0), due_date=due.isoformat(), status="due"))
        made += 1
    return made


def invoice_out(r: RentInvoice, today: date | None = None) -> dict:
    today = today or utcnow().date()
    overdue = r.status == "due" and r.due_date < today.isoformat()
    return {"id": r.id, "period": r.period, "amount": r.amount, "dueDate": r.due_date,
            "status": "overdue" if overdue else r.status, "method": r.method, "paidAt": iso(r.paid_at),
            "receiptNo": r.receipt_no, "payout": r.payout_status, "payable": r.status == "due" and r.due_date <= (today + timedelta(days=40)).isoformat()}


async def mark_paid(db: AsyncSession, r: RentInvoice, method: str, payment: Payment | None = None, reference: str | None = None) -> None:
    r.status, r.method, r.paid_at = "paid", method, utcnow()
    r.payment_id = payment.id if payment else None
    r.receipt_no = f"RR-{r.period.replace('-', '')}-{secrets.token_hex(3).upper()}"
    await db.flush()
    await record_event(db, r.deposit_id, "rent", {"invoiceId": r.id, "period": r.period, "amount": r.amount,
                                                   "receiptNo": r.receipt_no, "paidAt": iso(r.paid_at), "reference": reference})
    r.payout_status = "none" if method == "offline" else "due"


async def pay_out(db: AsyncSession, r: RentInvoice) -> None:  # after an online rent payment is committed
    d = await db.get(Deposit, r.deposit_id)
    pay = await db.get(Payment, r.payment_id) if r.payment_id else None
    fee = round(r.amount * settings.RENT_PLATFORM_FEE_PCT / 100)
    source = pay.payment_id if pay and pay.provider == "razorpay" else None
    if not source:
        return  # demo or manual: stays 'due' for an admin
    status, tid = await pay_owner(db, d.owner_id, r.amount - fee, {"rent": r.id, "period": r.period}, from_payment=source)
    r.payout_status, r.payout_ref = status, tid
    await db.commit()


async def owner_pan(db: AsyncSession, owner_id: str) -> str | None:
    acc = await db.get(PayoutAccount, owner_id)
    return open_sealed(acc.pan_enc) if acc else None


async def receipt_html(db: AsyncSession, r: RentInvoice) -> str:
    d = await db.get(Deposit, r.deposit_id)
    tenant, owner = await db.get(User, d.tenant_id), await db.get(User, d.owner_id)
    listing = await db.get(Listing, d.listing_id)
    a = await db.get(Agreement, r.agreement_id)
    yearly = r.amount * 12
    pan = await owner_pan(db, d.owner_id)
    pan_line = (f"Landlord PAN: <strong>{html.escape(pan)}</strong>" if pan else
                "Landlord PAN: <em>not added yet. The owner can add it on TrustRent (Account page, Payouts).</em>")
    if yearly <= HRA_PAN_LIMIT and not pan:
        pan_line = "Landlord PAN: not needed when yearly rent is ₹1,00,000 or less."
    address = (f"{listing.address}, {listing.locality}, {listing.city} {listing.pincode}" if listing and listing.address
               else f"{listing.locality}, {listing.city} {listing.pincode}" if listing else "")
    month = date.fromisoformat(r.period + "-01").strftime("%B %Y")
    pay = await db.get(Payment, r.payment_id) if r.payment_id else None
    mode = f"Online (payment {html.escape(pay.payment_id or '')})" if pay else "Paid directly to the owner (recorded by the owner)"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Rent receipt {html.escape(r.receipt_no or '')}</title>
<style>body{{font-family:Georgia,serif;max-width:640px;margin:40px auto;padding:0 16px;line-height:1.6}}
.box{{border:1px solid #333;padding:24px}}h1{{font-size:22px;margin:0 0 12px}}td{{padding:4px 8px 4px 0;vertical-align:top}}
.small{{font-size:12px;color:#555}}</style></head><body><div class="box">
<h1>Rent Receipt</h1>
<table>
<tr><td>Receipt no.</td><td><strong>{html.escape(r.receipt_no or '')}</strong></td></tr>
<tr><td>Date</td><td>{r.paid_at:%d %B %Y}</td></tr>
<tr><td>Received from</td><td>{html.escape(display_name(tenant))}</td></tr>
<tr><td>Amount</td><td><strong>₹{r.amount:,}</strong> ({rupees_in_words(r.amount)})</td></tr>
<tr><td>Towards</td><td>Rent for {month}</td></tr>
<tr><td>Property</td><td>{html.escape(address)}</td></tr>
<tr><td>Paid by</td><td>{mode}</td></tr>
<tr><td>Landlord</td><td>{html.escape(display_name(owner))}</td></tr>
<tr><td colspan="2">{pan_line}</td></tr>
</table>
<p class="small">Agreement fingerprint: {html.escape(a.text_hash if a else '')}<br>Generated by TrustRent for deposit {html.escape(d.id)}.
This electronically generated receipt is recorded in the TrustRent receipt chain. For cash payments above ₹5,000 the
Income Tax Department may expect a revenue stamp signed by the landlord.</p>
</div></body></html>"""


async def statement_html(db: AsyncSession, d: Deposit, fy: int) -> str:  # financial year fy-04 to (fy+1)-03, for HRA
    rows = list(await db.scalars(select(RentInvoice).where(RentInvoice.deposit_id == d.id, RentInvoice.status == "paid",
                                                          RentInvoice.period >= f"{fy}-04", RentInvoice.period <= f"{fy + 1}-03")
                                 .order_by(RentInvoice.period)))
    tenant, owner = await db.get(User, d.tenant_id), await db.get(User, d.owner_id)
    total = sum(r.amount for r in rows)
    pan = await owner_pan(db, d.owner_id)
    body = "".join(f"<tr><td>{html.escape(r.period)}</td><td>{html.escape(r.receipt_no or '')}</td><td>{r.paid_at:%d %b %Y}</td>"
                   f"<td style='text-align:right'>₹{r.amount:,}</td></tr>" for r in rows) or "<tr><td colspan=4>No paid rent in this year.</td></tr>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Rent statement FY {fy}-{str(fy + 1)[2:]}</title>
<style>body{{font-family:Georgia,serif;max-width:720px;margin:40px auto;padding:0 16px}}table{{width:100%;border-collapse:collapse}}
td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left}}</style></head><body>
<h1>Rent statement, financial year {fy}-{str(fy + 1)[2:]}</h1>
<p>Tenant: {html.escape(display_name(tenant))}<br>Landlord: {html.escape(display_name(owner))}{f", PAN {html.escape(pan)}" if pan else ""}<br>Deposit: {html.escape(d.id)}</p>
<table><tr><th>Month</th><th>Receipt</th><th>Paid on</th><th style='text-align:right'>Amount</th></tr>{body}
<tr><th colspan=3>Total</th><th style='text-align:right'>₹{total:,}</th></tr></table>
<p>{rupees_in_words(total)}. Use this statement and the monthly receipts for your HRA claim.</p></body></html>"""


async def send_reminders(db: AsyncSession) -> int:
    today = utcnow().date()
    soon = (today + timedelta(days=settings.RENT_REMINDER_DAYS)).isoformat()
    sent = 0
    for r in list(await db.scalars(select(RentInvoice).where(RentInvoice.status == "due", RentInvoice.due_date <= soon))):
        d = await db.get(Deposit, r.deposit_id)
        if not d or d.status in ("settled", "settling"):
            continue
        tenant, owner = await db.get(User, d.tenant_id), await db.get(User, d.owner_id)
        if r.due_date < today.isoformat():
            if not r.overdue_notified_at:
                notify(tenant, f"Rent for {r.period} is overdue", [f"₹{r.amount:,} was due on {r.due_date}. Pay it on TrustRent to get a receipt."], "/deposits")
                notify(owner, f"Rent for {r.period} is overdue", [f"{display_name(tenant)} hasn't paid ₹{r.amount:,} due on {r.due_date} yet."], "/deposits")
                r.overdue_notified_at = utcnow()
                sent += 1
        elif not r.reminded_at:
            notify(tenant, f"Rent for {r.period} is due on {r.due_date}", [f"₹{r.amount:,}. Pay on TrustRent and get an HRA-ready receipt."], "/deposits")
            r.reminded_at = utcnow()
            sent += 1
    await db.commit()
    return sent


async def end_tenancy(db: AsyncSession, d: Deposit) -> None:  # settled deposit: future rent is cancelled
    when = (d.settled_at or utcnow()).date().isoformat()
    for r in await db.scalars(select(RentInvoice).where(RentInvoice.deposit_id == d.id, RentInvoice.status == "due",
                                                        RentInvoice.due_date > when)):
        r.status = "cancelled"
