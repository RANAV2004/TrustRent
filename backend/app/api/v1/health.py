from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.core.config import settings
from app.core.database import AsyncSessionLocal
router = APIRouter()
@router.get("/health", tags=["System"])  # health
async def health_check():
    from app.main import VERSION
    return {
        "status": "healthy",
        "service": "TrustRent Core API",
        "environment": settings.ENVIRONMENT,
        "chain_id": settings.CHAIN_ID,
        "version": VERSION,
    }
@router.get("/health/ready", tags=["System"])  # readiness: database reachable
async def ready():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse({"status": "unavailable", "database": False}, status_code=503)
    return {"status": "ready", "database": True}
