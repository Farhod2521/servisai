"""CardXabarBot ko'prigi: Telegram user-session (Telethon) bank kirim xabarlarini o'qiydi.

Faqat CARD_SOURCES ro'yxatidagi aniq usernamelardan kelgan PRIVATE kiruvchi xabarlar qabul qilinadi.
TG_SESSION (StringSession) maxfiy: kodga, logga va hisobotga yozilmaydi. Ulanish uzilsa avtomatik qayta ulanadi;
xato bo'lsa faqat ownerga xabar boradi (bot yiqilmaydi).
"""
from __future__ import annotations

import asyncio
import logging

from config import settings
from services import paynotify, runtime

log = logging.getLogger("uzshop.cardbridge")

ALERT_AFTER_FAILS = 3
NOTICE_EVERY = 120          # tushunilmagan / mos kelmagan kirim haqida ownerga eng ko'pi bilan 2 daqiqada bir xabar

CLIENT = None      # ulangan Telethon mijozi (bot egasining akkaunti) — kanalga premium emojili post yuborish uchun ham ishlatiladi

# Diagnostika (admin → 💳 To'lov tizimi → 🔎 Diagnostika)
STATE: dict = {"started": None, "connected": False, "connected_at": None, "events": 0, "last_event": None,
               "last_kind": "", "last_error": "", "last_notice": 0.0}


def enabled() -> bool:
    return bool(settings.tg_api_id and settings.tg_api_hash and runtime.tg_session() and settings.card_source_list)


async def on_message(bot, *, sender_username: str | None, is_private: bool, chat_id: int, msg_id: int, text: str,
                     any_bot: bool = False) -> bool:
    """Bitta kiruvchi xabar. True — qayta ishlandi. Begona manba / guruh xabarlari e'tiborsiz qoldiriladi."""
    if not is_private:
        return False
    src = (sender_username or "").lstrip("@").lower()
    if not (src and src in settings.card_source_list) and not any_bot:
        return False               # begona manba (any_bot — Business orqali kelgan BOT xabari: odam soxta yoza olmaydi)
    src = src or "bot"
    import time
    from services import topup
    STATE["events"] += 1
    STATE["last_event"] = topup.utcnow()
    try:
        out = await paynotify.process_incoming(bot, src, f"{chat_id}:{msg_id}", text or "", "card")
        STATE["last_kind"] = f"{out.kind}" + (f" {out.parsed.amount}" if out.parsed and out.parsed.amount else
                                                (f" ({out.parsed.reason})" if out.parsed and out.parsed.reason else ""))
        # Tushunilmagan yoki mos buyurtma topilmagan kirim — owner bilib tursin (xabar formati o'zgargan bo'lishi mumkin)
        noisy = (out.kind == "ignored" and out.parsed is not None and out.parsed.kind == "unknown") or out.kind == "unmatched"
        if noisy and time.monotonic() - STATE["last_notice"] > NOTICE_EVERY:
            STATE["last_notice"] = time.monotonic()
            import html
            why = (f"summa {out.parsed.amount:,} so'm, lekin shu summali faol buyurtma yo'q".replace(",", " ")
                   if out.kind == "unmatched" and out.parsed and out.parsed.amount else
                   f"xabar tushunilmadi ({html.escape(out.parsed.reason if out.parsed else '?')})")
            await paynotify.notify_owner(bot, f"ℹ️ <b>CardXabarBot xabari</b>: {why}\n\n<i>{html.escape((text or '')[:300])}</i>")
    except Exception as ex:  # noqa: BLE001 — bitta xabar xatosi ko'prikni to'xtatmasin
        STATE["last_error"] = type(ex).__name__
        log.exception("CardXabar xabarini qayta ishlashda xato")
    return True


async def sweeper() -> None:
    """Har daqiqada muddati o'tgan buyurtmalarni expired qiladi (noyob summalar bo'shaydi)."""
    from database.db import SessionMaker
    from services import topup
    while True:
        try:
            async with SessionMaker() as s:
                await topup.sweep_expired(s)
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001
            log.warning("Buyurtmalarni tozalashda xato: %s", type(ex).__name__)
        await asyncio.sleep(60)


TASK: asyncio.Task | None = None


def start(bot) -> asyncio.Task:
    """Ko'prikni fon vazifasi sifatida ishga tushiradi; eskisi ishlayotgan bo'lsa — to'xtatib, yangisini (yangi session bilan) yoqadi."""
    global TASK
    if TASK is not None and not TASK.done():
        TASK.cancel()
    TASK = asyncio.create_task(run(bot))
    return TASK


async def run(bot) -> None:
    """Fon vazifasi: ulanadi, tinglaydi, uzilsa qayta ulanadi."""
    from services import topup as _t
    STATE["started"] = _t.utcnow()
    if not enabled():
        log.info("CardXabar ko'prigi o'chiq (TG_API_ID / TG_API_HASH / TG_SESSION yoki CARD_SOURCES yo'q)")
        return
    try:
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession
    except ImportError:
        log.error("telethon o'rnatilmagan — CardXabar ko'prigi ishlamaydi")
        return

    fails, alerted, delay = 0, False, 5
    while True:
        client = TelegramClient(StringSession(runtime.tg_session()), settings.tg_api_id, settings.tg_api_hash,
                                auto_reconnect=True, connection_retries=5, retry_delay=3)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await paynotify.notify_owner(bot, "⚠️ CardXabar ko'prigi: Telegram session yaroqsiz (TG_SESSION'ni qayta yarating). "
                                                  "Avto-to'lov faqat Payme/Click/SMS orqali ishlaydi.")
                log.error("TG_SESSION avtorizatsiyadan o'tmadi — ko'prik to'xtatildi")
                return

            @client.on(events.NewMessage(incoming=True))
            async def _handler(ev):  # noqa: ANN001
                sender = await ev.get_sender()
                await on_message(
                    bot, sender_username=getattr(sender, "username", None), is_private=bool(ev.is_private),
                    chat_id=int(ev.chat_id or 0), msg_id=int(ev.id), text=ev.raw_text or "")

            global CLIENT
            CLIENT = client
            log.info("CardXabar ko'prigi ulandi: %s", ", ".join(settings.card_source_list))
            first = STATE["connected_at"] is None
            from services import topup
            STATE["connected"], STATE["connected_at"], STATE["last_error"] = True, topup.utcnow(), ""
            if alerted:
                await paynotify.notify_owner(bot, "✅ CardXabar ko'prigi qayta ulandi.")
            elif first:        # bot har ishga tushganda ownerga bir marta: ko'prik ishlayaptimi — darhol bilinadi
                await paynotify.notify_owner(bot, "✅ <b>CardXabar ko'prigi ulandi</b>: "
                                                  f"@{', @'.join(settings.card_source_list)} xabarlari tinglanmoqda.")
            fails, alerted, delay = 0, False, 5
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            try:
                await client.disconnect()
            finally:
                raise
        except Exception as ex:  # noqa: BLE001
            fails += 1
            STATE["connected"], STATE["last_error"] = False, type(ex).__name__
            log.warning("CardXabar ko'prigi xatosi (%d): %s", fails, type(ex).__name__)
            if fails >= ALERT_AFTER_FAILS and not alerted:
                alerted = True
                await paynotify.notify_owner(bot, f"⚠️ CardXabar ko'prigi {fails} marta ulana olmadi ({type(ex).__name__}). "
                                                  "Qayta urinaman; bot ishlashda davom etadi.")
        finally:
            if CLIENT is client:
                CLIENT = None
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(delay)
        delay = min(delay * 2, 120)
