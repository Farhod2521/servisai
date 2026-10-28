"""Yuklanadigan ommaviy rasmlar: mahsulot logolari va e’lon (yangilik) rasmlari.

Fayllar `media/<papka>` ga saqlanadi va `/api/media/<papka>/...` orqali ommaga beriladi
(cheklar `media/receipts` da — ular ochiq EMAS).
"""

import uuid
from pathlib import Path

from .config import settings

# Ommaga ochiq papkalar (main.py da mount qilinadi)
PUBLIC_FOLDERS = ("logos", "banners")
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


def media_dir(folder: str) -> Path:
    assert folder in PUBLIC_FOLDERS
    path = Path(settings.media_dir) / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def logos_dir() -> Path:
    return media_dir("logos")


def detect_format(content: bytes) -> str | None:
    """Fayl turini kengaytmaga emas, ichidagi baytlarga qarab aniqlaydi."""
    return next((ext for ext, check in _SIGNATURES.items() if check(content)), None)


def save_image(content: bytes, folder: str) -> str:
    if not content:
        raise LogoError(422, "Fayl bo‘sh")
    if len(content) > MAX_LOGO_SIZE:
        raise LogoError(413, "Rasm hajmi 2 MB dan oshmasligi kerak")
    ext = detect_format(content)
    if ext is None:
        raise LogoError(422, "Rasm PNG, JPG yoki WEBP bo‘lishi kerak")
    name = f"{uuid.uuid4().hex}.{ext}"
    (media_dir(folder) / name).write_bytes(content)
    return f"/api/media/{folder}/{name}"


def delete_image(url: str | None, folder: str) -> None:
    """Faqat o‘zimiz yuklagan faylni o‘chiradi (yo‘l tashqariga chiqmasligi tekshiriladi)."""
    prefix = f"/api/media/{folder}/"
    if not url or not url.startswith(prefix):
        return
    name = url[len(prefix):]
    if "/" in name or "\\" in name or name.startswith("."):
        return
    (media_dir(folder) / name).unlink(missing_ok=True)


def save_logo(content: bytes) -> str:
    return save_image(content, "logos")


def delete_logo(url: str | None) -> None:
    delete_image(url, "logos")
