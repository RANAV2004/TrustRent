from app.core.database import Base
from app.models.user import User, UserRole
from app.models.tenancy import Tenancy, TenancyStateEnum
from app.models.evidence import Evidence, EvidenceType
from app.models.marketplace import Conversation, EmailVerification, IdentitySubmission, Listing, Message, OwnerApplication
from app.models.deposits import ConditionPhoto, Deposit, LedgerEntry, Payment
__all__ = [
    "Base", "User", "UserRole", "Tenancy", "TenancyStateEnum", "Evidence", "EvidenceType",
    "Listing", "OwnerApplication", "EmailVerification", "IdentitySubmission", "Deposit", "LedgerEntry", "Payment", "ConditionPhoto", "Conversation", "Message",
]
for _table in Base.metadata.tables.values():  # checked at commit
    for _fk in _table.foreign_key_constraints:
        _fk.deferrable, _fk.initially = True, "DEFERRED"