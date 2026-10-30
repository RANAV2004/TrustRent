from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal, add_missing_columns
from app.api.v1 import health, auth, identity, tenancies, evidence, arbitrator, faucet
from app.api.v1 import accounts, listings, owner, messages, admin, admin_console, payments, deposits, condition
from app.services.seed import remove_sample_data, seed_demo_admin, seed_demo_deposits, seed_sample_listings
import app.models  # noqa: F401
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.mailer import email_enabled
    from app.core.config import ENV_FILES
    found = [str(p) for p in ENV_FILES if p.is_file()]
    print(f"TrustRent settings from: {', '.join(found) or 'no .env file found'}")
    print(f"Sign-up email codes: {'sending from ' + (settings.SMTP_FROM_EMAIL or settings.SMTP_USER) if email_enabled() else 'NOT SET UP (add SMTP_USER and SMTP_APP_PASSWORD to .env)'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(add_missing_columns)
    if settings.SEED_SAMPLE_LISTINGS:
        async with AsyncSessionLocal() as db:
            await seed_sample_listings(db)
    else:
        async with AsyncSessionLocal() as db:
            if await remove_sample_data(db):
                print("Sample homes, sample users and their deposits removed")
    async with AsyncSessionLocal() as db:
        await seed_demo_admin(db)
    if settings.SEED_SAMPLE_LISTINGS:
        async with AsyncSessionLocal() as db:
            await seed_demo_deposits(db)
    yield
    await engine.dispose()
app = FastAPI(
    title="TrustRent Core API",
    description="REST API for TrustRent: A Blockchain-Based Security Deposit Escrow & Verified Tenancy System",
    version="1.3.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(identity.router, prefix="/api/v1")
app.include_router(tenancies.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(arbitrator.router, prefix="/api/v1")
app.include_router(faucet.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(listings.router, prefix="/api/v1")
app.include_router(owner.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(admin_console.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(deposits.router, prefix="/api/v1")
app.include_router(condition.router, prefix="/api/v1")
Path(settings.MEDIA_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")
@app.get("/")
def root():
    return {
        "message": "Welcome to TrustRent API",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }