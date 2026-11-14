from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.extras import SavedSearch
from app.models.marketplace import Listing, utcnow
from app.models.user import User
from app.services.notify import notify
from app.services.reputation import owner_stats, record_for
from app.services.search import Filters, matches


async def send_alerts(db: AsyncSession) -> int:
    """Email each saved search about homes that went live since its last alert."""
    searches = list(await db.scalars(select(SavedSearch)))
    if not searches:
        return 0
    oldest = min((s.last_alert_at or s.created_at) for s in searches)
    fresh = list(await db.scalars(select(Listing).where(Listing.status == "live", Listing.listed_at > oldest,
                                                        Listing.listed_days_ago.is_(None))))
    if not fresh:
        return 0
    stats = await owner_stats(db, {x.owner_id for x in fresh})
    sent = 0
    now = utcnow()
    for s in searches:
        since = s.last_alert_at or s.created_at
        f = Filters.from_dict(s.filters or {})
        hits = [x for x in fresh if x.listed_at > since and x.owner_id != s.user_id and
                matches(x, f, record_for(x, stats.get(x.owner_id))["tenancies_completed"])]
        if not hits:
            continue
        user = await db.get(User, s.user_id)
        lines = [f"{len(hits)} new home{'s' if len(hits) > 1 else ''} match your saved search “{s.name}”:"]
        lines += [f"{x.title}, {x.locality}: ₹{x.rent:,}/month" for x in hits[:5]]
        notify(user, f"New homes for “{s.name}”", lines, f"/search?q={f.q}" if f.q else "/search")
        s.last_alert_at = now
        sent += 1
    await db.commit()
    return sent
