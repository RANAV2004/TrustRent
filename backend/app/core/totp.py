import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_at(secret: str, at: float | None = None) -> str:  # RFC 6238 TOTP, SHA-1, 6 digits
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int((time.time() if at is None else at) // STEP)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def verify(secret: str, code: str, at: float | None = None, drift: int = 1) -> int | None:
    """Returns the matching time step (to block reuse), or None."""
    code = (code or "").strip().replace(" ", "")
    if not secret or len(code) != DIGITS or not code.isdigit():
        return None
    now = time.time() if at is None else at
    for d in range(-drift, drift + 1):
        t = now + d * STEP
        if hmac.compare_digest(code_at(secret, t), code):
            return int(t // STEP)
    return None


def otpauth_url(secret: str, account: str, issuer: str = "TrustRent") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"
