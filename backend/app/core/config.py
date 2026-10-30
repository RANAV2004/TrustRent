from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
_BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env", Path(".env"))
class Settings(BaseSettings):  # settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    JWT_SECRET: str = "super-secret-jwt-key-change-in-production-min-32-chars"
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
    STORAGE_MASTER_KEY_HEX: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
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
settings = Settings()
