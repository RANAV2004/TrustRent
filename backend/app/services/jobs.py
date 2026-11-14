import asyncio
import logging
from app.core.config import settings
from app.core.database import AsyncSessionLocal

log = logging.getLogger(__name__)


async def run_once() -> dict:
    from app.services.ledger import anchor_pending
    from app.services.settlement import sweep_deadlines
    from app.services.search_alerts import send_alerts
    out = {}
    async with AsyncSessionLocal() as db:
        out.update(await sweep_deadlines(db))
    async with AsyncSessionLocal() as db:
        out["anchored"] = await anchor_pending(db)
    async with AsyncSessionLocal() as db:
        out["alerts"] = await send_alerts(db)
    return out


async def loop() -> None:  # one worker per process; every step is safe to repeat
    await asyncio.sleep(5)
    while True:
        try:
            result = await run_once()
            if any(result.values()):
                log.info("Background jobs: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Background jobs failed")
        await asyncio.sleep(settings.JOB_INTERVAL_SECONDS)
