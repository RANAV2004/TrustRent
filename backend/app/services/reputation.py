from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deposits import Deposit
from app.models.marketplace import Listing


async def owner_stats(db: AsyncSession, owner_ids: set[str]) -> dict[str, dict]:
    """Track record from real settled deposits: completed, full refunds, disputes lost, average deduction."""
    out = {oid: {"tenancies_completed": 0, "full_refunds": 0, "disputes_lost": 0, "disputes": 0, "avg_deduction_pct": 0.0}
           for oid in owner_ids}
    if not owner_ids:
        return out
    pct: dict[str, list[float]] = {oid: [] for oid in owner_ids}
    rows = await db.scalars(select(Deposit).where(Deposit.owner_id.in_(owner_ids), Deposit.status == "settled"))
    for d in rows:
        s = out[d.owner_id]
        s["tenancies_completed"] += 1
        if not d.deducted:
            s["full_refunds"] += 1
        if d.disputed_at:
            s["disputes"] += 1
            if (d.proposed_deducted or 0) > (d.deducted or 0):  # reviewer gave the owner less than asked
                s["disputes_lost"] += 1
        if d.amount:
            pct[d.owner_id].append((d.deducted or 0) / d.amount * 100)
    for oid, values in pct.items():
        if values:
            out[oid]["avg_deduction_pct"] = round(sum(values) / len(values), 1)
    return out


def record_for(listing: Listing, stats: dict | None) -> dict:
    """Sample homes keep their illustrative numbers; real owners get computed ones."""
    if listing.listed_days_ago is not None or stats is None:
        return {"tenancies_completed": listing.tenancies_completed or 0, "full_refunds": listing.full_refunds or 0,
                "disputes_lost": listing.disputes_lost or 0, "avg_deduction_pct": None, "computed": False}
    return {**{k: stats[k] for k in ("tenancies_completed", "full_refunds", "disputes_lost", "avg_deduction_pct")},
            "computed": True}
