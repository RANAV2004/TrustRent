import os
from typing import Tuple
import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings
from app.services.storage.base import StorageProvider
class S3EncryptedStorageProvider(StorageProvider):
    def __init__(self):
        if not settings.S3_PRIVATE_BUCKET:
            raise RuntimeError("STORAGE_PROVIDER=s3 needs S3_PRIVATE_BUCKET and S3 credentials.")
        self.bucket = settings.S3_PRIVATE_BUCKET
        self.client = s3_client()
        self.aesgcm = AESGCM(bytes.fromhex(settings.STORAGE_MASTER_KEY_HEX[:64]))
    def store(self, key: str, data: bytes) -> Tuple[str, str]:
        nonce = os.urandom(12)
        object_key = f"private/{key}.enc"
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=self.aesgcm.encrypt(nonce, data, None))
        return f"s3://{self.bucket}/{object_key}", nonce.hex()
    def retrieve(self, storage_reference: str, iv_hex: str) -> bytes:
        bucket, _, key = storage_reference.removeprefix("s3://").partition("/")
        body = self.client.get_object(Bucket=bucket, Key=key)["Body"].read()
        return self.aesgcm.decrypt(bytes.fromhex(iv_hex), body, None)
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        region_name=settings.S3_REGION or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
    )
