from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from app.core.database import Base
from app.models.marketplace import utcnow


class PasswordReset(Base):  # one-time reset link
    __tablename__ = "password_resets"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class DisputeNote(Base):  # statement in a dispute
    __tablename__ = "dispute_notes"
    id = Column(String(36), primary_key=True)
    deposit_id = Column(String(16), ForeignKey("deposits.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(8), nullable=False)  # tenant | owner | admin
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Agreement(Base):  # rent agreement for a deposit
    __tablename__ = "agreements"
    id = Column(String(36), primary_key=True)
    deposit_id = Column(String(16), ForeignKey("deposits.id"), nullable=False, unique=True, index=True)
    terms = Column(JSON, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(66), nullable=False)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    record_tx = Column(String(66), nullable=True)
    esign_provider = Column(String(16), nullable=True)  # Aadhaar eSign through a provider
    esign_doc_id = Column(String(64), nullable=True, index=True)
    esign_status = Column(String(12), nullable=True)  # requested | completed | failed
    esign_links = Column(JSON, nullable=True)
    esigned_pdf_path = Column(String(500), nullable=True)
    esigned_pdf_iv = Column(String(64), nullable=True)
    esigned_hash = Column(String(66), nullable=True)
    esigned_at = Column(DateTime, nullable=True)
    estamp_state = Column(String(40), nullable=True)  # e-stamp paper bought by the owner
    estamp_number = Column(String(40), nullable=True)
    estamp_amount = Column(Integer, nullable=True)
    estamp_file_path = Column(String(500), nullable=True)
    estamp_file_iv = Column(String(64), nullable=True)
    estamp_file_hash = Column(String(66), nullable=True)


class AgreementSignature(Base):
    __tablename__ = "agreement_signatures"
    id = Column(String(36), primary_key=True)
    agreement_id = Column(String(36), ForeignKey("agreements.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(8), nullable=False)  # tenant | owner
    typed_name = Column(String(160), nullable=False)
    text_hash = Column(String(66), nullable=False)  # the exact text that was signed
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(300), nullable=True)
    signed_at = Column(DateTime, default=utcnow)
    record_tx = Column(String(66), nullable=True)


class SavedSearch(Base):  # alert for new homes
    __tablename__ = "saved_searches"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    filters = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    last_alert_at = Column(DateTime, nullable=True)
