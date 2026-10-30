import os
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings
from app.services.storage.base import StorageProvider
from app.services.hash_service import HashService
class IPFSStorageProvider(StorageProvider):
    def __init__(self, master_key_hex: str = None, api_key: str = None, secret_key: str = None):
        key_hex = master_key_hex or settings.STORAGE_MASTER_KEY_HEX
        self.master_key = bytes.fromhex(key_hex[:64])
        self.aesgcm = AESGCM(self.master_key)
        self.api_key = api_key
        self.secret_key = secret_key
    def store(self, key: str, data: bytes) -> Tuple[str, str]:
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, data, None)
        simulated_cid = f"Qm{HashService.hash_bytes(ciphertext)[2:46]}"
        return simulated_cid, nonce.hex()
    def retrieve(self, storage_reference: str, iv_hex: str) -> bytes:
        raise NotImplementedError("IPFS Gateway retrieval requires active IPFS cluster / Pinata endpoint")
