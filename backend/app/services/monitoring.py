"""Error alerts: Sentry (when SENTRY_DSN is set) plus throttled alert emails to the admins.

Nothing here may ever break a request: every function swallows its own failures.
"""
import asyncio
import logging
import os
from app.core.config import settings
from app.core.ratelimit import ALERTS_PER_KIND, ALERTS_TOTAL

log = logging.getLogger("trustrent.alerts")
_tasks: set[asyncio.Task] = set()


def release() -> str:
    return (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT") or "dev")[:12]


def _scrub(event, _hint):  # never send passwords, tokens, documents or personal details to Sentry
    request = event.get("request") or {}
    request.pop("data", None)
    request.pop("cookies", None)
    request.pop("query_string", None)
    headers = request.get("headers") or {}
    for key in list(headers):
        if key.lower() in ("authorization", "cookie", "x-razorpay-signature"):
            headers[key] = "[removed]"
    event.pop("user", None)
    return event


def init_sentry() -> bool:
    if not settings.SENTRY_DSN:
        return False
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, release=release(),
                        traces_sample_rate=0.0, before_send=_scrub)
        return True
    except Exception:  # noqa: BLE001
        log.exception("Sentry could not start")
        return False


def report_to_sentry(message: str, level: str = "error") -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_message(message, level=level)
    except Exception:  # noqa: BLE001
        pass


def alert_recipients() -> list[str]:
    return settings.ERROR_ALERT_EMAILS or settings.ADMIN_EMAILS


async def _send_alert(subject: str, body: str) -> None:
    from app.services.mailer import EmailError, _simple_email, email_enabled, send_message_email
    if not email_enabled():
        return
    for to in alert_recipients():
        try:
            await send_message_email(_simple_email(to, subject, [body]))
        except EmailError:
            pass


def alert(kind: str, subject: str, body: str) -> None:
    """Email the admins about a problem, at most once per `kind` every 30 minutes."""
    try:
        log.error("%s: %s", subject, body)
        if not settings.ERROR_ALERTS or not ALERTS_PER_KIND.allow(kind) or not ALERTS_TOTAL.allow("all"):
            return
        text = (f"{body}\n\nServer: {settings.ENVIRONMENT}, version {release()}.\n"
                "You get at most one email per problem every 30 minutes. Check the server logs"
                + (" and Sentry" if settings.SENTRY_DSN else "") + " for details.")
        task = asyncio.get_running_loop().create_task(_send_alert(f"[TrustRent alert] {subject}", text))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    except Exception:  # noqa: BLE001
        pass
