from sqlalchemy.ext.asyncio import AsyncSession
from app.core.observability import client_ip
from app.models.marketplace import utcnow
from app.models.trust import AuditLog
from app.models.user import User


def audit(db: AsyncSession, actor: User | None, action: str, target_type: str | None = None, target_id: str | None = None,
          **details) -> None:
    """Add an audit row to the current transaction; it is saved together with the action it describes."""
    label = "system" if actor is None else (actor.email or actor.id)
    db.add(AuditLog(at=utcnow(), actor_id=actor.id if actor else None, actor_label=label, action=action,
                    target_type=target_type, target_id=str(target_id) if target_id else None,
                    details={k: v for k, v in details.items() if v is not None}, ip=client_ip.get()))
