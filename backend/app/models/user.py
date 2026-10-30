import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from app.core.database import Base
class UserRole(str, enum.Enum):  # roles
    TENANT = "tenant"
    LANDLORD = "landlord"
    ARBITRATOR = "arbitrator"
class User(Base):  # user
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.TENANT)
    wallet_address = Column(String(42), unique=True, index=True, nullable=True)
    is_verified = Column(Boolean, default=False)
    attestation_hash = Column(String(66), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    first_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    username = Column(String(20), unique=True, index=True, nullable=True)
    phone = Column(String(24), unique=True, index=True, nullable=True)
    country = Column(String(60), nullable=True)
    password_hash = Column(String(255), nullable=True)
    provider = Column(String(16), nullable=True)
    premium_plan = Column(String(20), nullable=True)
    premium_until = Column(DateTime, nullable=True)
    is_demo = Column(Boolean, default=False)
    banned_at = Column(DateTime, nullable=True)
    ban_reason = Column(String(300), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
