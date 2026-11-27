import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.services import monitoring

@pytest.fixture
def alerts(monkeypatch):
    sent = []

    async def fake_send(msg):
        sent.append({"to": msg["To"], "subject": msg["Subject"], "body": msg.get_content()})
    monkeypatch.setattr("app.services.mailer.send_message_email", fake_send)
    return sent

async def settle():
    for _ in range(5):
        await asyncio.sleep(0)

async def test_health_reports_database(client, alerts):
    ok = await client.get("/api/v1/health")
    assert ok.status_code == 200 and ok.json()["status"] == "healthy" and ok.json()["database"] == "ok"

    class Broken:
        async def execute(self, *_a, **_k):
            raise ConnectionError("database is down")

    async def broken_db():
        yield Broken()
    app.dependency_overrides[get_db] = broken_db
    try:
        down = await client.get("/api/v1/health")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert down.status_code == 503 and down.json()["database"] == "down"
    await settle()
    assert alerts and alerts[0]["subject"] == "[TrustRent alert] Database unreachable"

async def test_server_errors_alert_admins_once(alerts, monkeypatch):
    def crash():
        raise RuntimeError("boom")
    monkeypatch.setattr("app.services.payments.razorpay_enabled", crash)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(3):
            res = await ac.get("/api/v1/config")
            assert res.status_code == 500
            assert "Something went wrong on our side" in res.json()["detail"]["message"]
            assert "boom" not in res.text
    await settle()
    mine = [a for a in alerts if "GET /api/v1/config" in a["subject"]]
    assert len(mine) == len(settings.ADMIN_EMAILS)
    assert "RuntimeError" in mine[0]["body"] and mine[0]["to"] == settings.ADMIN_EMAILS[0]

async def test_alerts_can_go_elsewhere_or_be_switched_off(alerts, monkeypatch):
    monkeypatch.setattr(settings, "ERROR_ALERT_EMAILS", ["ops@example.com"])
    monitoring.alert("kind-a", "Test", "body")
    await settle()
    assert [a["to"] for a in alerts] == ["ops@example.com"]
    monkeypatch.setattr(settings, "ERROR_ALERTS", False)
    monitoring.alert("kind-b", "Test", "body")
    await settle()
    assert len(alerts) == 1

async def test_browser_error_reports(client, caplog):
    body = {"message": "TypeError: x is undefined", "url": "https://trustrent.in/deposits?token=secret", "stack": "at a()"}
    res = await client.post("/api/v1/client-errors", json=body)
    assert res.status_code == 204
    assert "Browser error on /deposits: TypeError: x is undefined" in caplog.text and "secret" not in caplog.text
    for _ in range(25):
        assert (await client.post("/api/v1/client-errors", json=body)).status_code == 204
    assert caplog.text.count("Browser error on") == 20
    assert (await client.post("/api/v1/client-errors", json={"message": "x" * 600})).status_code == 422

def test_sentry_events_are_scrubbed():
    event = {"request": {"data": {"password": "p"}, "cookies": "c", "query_string": "q",
                         "headers": {"Authorization": "Bearer t", "User-Agent": "ua"}}, "user": {"email": "a@b.c"}}
    out = monitoring._scrub(event, None)
    assert "data" not in out["request"] and "cookies" not in out["request"] and "user" not in out
    assert out["request"]["headers"] == {"Authorization": "[removed]", "User-Agent": "ua"}
    assert monitoring.init_sentry() is False
