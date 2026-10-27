"""Mahsulot logolari: yuklash, tekshirish va saqlash.

Fayllar `media/logos` ga saqlanadi va `/api/media/logos/...` orqali ommaga beriladi
(cheklar `media/receipts` da — ular ochiq EMAS).
"""

import uuid
from pathlib import Path

from .config import settings

LOGO_URL_PREFIX = "/api/media/logos/"
MAX_LOGO_SIZE = 2 * 1024 * 1024

# SVG ataylab yo‘q: ichida skript bo‘lishi mumkin (XSS)
_SIGNATURES = {
    "png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "jpg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}


class LogoError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def logos_dir() -> Path:
    folder = Path(settings.media_dir) / "logos"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def detect_format(content: bytes) -> str | None:
    """Fayl turini kengaytmaga emas, ichidagi baytlarga qarab aniqlaydi."""
    return next((ext for ext, check in _SIGNATURES.items() if check(content)), None)


def save_logo(content: bytes) -> str:
    if not content:
        raise LogoError(422, "Fayl bo‘sh")
    if len(content) > MAX_LOGO_SIZE:
        raise LogoError(413, "Logo hajmi 2 MB dan oshmasligi kerak")
    ext = detect_format(content)
    if ext is None:
        raise LogoError(422, "Logo PNG, JPG yoki WEBP rasm bo‘lishi kerak")
    name = f"{uuid.uuid4().hex}.{ext}"
    (logos_dir() / name).write_bytes(content)
    return LOGO_URL_PREFIX + name


def delete_logo(url: str | None) -> None:
    """Faqat o‘zimiz yuklagan faylni o‘chiradi (yo‘l tashqariga chiqmasligi tekshiriladi)."""
    if not url or not url.startswith(LOGO_URL_PREFIX):
        return
    name = url[len(LOGO_URL_PREFIX):]
    if "/" in name or "\\" in name or name.startswith("."):
        return
    (logos_dir() / name).unlink(missing_ok=True)
