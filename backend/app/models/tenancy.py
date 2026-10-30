import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Enum
from app.core.database import Base
class TenancyStateEnum(str, enum.Enum):  # tenancy state
    DRAFTED = "Drafted"
    SIGNED = "Signed"
    ACTIVE = "Active"
    MOVE_OUT = "MoveOut"
    DISPUTED = "Disputed"
    REFUNDED = "Refunded"
class Tenancy(Base):  # tenancy
    __tablename__ = "tenancies"
    id = Column(String(36), primary_key=True, index=True)
    vault_address = Column(String(42), unique=True, index=True, nullable=True)
    landlord_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    property_address = Column(String(500), nullable=False)
    monthly_rent = Column(Numeric(precision=18, scale=2), nullable=False)
    deposit_amount = Column(Numeric(precision=18, scale=2), nullable=False)
    deduction_cap = Column(Numeric(precision=18, scale=2), nullable=False)
    claim_window_days = Column(Integer, default=7)
    lease_hash = Column(String(66), nullable=False)
    lease_storage_cid = Column(String(255), nullable=True)
    state = Column(Enum(TenancyStateEnum), default=TenancyStateEnum.DRAFTED)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
