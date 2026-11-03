"""External integrations (Razorpay, SMTP, Polygon, Google) with the network faked out, plus app startup."""
import hashlib
import hmac
import io
import smtplib
from types import SimpleNamespace
import httpx
import uuid
import pytest
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.services import chain, mailer, payments
from tests.test_condition_photos import paid_deposit
from tests.test_live_features import admin_headers, verified_tenant_with_visit
from tests.test_marketplace import owner_with_listing, signup
_RealAsyncClient = httpx.AsyncClient
def fake_http(monkeypatch, module, handler):
    """Route every httpx.AsyncClient made inside `module` through `handler`."""
    def make(**kw):
        return _RealAsyncClient(transport=httpx.MockTransport(handler), **kw)
    monkeypatch.setattr(module.httpx, "AsyncClient", make)
class Calls(list):
    enable = None
@pytest.fixture
def razorpay(monkeypatch):
    calls = Calls()
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.path == "/v1/orders":
            return httpx.Response(200, json={"id": f"order_{uuid.uuid4().hex[:12]}"})
        if req.url.path.endswith("/refund"):
            return httpx.Response(200, json={"id": "rfnd_1"})
        return httpx.Response(404)
    fake_http(monkeypatch, payments, handler)
    def enable():
        monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_key")
        monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp_secret")
    calls.enable = enable
    return calls
def sign(order_id: str, payment_id: str) -> str:
    return hmac.new(b"rzp_secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
async def test_razorpay_premium_order_and_signature_check(client, razorpay):
    _, uh = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("pan.jpg", io.BytesIO(b"x"), "image/jpeg")})
    razorpay.enable()
    cfg = (await client.get("/api/v1/config")).json()
    assert cfg["payments"] == "razorpay" and cfg["razorpayKeyId"] == "rzp_test_key"
    order = (await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "month"})).json()
    assert order["provider"] == "razorpay" and order["orderId"].startswith("order_") and order["amount"] == 299
    sent = razorpay[0]
    assert sent.headers["authorization"].startswith("Basic ") and b'"amount":29900' in sent.content
    bad = await client.post("/api/v1/payments/verify", headers=uh,
                            json={"orderId": order["orderId"], "paymentId": "pay_1", "signature": "forged"})
    assert bad.status_code == 400
    ok = await client.post("/api/v1/payments/verify", headers=uh,
                           json={"orderId": order["orderId"], "paymentId": "pay_1", "signature": sign(order["orderId"], "pay_1")})
    assert ok.status_code == 200 and ok.json()["payment"]["status"] == "paid"
    assert ok.json()["user"]["premium"]["planId"] == "month"
    again = await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": order["orderId"]})
    assert again.status_code == 200
    missing = await client.post("/api/v1/payments/verify", headers=uh, json={"orderId": "order_nope"})
    assert missing.status_code == 404
async def test_razorpay_deposit_refunded_on_settlement(client, razorpay):
    owner, oh, listing = await owner_with_listing(client)
    _, th = await verified_tenant_with_visit(client, listing, oh)
    razorpay.enable()
    order = (await client.post("/api/v1/payments/order", headers=th, json={"purpose": "deposit", "listingId": listing["id"]})).json()
    paid = (await client.post("/api/v1/payments/verify", headers=th, json={
        "orderId": order["orderId"], "paymentId": "pay_dep", "signature": sign(order["orderId"], "pay_dep")})).json()
    dep_id = paid["depositId"]
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 0})
    done = (await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})).json()
    assert done["status"] == "settled" and done["refundRef"] == "rfnd_1"
    refund = razorpay[-1]
    assert refund.url.path == "/v1/payments/pay_dep/refund" and b'"amount":3400000' in refund.content
async def test_razorpay_gateway_failures(client, monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "k")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "s")
    fake_http(monkeypatch, payments, lambda req: httpx.Response(401))
    with pytest.raises(payments.PaymentError, match="refused the order"):
        await payments.create_order(100, "r", {})
    with pytest.raises(payments.PaymentError, match="refund was refused"):
        await payments.refund("pay_1", 100)
    def down(req):
        raise httpx.ConnectError("offline")
    fake_http(monkeypatch, payments, down)
    with pytest.raises(payments.PaymentError, match="Could not reach"):
        await payments.create_order(100, "r", {})
    with pytest.raises(payments.PaymentError, match="Could not reach"):
        await payments.refund("pay_1", 100)
    _, uh = await signup(client)
    await client.post("/api/v1/users/me/identity", headers=uh, data={"docType": "PAN card"},
                      files={"file": ("pan.jpg", io.BytesIO(b"x"), "image/jpeg")})
    res = await client.post("/api/v1/payments/order", headers=uh, json={"purpose": "premium", "planId": "week"})
    assert res.status_code == 502
