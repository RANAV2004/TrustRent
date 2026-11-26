from app.core.database import Base
from app.models.user import User, UserRole
from app.models.marketplace import Conversation, EmailVerification, IdentitySubmission, Listing, Message, OwnerApplication
from app.models.deposits import ConditionPhoto, Deposit, LedgerEntry, Payment
from app.models.legal import Agreement, AgreementShare, LawyerApplication, LegalCase, LegalMessage
from app.models.support import SupportTicket, TicketAttachment, TicketMessage
__all__ = [
    "Base", "User", "UserRole",
    "Listing", "OwnerApplication", "EmailVerification", "IdentitySubmission", "Deposit", "LedgerEntry", "Payment", "ConditionPhoto", "Conversation", "Message",
    "LawyerApplication", "LegalCase", "LegalMessage", "Agreement", "AgreementShare",
    "SupportTicket", "TicketMessage", "TicketAttachment",
]
for _table in Base.metadata.tables.values():
    for _fk in _table.foreign_key_constraints:
        _fk.deferrable, _fk.initially = True, "DEFERRED"
