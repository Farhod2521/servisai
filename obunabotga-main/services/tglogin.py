"""Telegram sessiyasini botning o'zida olish (telefon/kompyuter/fayl kerak emas).

Oqim (faqat bot egasi uchun, handlers/sessiya.py): telefon → Telegram yuborgan kod → (bo'lsa) 2FA parol.
Natija — Telethon StringSession: bazadagi `settings` jadvaliga («tg_session») saqlanadi va CardXabar ko'prigi qayta yoqiladi.
Session akkaunt kaliti: logga yozilmaydi, zaxira (backup) fayliga tushmaydi.

MUHIM: Telegram login kodini Telegram chatida odatdagidek yozsangiz, uni o'zi bekor qiladi. Shuning uchun kod raqamlar orasiga
bo'sh joy qo'yib yoziladi («1 2 3 4 5»); bu yerda bo'sh joy va chiziqchalar olib tashlanadi.
"""
from __future__ import annotations

import logging
import re
import time

from config import settings
from services import runtime

log = logging.getLogger("uzshop.tglogin")

PENDING_TTL = 600
_PENDING: dict[int, dict] = {}      # owner_id → {"client", "phone", "hash", "t"}
_LAST_PHONE: dict[int, str] = {}    # owner_id → oxirgi telefon (kod eskirsa avtomatik yangi kod so'rash uchun)


class LoginError(Exception):
    """Foydalanuvchiga ko'rsatiladigan (o'zbekcha) xato."""


def configured() -> bool:
    return bool(settings.tg_api_id and settings.tg_api_hash)


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not 9 <= len(digits) <= 15:
        raise LoginError("Telefon raqam noto'g'ri. Masalan: +998901234567")
    return "+" + digits


def normalize_code(raw: str) -> str:
    code = re.sub(r"\D", "", raw or "")
    if not 4 <= len(code) <= 8:
        raise LoginError("Kod 5 xonali raqam bo'ladi. Raqamlar orasiga bo'sh joy qo'yib yozing: 1 2 3 4 5")
    return code


def _make_client():
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    return TelegramClient(StringSession(), settings.tg_api_id, settings.tg_api_hash)


async def _drop(owner_id: int) -> None:
    st = _PENDING.pop(owner_id, None)
    if st:
        try:
            await st["client"].disconnect()
        except Exception:  # noqa: BLE001
            pass


def _err(ex: Exception) -> LoginError:
    name = type(ex).__name__
    if name == "FloodWaitError":
        sec = int(getattr(ex, "seconds", 0) or 0)
        return LoginError(f"Telegram vaqtincha to'xtatdi: {sec // 60 + 1} daqiqadan keyin qayta urinib ko'ring.")
    table = {
        "PhoneNumberInvalidError": "Telefon raqam noto'g'ri.",
        "PhoneNumberBannedError": "Bu raqam Telegram tomonidan bloklangan.",
        "PhoneNumberFloodError": "Bu raqamga juda ko'p kod so'raldi. Birozdan keyin urinib ko'ring.",
        "ApiIdInvalidError": "TG_API_ID / TG_API_HASH noto'g'ri (my.telegram.org dan olingan bo'lishi kerak).",
        "PhoneCodeInvalidError": "Kod noto'g'ri. Qayta yozing (raqamlar orasiga bo'sh joy bilan).",
        "PhoneCodeExpiredError": "Kod eskirgan. /sessiya ni qaytadan boshlang — yangi kod keladi.",
        "PasswordHashInvalidError": "2FA parol noto'g'ri. Qayta yozing.",
    }
    return LoginError(table.get(name) or f"Telegram xatosi: {name}")