async def test_refund_failure_keeps_deposit_open(client, monkeypatch):
    dep_id, th, oh = await paid_deposit(client)
    from app.core.database import AsyncSessionLocal
    from app.models.deposits import Deposit, Payment
    async with AsyncSessionLocal() as db:
        d = await db.get(Deposit, dep_id)
        pay = await db.get(Payment, d.payment_id)
        pay.provider, pay.payment_id = "razorpay", "pay_x"
        await db.commit()
    async def broken(payment_id, amount):
        raise payments.PaymentError("The refund was refused by the payment gateway.")
    monkeypatch.setattr(payments, "refund", broken)
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 0})
    res = await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})
    assert res.status_code == 502
    assert (await client.get(f"/api/v1/deposits/{dep_id}", headers=th)).json()["status"] == "settlement_proposed"
async def test_google_sign_in_with_id_token(client, monkeypatch):
    from app.api.v1 import accounts
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-123")
    def handler(req):
        if req.url.params["id_token"] == "good":
            return httpx.Response(200, json={"aud": "client-123", "email_verified": "true", "email": "Meera@Gmail.com",
                                             "given_name": "Meera", "family_name": "Iyer"})
        return httpx.Response(400, json={"error": "invalid_token"})
    fake_http(monkeypatch, accounts, handler)
    ok = await client.post("/api/v1/auth/google", json={"credential": "good"})
    assert ok.status_code == 200
    user = ok.json()["user"]
    assert user["email"] == "meera@gmail.com" and user["firstName"] == "Meera" and user["provider"] == "google"
    same = await client.post("/api/v1/auth/google", json={"credential": "good"})
    assert same.json()["user"]["id"] == user["id"]
    assert (await client.post("/api/v1/auth/google", json={"credential": "bad"})).status_code == 401
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert (await client.post("/api/v1/auth/google", json={"email": "not-an-email"})).status_code == 400
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert (await client.post("/api/v1/auth/google", json={"email": "a@b.com"})).status_code == 501
class FakeSMTP:
    sent: list = []
    fail: Exception | None = None
    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def starttls(self, context):
        pass
    def login(self, user, password):
        if FakeSMTP.fail:
            raise FakeSMTP.fail
    def send_message(self, msg):
        FakeSMTP.sent.append(msg)
async def test_smtp_send_and_errors(monkeypatch):
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent, FakeSMTP.fail = [], None
    await mailer.send_code_email("riya@example.com", "654321", 10)
    assert FakeSMTP.sent[0]["To"] == "riya@example.com" and "654321" in FakeSMTP.sent[0]["Subject"]
    FakeSMTP.fail = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(mailer.EmailError, match="right now"):
        await mailer.send_code_email("riya@example.com", "1", 10)
    FakeSMTP.fail = OSError("network down")
    with pytest.raises(mailer.EmailError, match="in a minute"):
        await mailer.send_code_email("riya@example.com", "1", 10)
    FakeSMTP.fail = None
class FakeFn:
    def __init__(self, name, args, onchain):
        self.name, self.args, self.onchain = name, args, onchain
    def build_transaction(self, opts):
        return {"fn": self.name, **opts}
    def call(self):
        return self.onchain.get(self.args[0], (0, b"\0" * 32, 0, False, 0, 0, b"\0" * 32, 0))
