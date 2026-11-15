from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.admin import require_admin
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import field_error
from app.models.deposits import Deposit
from app.models.marketplace import utcnow
from app.models.trust import PayoutAccount, RentInvoice
from app.models.user import User, UserRole
from app.services.accounts import display_name, is_admin, iso
from app.services.audit import audit
from app.services.notify import notify
from app.services.payouts import ACCOUNT_RE, IFSC_RE, LINKED_RE, PAN_RE, route_enabled
from app.services.secrets_box import open_sealed, seal

router = APIRouter(tags=["Owner payouts"])


class PayoutIn(BaseModel):
    holderName: str = Field(min_length=3, max_length=120)
    ifsc: str
    accountNumber: str
    pan: str


class ApproveIn(BaseModel):
    approve: bool
    linkedAccountId: str = ""
    note: str = Field(default="", max_length=300)


def account_out(a: PayoutAccount | None, full: bool = False) -> dict | None:
    if not a:
        return None
    out = {"holderName": a.holder_name, "ifsc": a.ifsc, "accountLast4": a.account_last4, "panLast4": a.pan_last4,
           "status": a.status, "note": a.note, "linked": bool(a.linked_account_id), "updatedAt": iso(a.updated_at)}
    if full:
        out["linkedAccountId"] = a.linked_account_id
    return out


@router.get("/owner/payout-account")  # my payout details
async def my_payout(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"account": account_out(await db.get(PayoutAccount, user.id)), "routeEnabled": route_enabled()}


@router.put("/owner/payout-account")  # add / change bank details
async def set_payout(body: PayoutIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != UserRole.LANDLORD:
        raise HTTPException(status_code=403, detail="Only owners add payout details")
    ifsc, acc, pan = body.ifsc.strip().upper(), body.accountNumber.replace(" ", ""), body.pan.strip().upper()
    if not IFSC_RE.match(ifsc):
        raise field_error("Enter a valid IFSC code, e.g. HDFC0001234.", "ifsc")
    if not ACCOUNT_RE.match(acc):
        raise field_error("Enter a valid bank account number (9 to 18 digits).", "accountNumber")
    if not PAN_RE.match(pan):
        raise field_error("Enter a valid PAN, e.g. ABCDE1234F.", "pan")
    a = await db.get(PayoutAccount, user.id) or PayoutAccount(user_id=user.id)
    if a not in db:
        db.add(a)
    changed = a.account_enc is None or open_sealed(a.account_enc) != acc or a.ifsc != ifsc
    a.holder_name, a.ifsc, a.account_last4, a.account_enc = body.holderName.strip(), ifsc, acc[-4:], seal(acc)
    a.pan_last4, a.pan_enc, a.updated_at = pan[-4:], seal(pan), utcnow()
    if changed:  # a new bank account must be checked again before money goes there
        a.status, a.linked_account_id, a.note = "submitted", None, None
    audit(db, user, "payout_account.updated", "user", user.id, ifsc=ifsc, account_last4=acc[-4:], bank_changed=changed)
    await db.commit()
    if changed:
        admins = [e.lower() for e in settings.ADMIN_EMAILS]
        for staff in await db.scalars(select(User).where(func.lower(User.email).in_(admins))):
            if is_admin(staff):
                notify(staff, "Owner payout details to check", [f"{display_name(user)} added bank details ending {acc[-4:]}."], "/admin/payouts")
    return {"account": account_out(a), "routeEnabled": route_enabled()}


@router.get("/admin/payouts")  # payout desk
async def payouts(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    accounts = list(await db.scalars(select(PayoutAccount).order_by(PayoutAccount.updated_at.desc())))
    deps = list(await db.scalars(select(Deposit).where(Deposit.owner_payout == "due")))
    rents = list(await db.scalars(select(RentInvoice).where(RentInvoice.payout_status == "due")))
    rent_deps = {d.id: d for d in await db.scalars(select(Deposit).where(Deposit.id.in_({r.deposit_id for r in rents})))} if rents else {}
    ids = {a.user_id for a in accounts} | {d.owner_id for d in deps} | {d.owner_id for d in rent_deps.values()}
    people = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    accs = {a.user_id: a for a in accounts}

    def owner(oid):
        u = people.get(oid)
        return {"id": oid, "name": display_name(u) if u else "", "account": account_out(accs.get(oid))}
    due = [{"kind": "deposit", "id": d.id, "amount": d.deducted or 0, "depositId": d.id, "settledAt": iso(d.settled_at),
            "owner": owner(d.owner_id)} for d in deps]
    due += [{"kind": "rent", "id": r.id, "amount": r.amount, "depositId": r.deposit_id, "period": r.period, "paidAt": iso(r.paid_at),
             "owner": owner(rent_deps[r.deposit_id].owner_id)} for r in rents if r.deposit_id in rent_deps]
    return {"routeEnabled": route_enabled(), "due": due,
            "accounts": [{"user": {"id": a.user_id, "name": display_name(people[a.user_id]) if a.user_id in people else ""}}
                         | account_out(a, full=True) for a in accounts]}


@router.post("/admin/payout-accounts/{user_id}")  # approve bank details, link Razorpay Route account
async def review_payout(user_id: str, body: ApproveIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    a = await db.get(PayoutAccount, user_id)
    if not a:
        raise HTTPException(status_code=404, detail="No payout details")
    linked = body.linkedAccountId.strip()
    if body.approve and linked and not LINKED_RE.match(linked):
        raise field_error("A Razorpay linked account id looks like acc_XXXXXXXXXXXXXX.", "linkedAccountId")
    if body.approve and route_enabled() and not linked:
        raise field_error("Create the linked account in the Razorpay Dashboard (Route) and paste its id.", "linkedAccountId")
    a.status = "active" if body.approve else "rejected"
    a.linked_account_id = linked or None if body.approve else None
    a.note, a.updated_at = body.note.strip() or None, utcnow()
    audit(db, admin, "payout_account.approved" if body.approve else "payout_account.rejected", "user", user_id,
          linked_account=a.linked_account_id, note=a.note)
    await db.commit()
    notify(await db.get(User, user_id), "Payout details " + ("approved" if body.approve else "need another look"),
           ["Your bank details are verified. Rent and deposit payouts will go there."] if body.approve
           else [f"We couldn't use these bank details: {a.note or 'please check them'}"], "/owner")
    return account_out(a, full=True)


@router.get("/admin/payout-accounts/{user_id}/reveal")  # full numbers for a manual bank transfer (audited)
async def reveal(user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    a = await db.get(PayoutAccount, user_id)
    if not a:
        raise HTTPException(status_code=404, detail="No payout details")
    audit(db, admin, "payout_account.revealed", "user", user_id)
    await db.commit()
    return {"accountNumber": open_sealed(a.account_enc), "ifsc": a.ifsc, "holderName": a.holder_name, "pan": open_sealed(a.pan_enc)}
