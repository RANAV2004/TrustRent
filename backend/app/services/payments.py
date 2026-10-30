import hashlib
import hmac
import httpx
from app.core.config import settings
API = "https://api.razorpay.com/v1"
class PaymentError(Exception):
    pass
def razorpay_enabled() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
def _auth():
    return (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
async def create_order(amount_inr: int, receipt: str, notes: dict) -> dict:
    body = {"amount": amount_inr * 100, "currency": "INR", "receipt": receipt[:40], "notes": notes}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(f"{API}/orders", json=body, auth=_auth())
    except httpx.HTTPError as e:
        raise PaymentError("Could not reach the payment gateway. Try again.") from e
    if res.status_code >= 400:
        raise PaymentError("The payment gateway refused the order. Check the Razorpay keys.")
    return res.json()
def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
async def refund(payment_id: str, amount_inr: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(f"{API}/payments/{payment_id}/refund", json={"amount": amount_inr * 100}, auth=_auth())
    except httpx.HTTPError as e:
        raise PaymentError("Could not reach the payment gateway for the refund.") from e
    if res.status_code >= 400:
        raise PaymentError("The refund was refused by the payment gateway.")
    return res.json()