class FakeChain:
    """Stands in for both the Web3 instance and the DepositRegistry contract."""
    def __init__(self, status=1):
        self.status, self.sent, self.onchain = status, [], {}
        self.eth = SimpleNamespace(
            account=SimpleNamespace(from_key=lambda k: SimpleNamespace(
                address="0x" + "a" * 40, sign_transaction=lambda tx: SimpleNamespace(raw_transaction=b"raw"))),
            get_transaction_count=lambda addr, block: 7,
            send_raw_transaction=self._send,
            wait_for_transaction_receipt=lambda h, timeout: SimpleNamespace(status=self.status),
        )
        outer = self
        class Functions:
            def __getattr__(self, name):
                def fn(*args):
                    if name == "recordDeposit":
                        outer.onchain[args[0]] = (args[1], args[2], 1, False, 0, 0, b"\0" * 32, 0)
                    return FakeFn(name, args, outer.onchain)
                return fn
        self.functions = Functions()
    def _send(self, raw):
        self.sent.append(raw)
        return bytes([len(self.sent)]) * 32
@pytest.fixture
def polygon(monkeypatch):
    monkeypatch.setattr(settings, "DEPOSIT_REGISTRY_ADDRESS", "0x" + "1" * 40)
    monkeypatch.setattr(settings, "CHAIN_SIGNER_PRIVATE_KEY", "0x" + "2" * 64)
    fake = FakeChain()
    monkeypatch.setattr(chain, "_contract", lambda: (fake, fake))
    return fake
async def test_deposit_recorded_and_settled_on_chain(client, polygon):
    cfg = (await client.get("/api/v1/config")).json()
    assert cfg["depositNetwork"] == "polygon-amoy" and cfg["explorerTxUrl"]
    dep_id, th, oh = await paid_deposit(client)
    dep = (await client.get(f"/api/v1/deposits/{dep_id}", headers=th)).json()
    assert dep["receipt"]["network"] == "polygon-amoy" and dep["receipt"]["recordTx"] == "0x" + "01" * 32
    assert dep["receipt"]["recordUrl"].endswith(dep["receipt"]["recordTx"])
    assert dep["verification"]["verified"] is True
    await client.post(f"/api/v1/deposits/{dep_id}/propose", headers=oh, json={"deducted": 0})
    done = (await client.post(f"/api/v1/deposits/{dep_id}/respond", headers=th, json={"accept": True})).json()
    assert done["receipt"]["settleTx"] == "0x" + "02" * 32 and len(polygon.sent) == 2
    polygon.onchain.clear()  # chain forgot it: read returns None, ledger check still applies
    assert (await client.get(f"/api/v1/deposits/{dep_id}", headers=th)).json()["verification"]["verified"] is True
async def test_chain_revert_and_read_errors(monkeypatch, polygon):
    polygon.status = 0
    with pytest.raises(RuntimeError, match="reverted"):
        await chain.record_deposit("DEP-1", 100, "0x" + "ab" * 32)
    def boom():
        raise ConnectionError("rpc down")
    monkeypatch.setattr(chain, "_contract", boom)
    assert await chain.read_deposit("DEP-1") is None
    monkeypatch.setattr(settings, "CHAIN_ID", 137)
    assert chain.network_name() == "chain-137"
def test_chain_contract_builds_without_network(monkeypatch):
    monkeypatch.setattr(settings, "DEPOSIT_REGISTRY_ADDRESS", "0x" + "1" * 40)
    w3, contract = chain._contract()
    assert contract.address.lower() == "0x" + "1" * 40
async def test_chain_disabled_is_a_no_op():
    assert await chain.settle_deposit("DEP-1", 0, 0, "0x00") is None
    assert await chain.read_deposit("DEP-1") is None
def test_tokens():
    from datetime import timedelta
    token = create_access_token("user-1", timedelta(minutes=5))
    assert decode_access_token(token)["sub"] == "user-1"
    assert decode_access_token("not-a-jwt") is None
    expired = create_access_token("user-1", timedelta(seconds=-1))
    assert decode_access_token(expired) is None
async def test_app_startup_seeds_and_cleans(monkeypatch):
    from app.main import app, lifespan, root
    assert root()["docs_url"] == "/docs"
    monkeypatch.setattr(settings, "SEED_SAMPLE_LISTINGS", True)
    async with lifespan(app):
        pass
    monkeypatch.setattr(settings, "SEED_SAMPLE_LISTINGS", False)
    async with lifespan(app):
        pass
async def test_admin_login_reset_by_env_password(client, monkeypatch):
    await admin_headers(client)
    monkeypatch.setattr(settings, "DEMO_ADMIN_PASSWORD", "a-new-password-1")
    ah = await admin_headers(client)
    assert (await client.get("/api/v1/admin/overview", headers=ah)).status_code == 200
