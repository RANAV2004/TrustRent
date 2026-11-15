import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.trust import PayoutAccount
from app.services import payments

log = logging.getLogger(__name__)
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
ACCOUNT_RE = re.compile(r"^\d{9,18}$")
LINKED_RE = re.compile(r"^acc_[A-Za-z0-9]{10,30}$")


def route_enabled() -> bool:
    return settings.RAZORPAY_ROUTE_ENABLED and payments.razorpay_enabled()


async def linked_account(db: AsyncSession, owner_id: str) -> str | None:
    acc = await db.get(PayoutAccount, owner_id)
    return acc.linked_account_id if acc and acc.status == "active" and acc.linked_account_id else None


async def pay_owner(db: AsyncSession, owner_id: str, amount: int, notes: dict, from_payment: str | None = None) -> tuple[str, str | None]:
    """Send the owner's money through Razorpay Route when possible. Returns (payout_status, transfer_id).
    'transferred' = sent to their linked account; 'due' = an admin pays it by hand."""
    if amount <= 0:
        return "none", None
    account = await linked_account(db, owner_id) if route_enabled() else None
    if not account:
        return "due", None
    try:
        if from_payment:
            tid = await payments.transfer_from_payment(from_payment, account, amount, notes)
        else:
            tid = await payments.direct_transfer(account, amount, notes)
        return "transferred", tid
    except payments.PaymentError as e:
        log.warning("Route payout to %s failed (%s); left for manual payout", owner_id, e)
        return "due", None
