import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from app.core.database import Base
class EvidenceType(str, enum.Enum):  # evidence type
    MOVE_IN = "move_in"
    MOVE_OUT = "move_out"
    DISPUTE_CLAIM = "dispute_claim"
class Evidence(Base):  # evidence
    __tablename__ = "evidences"
    id = Column(String(36), primary_key=True, index=True)
    tenancy_id = Column(String(36), ForeignKey("tenancies.id"), nullable=False)
    submitted_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    evidence_type = Column(Enum(EvidenceType), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(66), nullable=False)
    manifest_hash = Column(String(66), nullable=True)
    storage_path = Column(String(500), nullable=False)
    encryption_iv = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
