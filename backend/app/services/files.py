from pathlib import Path
from app.core.config import settings
from app.services.storage.base import StorageProvider
from app.services.storage.local_encrypted import LocalEncryptedStorageProvider
def private_storage() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "s3":
        from app.services.storage.s3_encrypted import S3EncryptedStorageProvider
        return S3EncryptedStorageProvider()
    return LocalEncryptedStorageProvider()
def read_private(reference: str, iv_hex: str) -> bytes:
    if reference.startswith("s3://"):
        from app.services.storage.s3_encrypted import S3EncryptedStorageProvider
        return S3EncryptedStorageProvider().retrieve(reference, iv_hex)
    return LocalEncryptedStorageProvider().retrieve(reference, iv_hex)
def save_public(key: str, data: bytes, content_type: str) -> str:
    if settings.STORAGE_PROVIDER == "s3" and settings.S3_PUBLIC_BUCKET:
        from app.services.storage.s3_encrypted import s3_client
        s3_client().put_object(Bucket=settings.S3_PUBLIC_BUCKET, Key=key, Body=data, ContentType=content_type)
        return f"{settings.MEDIA_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    target = Path(settings.MEDIA_DIR) / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return key
