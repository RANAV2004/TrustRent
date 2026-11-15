import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


def _box() -> AESGCM:
    return AESGCM(bytes.fromhex(settings.STORAGE_MASTER_KEY_HEX[:64]))


def seal(text: str) -> str:  # nonce || ciphertext, hex
    nonce = os.urandom(12)
    return (nonce + _box().encrypt(nonce, text.encode(), b"trustrent-field")).hex()


def open_sealed(blob: str) -> str:
    raw = bytes.fromhex(blob)
    return _box().decrypt(raw[:12], raw[12:], b"trustrent-field").decode()
