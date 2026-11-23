"""Hisobot boti: do'kondagi hamma hodisa (savdo + FOYDA, to'lov, xato, yangi mijoz) alohida bot orqali adminlarga tushadi.

Token faqat muhit o'zgaruvchisida (ALERT_BOT_TOKEN) — kodga yoki GitHub'ga yozilmaydi.
Har bir admin hisobot botida bir marta /start bosishi kerak (Telegram qoidasi: bot birinchi yozmaydi).
/start bosmagan odamga xabar asosiy bot orqali boradi va qanday ulanish aytiladi — hech narsa yo'qolmaydi.
ALERT_BOT_TOKEN berilmasa — hammasi eskicha (asosiy bot orqali).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings

log = logging.getLogger("uzshop.alerts")

_bot: Bot | None = None
STATE: dict = {"username": "", "last_hint": None, "sent": 0, "failed": 0}
HINT_EVERY = 6 * 3600


def enabled() -> bool:
    return bool(settings.alert_bot_token)


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(settings.alert_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bot


async def close() -> None:
    global _bot
    if _bot is not None:
        try:
            await _bot.session.close()
        finally:
            _bot = None


def recipients(owner_only: bool = False) -> list[int]:
    ids = [settings.owner_id] if owner_only else [settings.owner_id, *settings.admins]
    return [i for i in dict.fromkeys(ids) if i]


def _extra_chat():
    v = (settings.alert_chat_id or "").strip()
    if not v:
        return None
    return int(v) if v.lstrip("-").isdigit() else v


async def username() -> str:
    if not STATE["username"] and enabled():
        try:
            STATE["username"] = (await get_bot().get_me()).username or ""
        except Exception:  # noqa: BLE001
            pass
    return STATE["username"]


async def broadcast(main_bot, text: str, *, owner_only: bool = False) -> int:
    """Adminlarga xabar. Hisobot boti yoqilgan bo'lsa — shu bot orqali; /start bosmaganlarga asosiy bot orqali.
    Yuborilganlar soni qaytadi."""
    ids = recipients(owner_only)
    sent = 0
    if not enabled():
        for cid in ids:
            try:
                await main_bot.send_message(cid, text)
                sent += 1
            except Exception:  # noqa: BLE001 — admin botni bloklagan bo'lishi mumkin
                pass
        return sent

    ab = get_bot()
    failed: list[int] = []
    for cid in ids:
        try:
            await ab.send_message(cid, text)
            sent += 1
        except Exception as ex:  # noqa: BLE001
            failed.append(cid)
            log.info("Hisobot boti %s ga yubora olmadi: %s", cid, type(ex).__name__)
    extra = _extra_chat()
    if extra is not None:
        try:
            await ab.send_message(extra, text)
            sent += 1
        except Exception as ex:  # noqa: BLE001
            log.warning("Hisobot guruhiga yuborilmadi (%s): %s", extra, type(ex).__name__)
    STATE["sent"] += sent
    STATE["failed"] += len(failed)

    if failed:        # /start bosmagan adminlar: xabar asosiy bot orqali ketadi + qanday ulanish
        uname = await username()
        hint = ""
        if uname and (STATE["last_hint"] is None or time.monotonic() - STATE["last_hint"] > HINT_EVERY):
            STATE["last_hint"] = time.monotonic()
            hint = f"\n\n👉 Hisobot botini ulang: https://t.me/{uname} → «Start» ni bosing. Shundan keyin xabarlar o'sha botga keladi."
        for cid in failed:
            try:
                await main_bot.send_message(cid, text + hint)
                sent += 1
            except Exception:  # noqa: BLE001
                pass
    return sent


async def new_user(user) -> None:
    """Yangi mijoz haqida qisqa xabar (faqat hisobot boti yoqilgan bo'lsa). Fon vazifasi sifatida chaqiriladi."""
    if not enabled():
        return
    import html
    try:
        who = f"@{user.username}" if user.username else "username yo'q"
        ab = get_bot()
        text = (f"🆕 <b>Yangi mijoz</b>\n👤 {html.escape(user.full_name or '—')} · {html.escape(who)} · <code>{user.tg_id}</code>")
        for cid in recipients():
            try:
                await ab.send_message(cid, text)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001 — hisobot xatosi mijozni to'xtatmasin
        log.debug("new_user alert xatosi", exc_info=True)


def schedule_new_user(user) -> None:
    if enabled():
        try:
            asyncio.get_running_loop().create_task(new_user(user))
        except RuntimeError:
            pass


async def hello(main_bot) -> None:
    """Bot ishga tushganda: hisobot boti ulanganini bildiradi (kim /start bosmagan — shu zahoti bilinadi)."""
    if enabled():
        stamp = (datetime.utcnow() + timedelta(hours=5)).strftime("%d.%m %H:%M")
        await broadcast(main_bot, f"▶️ <b>Hisobot boti ulandi</b> · {stamp}\nSavdolar, foyda, to'lovlar va xatolar shu yerga keladi.")
