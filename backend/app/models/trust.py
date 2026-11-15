from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.core.database import Base
from app.models.marketplace import utcnow


class AuditLog(Base):  # who did what, for admins
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime, default=utcnow, index=True)
    actor_id = Column(String(36), nullable=True, index=True)  # None = system job
    actor_label = Column(String(255), nullable=False)
    action = Column(String(40), nullable=False, index=True)
    target_type = Column(String(20), nullable=True)
    target_id = Column(String(64), nullable=True, index=True)
    details = Column(JSON, default=dict)
    ip = Column(String(64), nullable=True)


class ListingReport(Base):  # "report this listing"
    __tablename__ = "listing_reports"
    id = Column(String(36), primary_key=True)
    listing_id = Column(String(16), ForeignKey("listings.id"), nullable=False, index=True)
    reporter_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    reason = Column(String(20), nullable=False)
    details = Column(Text, nullable=True)
    status = Column(String(10), default="open", index=True)  # open | actioned | dismissed
    created_at = Column(DateTime, default=utcnow)
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution = Column(Text, nullable=True)


class Review(Base):  # after a settled deposit, each side reviews the other once
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("deposit_id", "author_id", name="ux_review_once"),)
    id = Column(String(36), primary_key=True)
    deposit_id = Column(String(16), ForeignKey("deposits.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    subject_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    direction = Column(String(16), nullable=False)  # tenant_to_owner | owner_to_tenant
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    hidden_at = Column(DateTime, nullable=True)
    hidden_reason = Column(String(300), nullable=True)


class ChecklistMark(Base):  # a side finished its room-by-room photos for a stage
    __tablename__ = "checklist_marks"
    __table_args__ = (UniqueConstraint("deposit_id", "side", "stage", name="ux_checklist_once"),)
    id = Column(String(36), primary_key=True)
    deposit_id = Column(String(16), ForeignKey("deposits.id"), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    stage = Column(String(10), nullable=False)
    rooms = Column(JSON, default=list)
    completed_at = Column(DateTime, default=utcnow)
    record_tx = Column(String(66), nullable=True)


class PayoutAccount(Base):  # where an owner gets paid (bank details encrypted)
    __tablename__ = "payout_accounts"
    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    holder_name = Column(String(120), nullable=False)
    ifsc = Column(String(11), nullable=False)
    account_last4 = Column(String(4), nullable=False)
    account_enc = Column(Text, nullable=False)
    pan_last4 = Column(String(4), nullable=False)
    pan_enc = Column(Text, nullable=False)
    linked_account_id = Column(String(40), nullable=True)  # Razorpay Route acc_...
    status = Column(String(10), default="submitted")  # submitted | active | rejected
    note = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class RentInvoice(Base):  # one month of rent from a signed agreement
    __tablename__ = "rent_invoices"
    __table_args__ = (UniqueConstraint("deposit_id", "period", name="ux_rent_period"),)
    id = Column(String(36), primary_key=True)
    deposit_id = Column(String(16), ForeignKey("deposits.id"), nullable=False, index=True)
    agreement_id = Column(String(36), nullable=False)
    period = Column(String(7), nullable=False)  # YYYY-MM
    amount = Column(Integer, nullable=False)
    due_date = Column(String(10), nullable=False)
    status = Column(String(10), default="due")  # due | paid | cancelled
    method = Column(String(10), nullable=True)  # online | offline
    payment_id = Column(String(36), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    receipt_no = Column(String(24), nullable=True, unique=True)
    payout_status = Column(String(12), nullable=True)  # transferred | due | paid | none
    payout_ref = Column(String(40), nullable=True)
    reminded_at = Column(DateTime, nullable=True)
    overdue_notified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class DigilockerSession(Base):  # PKCE verifier kept server-side
    __tablename__ = "digilocker_sessions"
    state = Column(String(64), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    verifier = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