async def begin(owner_id: int, phone_raw: str) -> str:
    """Telefonga kod yuboradi. Qaytadi: normallashtirilgan telefon."""
    if not configured():
        raise LoginError("Render → Environment'da TG_API_ID va TG_API_HASH yo'q (my.telegram.org dan oling).")
    phone = normalize_phone(phone_raw)
    await _drop(owner_id)
    client = _make_client()
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
    except Exception as ex:  # noqa: BLE001
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        log.warning("Kod yuborilmadi: %s", type(ex).__name__)
        raise _err(ex) from ex
    _PENDING[owner_id] = {"client": client, "phone": phone, "hash": sent.phone_code_hash, "t": time.monotonic()}
    _LAST_PHONE[owner_id] = phone
    return phone


def _state(owner_id: int) -> dict:
    st = _PENDING.get(owner_id)
    if not st or time.monotonic() - st["t"] > PENDING_TTL:
        raise LoginError("Vaqt tugadi. /sessiya ni qaytadan boshlang.")
    return st


async def _finish(owner_id: int) -> None:
    st = _PENDING[owner_id]
    session = st["client"].session.save()
    await runtime.set_value("tg_session", session)
    await _drop(owner_id)
    log.info("Telegram session saqlandi (bazaga)")


async def submit_code(owner_id: int, raw: str) -> str:
    """Kodni tekshiradi. Qaytadi: 'ok' (tayyor) yoki 'password' (2FA parol kerak)."""
    st = _state(owner_id)
    code = normalize_code(raw)
    try:
        await st["client"].sign_in(phone=st["phone"], code=code, phone_code_hash=st["hash"])
    except Exception as ex:  # noqa: BLE001
        if type(ex).__name__ == "SessionPasswordNeededError":
            return "password"
        if type(ex).__name__ == "PhoneCodeExpiredError":
            await _drop(owner_id)
        raise _err(ex) from ex
    await _finish(owner_id)
    return "ok"


async def submit_password(owner_id: int, password: str) -> str:
    st = _state(owner_id)
    try:
        await st["client"].sign_in(password=password)
    except Exception as ex:  # noqa: BLE001
        raise _err(ex) from ex
    await _finish(owner_id)
    return "ok"


async def resend(owner_id: int) -> bool:
    """Kod eskirgan/bekor bo'lsa — oxirgi telefonga YANGI kod yuboradi. True — yuborildi."""
    phone = _LAST_PHONE.get(owner_id)
    if not phone:
        return False
    try:
        await begin(owner_id, phone)
    except LoginError:
        return False
    return True


async def cancel(owner_id: int) -> None:
    await _drop(owner_id)


async def logout_saved() -> None:
    """Saqlangan sessiyani bazadan o'chiradi (Render'dagi TG_SESSION qolsa — u ishlatiladi)."""
    await runtime.set_value("tg_session", None)


# ─────────────────────────── Brauzer orqali kirish (kod Telegram chatiga yozilmaydi) ───────────────────────────
# Telegram login kodini Telegram CHATIDA yozilsa — o'zi bekor qiladi («Kod eskirgan»). Shuning uchun asosiy usul: botdan bir martalik
# havola → brauzerdagi sahifada telefon, kod va parol yoziladi (chatga hech narsa yozilmaydi).

import secrets

LINK_TTL = 900
LINK_MAX_TRIES = 25
_LINKS: dict[str, dict] = {}     # token → {"owner", "exp", "tries"}


def new_link(owner_id: int) -> str:
    now = time.monotonic()
    for k in [k for k, v in _LINKS.items() if v["exp"] < now or v["owner"] == owner_id]:
        _LINKS.pop(k, None)
    token = secrets.token_urlsafe(24)
    _LINKS[token] = {"owner": owner_id, "exp": now + LINK_TTL, "tries": 0}
    return token


def link_owner(token: str, *, count: bool = False) -> int | None:
    """Havola yaroqli bo'lsa — owner ID; aks holda None. count=True — urinish hisoblanadi."""
    item = None
    for k, v in _LINKS.items():
        if secrets.compare_digest(k.encode(), (token or "").encode()):
            item = v
    if not item or item["exp"] < time.monotonic() or item["tries"] >= LINK_MAX_TRIES:
        return None
    if count:
        item["tries"] += 1
    return item["owner"]


def drop_link(token: str) -> None:
    _LINKS.pop(token, None)
