import os
import tempfile
_tmp = tempfile.mkdtemp(prefix="trustrent-test-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["STORAGE_LOCAL_DIR"] = os.path.join(_tmp, "storage")
os.environ["MEDIA_DIR"] = os.path.join(_tmp, "media")
os.environ["DEBUG"] = "false"
os.environ["DEMO_ADMIN_PASSWORD"] = "test-admin-password"
os.environ["DEMO_MODE"] = "true"  # most tests exercise demo flows; production-mode tests switch it off
os.environ["ENABLE_LEGACY_API"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # rate-limit tests switch it on
os.environ["RUN_BACKGROUND_JOBS"] = "false"
os.environ["ENVIRONMENT"] = "test"
import pytest  # noqa: E402
from app.core.database import engine, Base  # noqa: E402
import app.models  # noqa: E402,F401
@pytest.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    from app.core.config import settings
    from tests.mailbox import OUTBOX
    sent = OUTBOX
    sent.clear()
    async def fake_send(to, code, minutes=10):
        sent[to] = code
    monkeypatch.setattr(settings, "SMTP_USER", "trustrent.otp@gmail.com")
    monkeypatch.setattr(settings, "SMTP_APP_PASSWORD", "test-app-password")
    monkeypatch.setattr("app.api.v1.accounts.send_code_email", fake_send)
    return sent
@pytest.fixture(autouse=True)
async def mail(monkeypatch):  # every email (notifications, reset links) lands here instead of SMTP
    from app.services import notify
    sent: list[dict] = []
    async def fake_send(to, subject, text, html=None):
        sent.append({"to": to, "subject": subject, "text": text})
    monkeypatch.setattr("app.services.mailer.send_email", fake_send)
    monkeypatch.setattr("app.api.v1.accounts.send_email", fake_send)
    yield sent
    await notify.drain()


@pytest.fixture(autouse=True)
def fresh_limits():
    from app.core.ratelimit import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac