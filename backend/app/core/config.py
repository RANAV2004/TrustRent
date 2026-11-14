from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
_BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env", Path(".env"))
class Settings(BaseSettings):  # settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite+aiosqlite:///./trustrent.db"
    POLYGON_AMOY_RPC_URL: str = "https://rpc-amoy.polygon.technology"
    CHAIN_ID: int = 80002
    BACKEND_ATTESTER_PRIVATE_KEY: str = Field(default="")
    IDENTITY_REGISTRY_ADDRESS: str = Field(default="")
    ARBITRATOR_REGISTRY_ADDRESS: str = Field(default="")
    TENANCY_FACTORY_ADDRESS: str = Field(default="")
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_DIR: str = "./local_storage"
    STORAGE_MASTER_KEY_HEX: str = ""
    DEMO_MODE: bool = False  # never on in production: demo logins, auto-approval and free payments
    ENABLE_LEGACY_API: bool = False  # old wallet/tenancy/evidence endpoints
    RATE_LIMIT_ENABLED: bool = True
    MAX_REQUEST_MB: int = 50
    FRONTEND_URL: str = "http://localhost:3000"
    REQUIRE_STAFF_MFA: bool = True
    RAZORPAY_WEBHOOK_SECRET: str = ""
    SETTLEMENT_RESPONSE_DAYS: int = 7  # tenant silent this long: proposal auto-accepted
    MOVE_OUT_CLAIM_DAYS: int = 14  # owner silent this long after move-out: full refund
    JOB_INTERVAL_SECONDS: int = 600
    RUN_BACKGROUND_JOBS: bool = True
    SENTRY_DSN: str = ""
    LOG_JSON: bool = False
    GOOGLE_CLIENT_ID: str = ""
    MEDIA_DIR: str = "./media"
    SEED_SAMPLE_LISTINGS: bool = True
    EARLY_ACCESS_HOURS: int = 48
    ADMIN_EMAILS: List[str] = ["admin@trustrent.in"]
    DEMO_ADMIN_PASSWORD: str = ""
    VERIFICATION_REGISTER_PATH: str = "./registers/verification_register.xlsx"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_APP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "TrustRent"
    SMTP_FROM_EMAIL: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "auto"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_PRIVATE_BUCKET: str = ""
    S3_PUBLIC_BUCKET: str = ""
    MEDIA_PUBLIC_BASE_URL: str = ""
    DEPOSIT_REGISTRY_ADDRESS: str = ""
    CHAIN_SIGNER_PRIVATE_KEY: str = ""
    CHAIN_EXPLORER_TX_URL: str = "https://amoy.polygonscan.com/tx/"
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore"
    )
UNSAFE_JWT_SECRETS = {"", "super-secret-jwt-key-change-in-production-min-32-chars", "change-me", "change-this-to-a-long-random-secret-min-32-chars"}
UNSAFE_STORAGE_KEYS = {"", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
DEV_STORAGE_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
settings = Settings()


def is_production() -> bool:
    return settings.ENVIRONMENT.strip().lower() in ("production", "prod")


def _valid_key(hex_key: str) -> bool:
    try:
        return len(bytes.fromhex(hex_key)) == 32
    except ValueError:
        return False


def check_settings() -> list[str]:  # problems that must stop a production start
    problems = []
    if settings.DEMO_MODE:
        problems.append("DEMO_MODE is on (anyone could sign in as any Google user and payments are fake)")
    if settings.JWT_SECRET in UNSAFE_JWT_SECRETS or len(settings.JWT_SECRET) < 32:
        problems.append("JWT_SECRET is missing or weak (use 32+ random characters)")
    if settings.STORAGE_MASTER_KEY_HEX in UNSAFE_STORAGE_KEYS or not _valid_key(settings.STORAGE_MASTER_KEY_HEX):
        problems.append("STORAGE_MASTER_KEY_HEX is missing, the public sample key, or not 64 hex characters")
    if settings.ENABLE_LEGACY_API:
        problems.append("ENABLE_LEGACY_API is on")
    return problems


import logging  # noqa: E402
import secrets  # noqa: E402
_log = logging.getLogger(__name__)
if is_production():
    _problems = check_settings()
    if _problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(_problems))
else:
    if settings.JWT_SECRET in UNSAFE_JWT_SECRETS or len(settings.JWT_SECRET) < 32:
        _log.warning("JWT_SECRET is missing or weak; using a random key. Sign-ins reset on restart. Set JWT_SECRET in .env.")
        settings.JWT_SECRET = secrets.token_urlsafe(48)
    if settings.STORAGE_MASTER_KEY_HEX in UNSAFE_STORAGE_KEYS or not _valid_key(settings.STORAGE_MASTER_KEY_HEX):
        _log.warning("STORAGE_MASTER_KEY_HEX is not set; using the public development key. Never do this with real documents.")
        settings.STORAGE_MASTER_KEY_HEX = DEV_STORAGE_KEY
