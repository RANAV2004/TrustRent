"""Email notifications for things people would otherwise miss (new messages, visits, deposits, decisions).

Sent in the background after the response, so a slow or failing mail server never delays or breaks a
request. Chat emails are throttled per conversation so a busy chat doesn't flood the inbox.
"""
import asyncio
import logging
from datetime import timedelta
from app.core.config import settings
from app.core.ratelimit import NOTIFY_PER_THREAD, NOTIFY_ADMINS
from app.models.marketplace import utcnow
from app.models.user import User

log = logging.getLogger("trustrent.notify")
_tasks: set[asyncio.Task] = set()
ACTIVE_WINDOW = timedelta(minutes=2)  # someone reading the chat right now doesn't need an email


def link(path: str | None) -> str | None:
    return f"{settings.APP_URL.rstrip('/')}{path}" if settings.APP_URL and path else None


def _wanted(user: User | None) -> bool:
    return bool(settings.EMAIL_NOTIFICATIONS and user and user.email and not user.is_demo
                and not user.deleted_at and not user.banned_at)


def recently_active(last_read) -> bool:
    return bool(last_read and last_read > utcnow() - ACTIVE_WINDOW)


async def _deliver(to: str, subject: str, lines: list[str]) -> None:
    from app.services.mailer import EmailError, _simple_email, email_enabled, send_message_email
    if not email_enabled():
        return
    try:
        await send_message_email(_simple_email(to, subject, lines))
    except EmailError:
        log.warning("Couldn't email %r", subject)


def _schedule(to: str, subject: str, lines: list[str]) -> None:
    try:
        task = asyncio.get_running_loop().create_task(_deliver(to, subject, lines))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    except RuntimeError:  # no event loop (scripts): skip quietly
        pass


def notify(user: User | None, subject: str, lines: list[str], path: str | None = None, thread: str | None = None) -> None:
    """Email one person. `thread` limits it to one email per conversation every 15 minutes."""
    if not _wanted(user):
        return
    if thread and not NOTIFY_PER_THREAD.allow(f"{user.id}:{thread}"):
        return
    from app.services.accounts import display_name
    url = link(path)
    body = [f"Hello {display_name(user)},", *lines]
    if url:
        body.append(f"Open TrustRent: {url}")
    body.append("You're getting this email because you have a TrustRent account.")
    _schedule(user.email, subject, body)


def notify_admins(kind: str, subject: str, lines: list[str], path: str | None = None) -> None:
    """Tell the admins something needs them (a new verification request). At most hourly per kind."""
    if not settings.EMAIL_NOTIFICATIONS or not NOTIFY_ADMINS.allow(kind):
        return
    url = link(path)
    for to in settings.ADMIN_EMAILS:
        _schedule(to, f"[TrustRent admin] {subject}", [*lines, *([f"Open the admin console: {url}"] if url else [])])


def rupees(amount: int | None) -> str:
    return f"Rs {amount or 0:,}"


def snippet(text: str | None, limit: int = 200) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= limit else t[: limit - 1] + "…"
