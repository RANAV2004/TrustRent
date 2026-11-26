"""Authenticator-app codes (TOTP, RFC 6238) for admin two-step sign-in, plus one-time recovery codes."""
import base64
import hashlib
import hmac
import io
import os
import secrets
import struct
import time
from urllib.parse import quote
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

PERIOD = 30
DIGITS = 6
ISSUER = "TrustRent"
RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret_b32: str) -> bytes:
    return base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))


def code_at(secret_b32: str, step: int, digits: int = DIGITS) -> str:
    mac = hmac.new(_key(secret_b32), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** digits).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // PERIOD)


def verify(secret_b32: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """Returns the matching time step, or None. Allows one step of clock drift; a code works only once."""
    code = "".join(c for c in code if c.isdigit())
    if len(code) != DIGITS:
        return None
    step = current_step(now)
    for s in (step - 1, step, step + 1):
        if (last_step is None or s > last_step) and hmac.compare_digest(code_at(secret_b32, s), code):
            return s
    return None


def otpauth_uri(secret_b32: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer={ISSUER}&digits={DIGITS}&period={PERIOD}"


def qr_svg(uri: str) -> str:
    import segno
    out = io.BytesIO()
    segno.make(uri, error="m").save(out, kind="svg", scale=5, border=2, dark="#0d5b4c")
    return out.getvalue().decode()


# The secret is stored encrypted, so a database leak alone doesn't give away admins' codes.
def _aes() -> AESGCM:
    return AESGCM(hashlib.sha256(b"trustrent-totp|" + bytes.fromhex(settings.STORAGE_MASTER_KEY_HEX[:64])).digest())


def seal(secret_b32: str) -> str:
    nonce = os.urandom(12)
    return (nonce + _aes().encrypt(nonce, secret_b32.encode(), None)).hex()


def unseal(sealed: str) -> str:
    raw = bytes.fromhex(sealed)
    return _aes().decrypt(raw[:12], raw[12:], None).decode()


def new_recovery_codes(n: int = 8) -> list[str]:
    def one() -> str:
        s = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(8))
        return f"{s[:4]}-{s[4:]}"
    return [one() for _ in range(n)]


def normalise_recovery(code: str) -> str:
    s = "".join(c for c in code.lower() if c.isalnum())
    return f"{s[:4]}-{s[4:]}" if len(s) == 8 else ""
