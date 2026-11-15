"""What we send to outside providers (Razorpay Route, Digio, DigiLocker), checked with a fake HTTP transport."""
import base64
import json
import httpx
import pytest
from app.core.config import settings


@pytest.fixture
def transport(monkeypatch):
    calls, replies = [], {}
    real = httpx.AsyncClient

    def handler(request: httpx.Request):
        calls.append(request)
        for key, resp in replies.items():
            if key in str(request.url):
                return resp(request) if callable(resp) else resp
        return httpx.Response(404)

    def client(*a, **k):
        k.pop("transport", None)
        return real(*a, transport=httpx.MockTransport(handler), **k)
    monkeypatch.setattr(httpx, "AsyncClient", client)
    return calls, replies


async def test_route_transfers(transport, monkeypatch):
    from app.services import payments
    calls, replies = transport
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_k")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "s3cret")
    replies["/payments/pay_1/transfers"] = httpx.Response(200, json={"entity": "collection", "count": 1, "items": [{"id": "trf_A"}]})
    replies["/v1/transfers"] = httpx.Response(200, json={"id": "trf_B", "entity": "transfer"})
    assert await payments.transfer_from_payment("pay_1", "acc_X", 1500, {"rent": "r1"}) == "trf_A"
    body = json.loads(calls[-1].content)
    assert body["transfers"][0] == {"account": "acc_X", "amount": 150000, "currency": "INR", "notes": {"rent": "r1"}}
    assert calls[-1].headers["authorization"] == "Basic " + base64.b64encode(b"rzp_test_k:s3cret").decode()
    assert await payments.direct_transfer("acc_X", 200, {}) == "trf_B"
    assert json.loads(calls[-1].content)["amount"] == 20000
    replies["/v1/transfers"] = httpx.Response(400, json={"error": {}})
    with pytest.raises(payments.PaymentError):
        await payments.direct_transfer("acc_X", 200, {})


async def test_digio_requests(transport, monkeypatch):
    from app.services import esign
    calls, replies = transport
    monkeypatch.setattr(settings, "DIGIO_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "DIGIO_CLIENT_SECRET", "csec")
    replies["/uploadpdf"] = httpx.Response(200, json={"id": "DID1"})
    replies["/document/download"] = httpx.Response(200, content=b"%PDF-1.7 signed")
    replies["/document/DID1"] = httpx.Response(200, json={"signing_parties": [{"status": "signed"}, {"status": "signed"}]})
    doc = await esign.create_request(b"%PDF-1.4", "a.pdf", [{"identifier": "o@x.in", "name": "O"}, {"identifier": "t@x.in", "name": "T"}])
    body = json.loads(calls[-1].content)
    assert doc == "DID1" and body["signers"][0]["sign_type"] == "aadhaar" and base64.b64decode(body["file_data"]) == b"%PDF-1.4"
    assert esign.is_complete(await esign.fetch("DID1")) is True
    assert esign.is_complete({"signing_parties": [{"status": "signed"}, {"status": "requested"}]}) is False
    assert (await esign.download("DID1")).startswith(b"%PDF")
    assert calls[-1].url.params["document_id"] == "DID1"
    replies["/uploadpdf"] = httpx.Response(401)
    with pytest.raises(esign.EsignError):
        await esign.create_request(b"%PDF", "a.pdf", [])


async def test_digilocker_token_exchange(transport, monkeypatch):
    from app.services import digilocker
    calls, replies = transport
    monkeypatch.setattr(settings, "DIGILOCKER_CLIENT_ID", "dl")
    monkeypatch.setattr(settings, "DIGILOCKER_CLIENT_SECRET", "dls")
    monkeypatch.setattr(settings, "DIGILOCKER_REDIRECT_URI", "https://app.example/identity/digilocker")
    replies["/oauth2/1/token"] = httpx.Response(200, json={"access_token": "AT"})
    replies["/xml/eaadhaar"] = httpx.Response(200, content=b"<x/>")
    assert await digilocker.fetch_eaadhaar("CODE", "VERIFIER") == b"<x/>"
    form = dict(x.split("=", 1) for x in calls[0].content.decode().split("&"))
    assert form["code_verifier"] == "VERIFIER" and form["grant_type"] == "authorization_code"
    assert calls[1].headers["authorization"] == "Bearer AT"
    replies["/oauth2/1/token"] = httpx.Response(400, json={})
    with pytest.raises(digilocker.DigilockerError):
        await digilocker.fetch_eaadhaar("CODE", "VERIFIER")
