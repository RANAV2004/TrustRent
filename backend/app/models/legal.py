from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from app.core.database import Base
from app.models.marketplace import utcnow

class LawyerApplication(Base):
    __tablename__ = "lawyer_applications"
    id = Column(String(12), primary_key=True)
    status = Column(String(12), default="pending", index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(24), nullable=False)
    city = Column(String(60), nullable=False)
    bar_council = Column(String(80), nullable=False)
    enrolment_no = Column(String(40), nullable=False, index=True)
    experience_years = Column(Integer, nullable=False)
    practice_areas = Column(JSON, default=list)
    languages = Column(JSON, default=list)
    office_address = Column(String(300), nullable=False)
    about = Column(Text, nullable=True)
    photo_path = Column(String(500), nullable=False)
    photo_iv = Column(String(64), nullable=False)
    id_doc_type = Column(String(60), nullable=False)
    id_file_name = Column(String(255), nullable=False)
    id_file_path = Column(String(500), nullable=False)
    id_file_iv = Column(String(64), nullable=False)
    id_file_hash = Column(String(66), nullable=False)
    enrolment_file_name = Column(String(255), nullable=False)
    enrolment_file_path = Column(String(500), nullable=False)
    enrolment_file_iv = Column(String(64), nullable=False)
    enrolment_file_hash = Column(String(66), nullable=False)
    public_photo = Column(String(500), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    submitted_at = Column(DateTime, default=utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(36), nullable=True)
    review_note = Column(String(500), nullable=True)

class LegalCase(Base):
    __tablename__ = "legal_cases"
    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    lawyer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    listing_id = Column(String(16), ForeignKey("listings.id"), nullable=True)
    subject = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)
    owner_last_read = Column(DateTime, nullable=True)
    lawyer_last_read = Column(DateTime, nullable=True)

class LegalMessage(Base):
    __tablename__ = "legal_messages"
    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("legal_cases.id"), nullable=False, index=True)
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

class Agreement(Base):
    __tablename__ = "agreements"
    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("legal_cases.id"), nullable=False, index=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(120), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_iv = Column(String(64), nullable=False)
    file_hash = Column(String(66), nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)

class AgreementShare(Base):
    __tablename__ = "agreement_shares"
    id = Column(String(36), primary_key=True)
    agreement_id = Column(String(36), ForeignKey("agreements.id"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    shared_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    shared_at = Column(DateTime, default=utcnow)
