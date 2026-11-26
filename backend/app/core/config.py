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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60  # sign-ins last a week; a password reset ends them early
    DATABASE_URL: str = "sqlite+aiosqlite:///./trustrent.db"
    POLYGON_AMOY_RPC_URL: str = "https://rpc-amoy.polygon.technology"
    CHAIN_ID: int = 80002
    BACKEND_ATTESTER_PRIVATE_KEY: str = Field(default="")
    IDENTITY_REGISTRY_ADDRESS: str = Field(default="")
    ARBITRATOR_REGISTRY_ADDRESS: str = Field(default="")
    TENANCY_FACTORY_ADDRESS: str = Field(default="")
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_DIR: str = "./local_storage"
    STORAGE_MASTER_KEY_HEX: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # demo only
    DEMO_MODE: bool = True
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
    RAZORPAY_WEBHOOK_SECRET: str = ""
    ADMIN_TWO_FACTOR: str = "required"  # "required": admins must use an authenticator app; "optional"
    SENTRY_DSN: str = ""  # optional: error tracking at sentry.io
    ERROR_ALERTS: bool = True  # email the admins when the server hits an error
    ERROR_ALERT_EMAILS: List[str] = []  # who gets the alerts; empty means ADMIN_EMAILS
    EMAIL_NOTIFICATIONS: bool = True  # emails about new messages, visits, deposits and decisions
    APP_URL: str = ""  # the website address, used in emails, e.g. https://trustrent.in
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
PUBLIC_STORAGE_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
UNSAFE_JWT_SECRETS = {"", "super-secret-jwt-key-change-in-production-min-32-chars", "change-me", "change-this-to-a-long-random-secret-min-32-chars"}
settings = Settings()
if settings.JWT_SECRET in UNSAFE_JWT_SECRETS or len(settings.JWT_SECRET) < 32:  # never sign with a known key
    import logging
    import secrets
    logging.getLogger(__name__).warning("JWT_SECRET is missing or weak; using a random key. Sign-ins reset on restart. Set JWT_SECRET in .env.")
    settings.JWT_SECRET = secrets.token_urlsafe(48)
def _valid_key(hex_key: str) -> bool:
    try:
        return len(bytes.fromhex(hex_key)) == 32
    except ValueError:
        return False
def production_problems() -> list[str]:  # settings that must be fixed before real users arrive
    problems = []
    if not _valid_key(settings.STORAGE_MASTER_KEY_HEX):
        problems.append("STORAGE_MASTER_KEY_HEX must be 64 hex characters (32 bytes).")
    elif not settings.DEMO_MODE and settings.STORAGE_MASTER_KEY_HEX.lower() == PUBLIC_STORAGE_KEY:
        problems.append("STORAGE_MASTER_KEY_HEX is the public demo key: ID documents would be readable by anyone "
                        "with the code. Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
    return problems
def production_warnings() -> list[str]:
    if settings.DEMO_MODE:
        return []
    warnings = []
    if settings.DATABASE_URL.startswith("sqlite"):
        warnings.append("DATABASE_URL is SQLite. On Render/Railway the disk is wiped on every deploy: use PostgreSQL.")
    if settings.STORAGE_PROVIDER != "s3":
        warnings.append("STORAGE_PROVIDER is local. Uploaded documents and photos are lost when the server's disk is "
                        "wiped: use STORAGE_PROVIDER=s3.")
    if settings.RAZORPAY_KEY_ID and not settings.RAZORPAY_WEBHOOK_SECRET:
        warnings.append("RAZORPAY_WEBHOOK_SECRET is not set: payments where the customer closes the window before "
                        "returning will not be completed automatically.")
    if any("localhost" in o for o in settings.CORS_ORIGINS):
        warnings.append("CORS_ORIGINS still allows localhost.")
    return warnings
