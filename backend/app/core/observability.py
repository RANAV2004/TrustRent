import json
import logging
import time
import uuid
from contextvars import ContextVar
from app.core.config import settings

request_id: ContextVar[str] = ContextVar("request_id", default="-")
log = logging.getLogger("trustrent.http")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
               "logger": record.name, "message": record.getMessage(), "request_id": request_id.get()}
        for key in ("method", "path", "status", "ms"):
            if hasattr(record, key):
                out[key] = getattr(record, key)
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out)


def setup_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_trustrent", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if settings.LOG_JSON else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root._trustrent = True  # type: ignore[attr-defined]
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, traces_sample_rate=0.1,
                            send_default_pii=False)
        except ImportError:
            logging.getLogger(__name__).warning("SENTRY_DSN is set but sentry-sdk isn't installed")


SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]


class GatewayMiddleware:  # ASGI: request id, body size cap, security headers, access log
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        rid = headers.get(b"x-request-id", b"").decode()[:64] or uuid.uuid4().hex[:16]
        token = request_id.set(rid)
        limit = settings.MAX_REQUEST_MB * 1024 * 1024
        start, status_holder = time.perf_counter(), {"code": 500}
        try:
            if int(headers.get(b"content-length", b"0") or 0) > limit:
                return await _too_large(send, rid)
        except ValueError:
            pass
        received = {"n": 0}

        async def limited_receive():
            message = await receive()
            if message["type"] == "http.request":
                received["n"] += len(message.get("body", b""))
                if received["n"] > limit:
                    raise BodyTooLarge()
            return message

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                extra = [(b"x-request-id", rid.encode())] + SECURITY_HEADERS
                have = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [h for h in extra if h[0] not in have]
                if settings.ENVIRONMENT.lower() in ("production", "prod"):
                    message["headers"].append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
            await send(message)

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except BodyTooLarge:
            await _too_large(send, rid)
        finally:
            path = scope.get("path", "")
            if path != "/api/v1/health":
                log.info("%s %s %s", scope.get("method"), path, status_holder["code"],
                         extra={"method": scope.get("method"), "path": path, "status": status_holder["code"],
                                "ms": round((time.perf_counter() - start) * 1000, 1)})
            request_id.reset(token)


class BodyTooLarge(Exception):
    pass


async def _too_large(send, rid: str):
    body = json.dumps({"detail": {"message": f"The upload is larger than {settings.MAX_REQUEST_MB} MB.", "field": None}}).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"x-request-id", rid.encode())]})
    await send({"type": "http.response.body", "body": body})
