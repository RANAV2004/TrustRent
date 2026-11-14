import asyncio
import html
import logging
from app.core.config import settings
from app.models.user import User
from app.services import mailer

log = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


def wants_email(user: User | None) -> bool:
    if not user or not user.email or user.deleted_at or user.banned_at or user.is_demo:
        return False
    return user.email_notifications is not False


def _render(name: str, lines: list[str], link: str | None) -> tuple[str, str]:
    url = f"{settings.FRONTEND_URL.rstrip('/')}{link}" if link else None
    text = f"Hi {name},\n\n" + "\n\n".join(lines)
    if url:
        text += f"\n\nOpen TrustRent: {url}"
    text += "\n\nYou can turn these emails off on your TrustRent profile page."
    body = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    button = (f'<p><a href="{html.escape(url)}" style="background:#0D5B4C;color:#fff;padding:10px 16px;'
              f'border-radius:8px;text-decoration:none">Open TrustRent</a></p>') if url else ""
    page = (f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:auto;color:#1b1b1b">'
            f'<p style="font-size:18px;font-weight:bold">TrustRent</p><p>Hi {html.escape(name)},</p>{body}{button}'
            f'<p style="color:#6b6b6b;font-size:13px">You can turn these emails off on your TrustRent profile page.</p></div>')
    return text, page


async def _deliver(to: str, subject: str, text: str, page: str) -> None:
    try:
        await mailer.send_email(to, subject, text, page)
    except Exception as e:  # noqa: BLE001 - a failed notification never breaks the action
        log.warning("Notification to %s failed: %s", to, e)


def notify(user: User | None, subject: str, lines: list[str], link: str | None = None, *, force: bool = False) -> None:
    """Email a user in the background. force=True ignores the opt-out (security emails)."""
    if not user or not user.email or user.deleted_at or user.is_demo:
        return
    if not force and not wants_email(user):
        return
    if not mailer.email_enabled():
        log.info("Email off; would notify %s: %s", user.email, subject)
        return
    name = user.first_name or (user.name or "").split(" ")[0] or "there"
    text, page = _render(name, lines, link)
    task = asyncio.get_running_loop().create_task(_deliver(user.email, f"TrustRent: {subject}", text, page))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:  # tests and shutdown: wait for queued emails
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
