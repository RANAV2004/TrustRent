import asyncio
import logging
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import CLIENT_ERRORS_PER_IP, client_ip
from app.services.monitoring import alert, release, report_to_sentry
router = APIRouter(tags=["System"])
log = logging.getLogger("trustrent.client")


@router.get("/health")  # health: point an uptime monitor here
async def health_check(response: Response, db: AsyncSession = Depends(get_db)):
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=5)
        database = "ok"
    except Exception:  # noqa: BLE001 - any failure means the database can't be used
        database = "down"
        response.status_code = 503
        alert("health:database", "Database unreachable", "The health check couldn't reach the database.")
    return {
        "status": "healthy" if database == "ok" else "unhealthy",
        "database": database,
        "service": "TrustRent Core API",
        "environment": settings.ENVIRONMENT,
        "version": release(),
    }


class ClientErrorIn(BaseModel):
    message: str = Field(max_length=500)
    url: str = Field(default="", max_length=500)
    stack: str = Field(default="", max_length=4000)
    digest: str | None = Field(default=None, max_length=100)


@router.post("/client-errors", status_code=204)  # browser crash reports
async def client_error(body: ClientErrorIn, request: Request):
    if CLIENT_ERRORS_PER_IP.allow(client_ip(request)):
        page = urlsplit(body.url).path[:200] or "unknown page"  # no query strings: they can hold personal data
        message = " ".join(body.message.split())[:300]
        log.warning("Browser error on %s: %s%s", page, message, f" (digest {body.digest})" if body.digest else "")
        report_to_sentry(f"Browser error on {page}: {message}")
    return Response(status_code=204)
