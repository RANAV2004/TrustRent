from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.deposits import Deposit
from app.models.marketplace import utcnow
from app.models.trust import Review


def window_end(d: Deposit):
    return d.settled_at + timedelta(days=settings.REVIEW_WINDOW_DAYS) if d.settled_at else None


async def visible_reviews(db: AsyncSession, subject_ids: set[str]) -> list[Review]:
    """Blind reviews: one shows once the other side has reviewed too, or the review window has closed."""
    if not subject_ids:
        return []
    rows = list(await db.scalars(select(Review).where(Review.subject_id.in_(subject_ids), Review.hidden_at.is_(None))))
    if not rows:
        return []
    deposits = {d.id: d for d in await db.scalars(select(Deposit).where(Deposit.id.in_({r.deposit_id for r in rows})))}
    authors = {(r.deposit_id, r.author_id) for r in await db.scalars(select(Review).where(Review.deposit_id.in_(deposits)))}
    now = utcnow()
    out = []
    for r in rows:
        d = deposits.get(r.deposit_id)
        other = r.subject_id
        both = (r.deposit_id, other) in authors
        closed = d is not None and window_end(d) is not None and window_end(d) < now
        if both or closed:
            out.append(r)
    return out


async def rating_summary(db: AsyncSession, subject_ids: set[str]) -> dict[str, dict]:
    out = {sid: {"avg": None, "count": 0} for sid in subject_ids}
    for r in await visible_reviews(db, subject_ids):
        s = out[r.subject_id]
        s["count"] += 1
        s["_sum"] = s.get("_sum", 0) + r.rating
    for s in out.values():
        if s["count"]:
            s["avg"] = round(s.pop("_sum") / s["count"], 1)
        s.pop("_sum", None)
    return out
