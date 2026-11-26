import os
from pathlib import Path
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings
from app.services.storage.base import StorageProvider
class LocalEncryptedStorageProvider(StorageProvider):
    def __init__(self, storage_dir: str = None, master_key_hex: str = None):
        self.local_dir = Path(storage_dir or settings.STORAGE_LOCAL_DIR)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        key_hex = master_key_hex or settings.STORAGE_MASTER_KEY_HEX
        self.master_key = bytes.fromhex(key_hex[:64])
        self.aesgcm = AESGCM(self.master_key)
    def store(self, key: str, data: bytes) -> Tuple[str, str]:
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, data, None)
        target_path = self.local_dir / f"{key}.enc"
        with open(target_path, "wb") as f:
            f.write(ciphertext)
        return str(target_path), nonce.hex()
    def retrieve(self, storage_reference: str, iv_hex: str) -> bytes:
        nonce = bytes.fromhex(iv_hex)
        path = Path(storage_reference)
        if not path.exists():
            raise FileNotFoundError(f"Storage reference not found: {storage_reference}")
        with open(path, "rb") as f:
            ciphertext = f.read()
        return self.aesgcm.decrypt(nonce, ciphertext, None)
