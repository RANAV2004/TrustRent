import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal, add_missing_columns, add_indexes
from app.core.observability import GatewayMiddleware, setup_logging
from app.api.v1 import health, auth, identity, tenancies, evidence, arbitrator
from app.api.v1 import accounts, listings, owner, messages, admin, admin_console, payments, deposits, condition
from app.api.v1 import agreements, disputes, searches
from app.services.seed import remove_sample_data, seed_demo_admin, seed_demo_deposits, seed_sample_listings
import app.models  # noqa: F401
VERSION = "1.4.0"
setup_logging()
log = logging.getLogger("trustrent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.mailer import email_enabled
    from app.services import jobs
    from app.services.notify import drain
    from app.core.config import ENV_FILES
    found = [str(p) for p in ENV_FILES if p.is_file()]
    log.info("TrustRent settings from: %s", ", ".join(found) or "no .env file found")
    log.info("Emails: %s", "sending from " + (settings.SMTP_FROM_EMAIL or settings.SMTP_USER) if email_enabled()
             else "NOT SET UP (add SMTP_USER and SMTP_APP_PASSWORD to .env)")
    if settings.DEMO_MODE:
        log.warning("DEMO_MODE is ON: demo sign-ins, auto-approved IDs and fake payments. Never use it with real users.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(add_missing_columns)
        await conn.run_sync(add_indexes)
    if settings.SEED_SAMPLE_LISTINGS:
        async with AsyncSessionLocal() as db:
            await seed_sample_listings(db)
    else:
        async with AsyncSessionLocal() as db:
            if await remove_sample_data(db):
                log.info("Sample homes, sample users and their deposits removed")
    async with AsyncSessionLocal() as db:
        await seed_demo_admin(db)
    if settings.SEED_SAMPLE_LISTINGS:
        async with AsyncSessionLocal() as db:
            await seed_demo_deposits(db)
    worker = asyncio.create_task(jobs.loop()) if settings.RUN_BACKGROUND_JOBS else None
    yield
    if worker:
        worker.cancel()
    await drain()
    await engine.dispose()
app = FastAPI(
    title="TrustRent Core API",
    description="REST API for TrustRent: A Blockchain-Based Security Deposit Escrow & Verified Tenancy System",
    version=VERSION,
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,  # the app sends a bearer token, never cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Total-Count", "Retry-After"],
)
app.add_middleware(GatewayMiddleware)
ROUTERS = [health, auth, accounts, listings, owner, messages, admin, admin_console, payments, deposits, condition,
           agreements, disputes, searches]
if settings.ENABLE_LEGACY_API:  # old on-chain vault flow; off unless asked for
    ROUTERS += [identity, tenancies, evidence, arbitrator]
for module in ROUTERS:
    app.include_router(module.router, prefix="/api/v1")
Path(settings.MEDIA_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")
@app.get("/")
def root():
    return {
        "message": "Welcome to TrustRent API",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }
