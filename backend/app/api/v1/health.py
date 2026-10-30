from fastapi import APIRouter
from app.core.config import settings
router = APIRouter()
@router.get("/health", tags=["System"])  # health
async def health_check():
    return {
        "status": "healthy",
        "service": "TrustRent Core API",
        "environment": settings.ENVIRONMENT,
        "chain_id": settings.CHAIN_ID,
        "version": "1.0.0"
    }
