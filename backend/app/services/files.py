from pathlib import Path
from urllib.parse import quote
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
def content_disposition(kind: str, name: str, fallback: str = "document") -> str:
    """A header that works for any file name: plain ASCII for old browsers, the real (e.g. Hindi) name for the rest."""
    clean = "".join(c for c in (name or "") if c.isalnum() or c in "._- ").strip()[:120] or fallback
    stem, dot, ext = clean.rpartition(".") if "." in clean else (clean, "", "")
    ascii_stem = "".join(c for c in stem if c.isascii()).strip(" .") or fallback
    ascii_ext = "".join(c for c in ext if c.isascii())
    ascii_name = ascii_stem + (f".{ascii_ext}" if dot and ascii_ext else "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(clean)}"
def delete_public(reference: str | None) -> None:
    """Remove a public file (e.g. a lawyer's photo) from the public bucket or the media folder."""
    if not reference:
        return
    try:
        base = settings.MEDIA_PUBLIC_BASE_URL.rstrip("/")
        if reference.startswith(("http://", "https://")):
            if settings.STORAGE_PROVIDER == "s3" and settings.S3_PUBLIC_BUCKET and base and reference.startswith(base + "/"):
                from app.services.storage.s3_encrypted import s3_client
                s3_client().delete_object(Bucket=settings.S3_PUBLIC_BUCKET, Key=reference[len(base) + 1:])
            return
        target = (Path(settings.MEDIA_DIR) / reference).resolve()
        if Path(settings.MEDIA_DIR).resolve() in target.parents and target.is_file():
            target.unlink()
    except Exception:  # noqa: BLE001 - a leftover file must not stop the account deletion
        import logging
        logging.getLogger(__name__).exception("Couldn't delete public file %s", reference)
def save_public(key: str, data: bytes, content_type: str) -> str:
    if settings.STORAGE_PROVIDER == "s3" and settings.S3_PUBLIC_BUCKET:
        from app.services.storage.s3_encrypted import s3_client
        s3_client().put_object(Bucket=settings.S3_PUBLIC_BUCKET, Key=key, Body=data, ContentType=content_type)
        return f"{settings.MEDIA_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    target = Path(settings.MEDIA_DIR) / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return key
