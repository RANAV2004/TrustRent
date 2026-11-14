import io
import warnings
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.errors import field_error

Image.MAX_IMAGE_PIXELS = 40_000_000  # ~40 MP; bigger images are refused (decompression bombs)
MAX_SIDE = 2000


async def read_limited(upload: UploadFile, max_bytes: int, field: str, label: str = "The file") -> bytes:
    """Read at most max_bytes; refuse anything bigger without loading it all."""
    chunks, total = [], 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise field_error(f"{label} is larger than {max_bytes // (1024 * 1024)} MB.", field)
        chunks.append(chunk)
    return b"".join(chunks)


def clean_image(raw: bytes, field: str = "file", max_side: int = MAX_SIDE) -> bytes:
    """Decode, re-encode as JPEG: drops EXIF/GPS and anything that isn't a real picture."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(raw))
            img.load()
            img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning, ValueError):
        raise field_error("That file isn't a photo we can read. Use JPG, PNG or WebP.", field) from None
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def is_document(raw: bytes) -> bool:  # ID / property proofs: PDF or a real image only
    if raw.startswith(b"%PDF-"):
        return True
    if raw[:3] == b"\xff\xd8\xff" or raw.startswith(b"\x89PNG\r\n\x1a\n") or (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"):
        return True
    return False
