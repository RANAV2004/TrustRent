from contextlib import asynccontextmanager
from pathlib import Path
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import production_problems, production_warnings, settings
from app.services.monitoring import alert, init_sentry
from app.core.database import engine, Base, AsyncSessionLocal, add_missing_columns
from app.api.v1 import health, support, two_factor
from app.api.v1 import accounts, listings, owner, messages, admin, admin_console, payments, deposits, condition, legal
from app.services.seed import remove_sample_data, seed_demo_admin, seed_demo_deposits, seed_sample_listings
import app.models  # noqa: F401
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.mailer import email_enabled
    from app.core.config import ENV_FILES
    found = [str(p) for p in ENV_FILES if p.is_file()]
    print(f"TrustRent settings from: {', '.join(found) or 'no .env file found'}")
    print(f"Sign-up email codes: {'sending from ' + (settings.SMTP_FROM_EMAIL or settings.SMTP_USER) if email_enabled() else 'NOT SET UP (add SMTP_USER and SMTP_APP_PASSWORD to .env)'}")
    problems = production_problems()
    if problems:  # refuse to start rather than store ID documents unsafely
        raise RuntimeError("TrustRent can't start safely:\n- " + "\n- ".join(problems))
    for warning in production_warnings():
        logging.getLogger("trustrent").warning("Before going live: %s", warning)
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
init_sentry()  # before the app is built, so it hooks into every request
API_DOCS = settings.DEMO_MODE or settings.DEBUG
app = FastAPI(
    title="TrustRent Core API",
    description="REST API for TrustRent: A Blockchain-Based Security Deposit Escrow & Verified Tenancy System",
    version="1.3.0",
    lifespan=lifespan,
    # the interactive API docs list every endpoint: only show them in demo/development
    docs_url="/docs" if API_DOCS else None,
    redoc_url="/redoc" if API_DOCS else None,
    openapi_url="/openapi.json" if API_DOCS else None,
)
MAX_REQUEST_BYTES = 60 * 1024 * 1024  # 8 listing photos of 5 MB plus form data
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):  # a bug: tell the admins, give the user a clear message
    route = "/".join("{id}" if any(c.isdigit() for c in part) and len(part) >= 6 else part
                     for part in request.url.path.split("/"))  # IDs out, so one bug = one alert
    alert(f"500:{request.method}:{route}:{type(exc).__name__}", f"Server error on {request.method} {route}",
          f"{type(exc).__name__} while handling {request.method} {route}. Users saw 'Something went wrong'.")
    return JSONResponse({"detail": {"message": "Something went wrong on our side. We've been alerted. Try again shortly.",
                                    "field": None}}, status_code=500)
@app.middleware("http")
async def guard_requests(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_REQUEST_BYTES:
        return JSONResponse({"detail": {"message": "The upload is too large.", "field": None}}, status_code=413)
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(listings.router, prefix="/api/v1")
app.include_router(owner.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(admin_console.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(deposits.router, prefix="/api/v1")
app.include_router(condition.router, prefix="/api/v1")
app.include_router(legal.router, prefix="/api/v1")
app.include_router(two_factor.router, prefix="/api/v1")
app.include_router(support.router, prefix="/api/v1")
Path(settings.MEDIA_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")
@app.get("/")
def root():
    return {"message": "Welcome to TrustRent API"} | ({"docs_url": "/docs"} if API_DOCS else {})