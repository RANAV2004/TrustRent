from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from app.core.database import Base
from app.models.marketplace import utcnow


class SupportTicket(Base):  # a query raised from Help & support
    __tablename__ = "support_tickets"
    id = Column(String(20), primary_key=True)  # the ticket number, e.g. TKT-261126-4F7K
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(40), nullable=False)
    subject = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    page_url = Column(String(300), nullable=True)  # where the problem happened, if the user says
    status = Column(String(12), default="open", index=True)  # open / in_progress / closed
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(String(36), nullable=True)
    resolution = Column(Text, nullable=True)


class TicketMessage(Base):  # the ticket's timeline: replies and status changes
    __tablename__ = "ticket_messages"
    id = Column(String(36), primary_key=True)
    ticket_id = Column(String(20), ForeignKey("support_tickets.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    from_support = Column(Boolean, default=False)
    kind = Column(String(10), default="message")  # message / status
    status_to = Column(String(12), nullable=True)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class TicketAttachment(Base):  # a screenshot, stored encrypted
    __tablename__ = "ticket_attachments"
    id = Column(String(36), primary_key=True)
    ticket_id = Column(String(20), ForeignKey("support_tickets.id"), nullable=False, index=True)
    message_id = Column(String(36), ForeignKey("ticket_messages.id"), nullable=True)  # empty: added with the ticket
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    file_name = Column(String(120), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_iv = Column(String(64), nullable=False)
    file_hash = Column(String(66), nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)
