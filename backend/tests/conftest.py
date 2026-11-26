import os
import tempfile
_tmp = tempfile.mkdtemp(prefix="trustrent-test-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["STORAGE_LOCAL_DIR"] = os.path.join(_tmp, "storage")
os.environ["MEDIA_DIR"] = os.path.join(_tmp, "media")
os.environ["DEBUG"] = "false"
os.environ["DEMO_ADMIN_PASSWORD"] = "test-admin-password"
os.environ["ADMIN_TWO_FACTOR"] = "optional"  # test_two_factor.py switches it on
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
    async def fake_reset(to, code, minutes=10):
        sent[f"reset:{to}"] = code
    monkeypatch.setattr("app.api.v1.accounts.send_code_email", fake_send)
    monkeypatch.setattr("app.api.v1.accounts.send_reset_email", fake_reset)
    from tests.mailbox import MAILS
    MAILS.clear()
    async def fake_message(msg):  # notifications, alerts, lawyer emails: never reach a real mail server
        MAILS.append({"to": msg["To"], "subject": msg["Subject"], "body": msg.get_content()})
    monkeypatch.setattr("app.services.mailer.send_message_email", fake_message)
    return sent
@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.core.ratelimit import ALL_LIMITERS
    for limiter in ALL_LIMITERS:
        limiter.reset()
    yield
@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac