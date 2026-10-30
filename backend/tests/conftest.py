import os
import tempfile
_tmp = tempfile.mkdtemp(prefix="trustrent-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["STORAGE_LOCAL_DIR"] = os.path.join(_tmp, "storage")
os.environ["MEDIA_DIR"] = os.path.join(_tmp, "media")
os.environ["DEBUG"] = "false"
import pytest  # noqa: E402
from app.core.database import engine, Base  # noqa: E402
import app.models  # noqa: E402,F401
@pytest.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

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
@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
