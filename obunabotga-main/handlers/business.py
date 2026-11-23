"""Telegram Business ko'prigi: bot egasining Telegram akkauntiga (Premium) BOT ULANADI, akkauntga kelgan @HUMOcardbot kirim
xabarlari botga business_message sifatida keladi → avto-to'lov. Session, kod, parol, userbot — hech narsa kerak emas (rasmiy usul).

Ulash (bir marta): Telegram → Sozlamalar → Telegram Business → Chatbotlar → shu botni qo'shing (kerakli chatlarga: @HUMOcardbot).
Faqat bot egasining (TELEGRAM_OWNER_ID) ulanishi qabul qilinadi; boshqa birovning business akkaunti ulansa — e'tiborsiz qoldiriladi.
"""
from __future__ import annotations

import html
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BusinessConnection, Message

from config import settings
from services import cardbridge, paynotify, runtime, topup

router = Router(name="business")
log = logging.getLogger("uzshop.business")

_OWNER_CONN: dict[str, bool] = {}          # business_connection_id → bu owner'ning ulanishimi
STATE: dict = {"connected": False, "last_event": None, "events": 0, "first_notified": False, "seen": [], "announced": set()}


async def _is_owner_connection(bot: Bot, conn_id: str | None) -> bool:
    if not conn_id:
        return False
    if conn_id in _OWNER_CONN:
        return _OWNER_CONN[conn_id]
    if runtime._cache.get("biz_conn") == conn_id:          # owner ulanishi bazada saqlangan (bot qayta ishga tushgan bo'lsa ham)
        _OWNER_CONN[conn_id] = True
        return True
    try:
        conn = await bot.get_business_connection(conn_id)
        ok = bool(conn.user and int(conn.user.id) == int(settings.owner_id))
    except Exception as ex:  # noqa: BLE001 — ulanish ma'lumotini olib bo'lmadi: ishonmaymiz, keyingi safar qayta urinamiz
        log.warning("Business ulanishini tekshirib bo'lmadi: %s", type(ex).__name__)
        if not STATE.get("verify_warned"):
            STATE["verify_warned"] = True
            await paynotify.notify_owner(bot, f"⚠️ Business ulanishini tekshirib bo'lmadi ({type(ex).__name__}). Sozlamalarda botni olib tashlab, "
                                              "qayta qo'shing — shunda ulanish yangilanadi.")
        return False
    _OWNER_CONN[conn_id] = ok
    return ok


@router.business_connection()
async def on_connection(conn: BusinessConnection, bot: Bot):
    mine = bool(conn.user and int(conn.user.id) == int(settings.owner_id))
    _OWNER_CONN[conn.id] = mine
    if not mine:
        log.warning("Begona business ulanish e'tiborsiz qoldirildi")
        return
    STATE["connected"] = bool(conn.is_enabled)
    STATE["can_reply"] = bool(getattr(conn, "can_reply", False))
    await runtime.set_value("biz_conn", conn.id if conn.is_enabled else None)
    if conn.is_enabled and not STATE["can_reply"]:
        await paynotify.notify_owner(bot, "⚠️ Botga <b>ruxsatlar berilmagan</b> (javob berish/o'qish o'chiq). Telegram bunday holatda xabarlarni "
                                          "botga bermasligi mumkin. Telegram → Sozlamalar → Telegram Business → Chatbotlar → botni oching va "
                                          "<b>barcha ruxsatlarni yoqing</b>, Saqlang.")
    text = ("✅ <b>Business ulandi.</b> @HUMOcardbot kirim xabarlari endi shu akkauntdan avtomatik o'qiladi.\n\n"
            "Sinash: botdan 1 000 so'm to'ldirish so'rang va aniq summani o'tkazing."
            if conn.is_enabled else "⚠️ Business ulanish o'chirildi — avto-to'lov to'xtadi.")
    await paynotify.notify_owner(bot, text)


@router.business_message()
async def on_business_message(message: Message, bot: Bot):
    if not await _is_owner_connection(bot, message.business_connection_id):
        return
    sender = message.from_user
    if sender is None or int(sender.id) == int(settings.owner_id):
        return                                                   # owner'ning o'z xabarlari (chiquvchi) — kirim emas
    text = message.text or message.caption or ""
    who = f"@{sender.username}" if sender.username else f"id{sender.id}"
    STATE["seen"] = (STATE["seen"] + [(topup.utcnow(), who, bool(sender.is_bot), text[:50] if sender.is_bot else "")])[-8:]
    if who not in STATE["announced"] and len(STATE["announced"]) < 20:      # har yangi yuboruvchi haqida ownerga bir marta: xabar KELAYAPTIMI — bilinadi
        STATE["announced"].add(who)
        await paynotify.notify_owner(bot, f"ℹ️ Business orqali xabar keldi: <b>{who}</b> ({'bot' if sender.is_bot else 'odam'})"
                                          + ("" if sender.is_bot else " — e'tiborsiz qoldirildi (faqat botlar kirim hisoblanadi)"))
    handled = await cardbridge.on_message(
        bot, sender_username=sender.username, is_private=message.chat.type == "private",
        chat_id=int(message.chat.id), msg_id=int(message.message_id), text=text, any_bot=bool(sender.is_bot))
    if handled:
        STATE["connected"], STATE["last_event"] = True, topup.utcnow()
        STATE["events"] += 1
        if not STATE["first_notified"]:
            STATE["first_notified"] = True
            await paynotify.notify_owner(bot, f"✅ Business ko'prigi ishlayapti: @{sender.username} xabari keldi.")


@router.message(Command("business"))
async def info(message: Message, user, bot: Bot):
    if not paynotify.is_owner(getattr(user, "tg_id", None)):
        return
    me = await bot.me()
    conn_id = runtime._cache.get("biz_conn")
    if conn_id:                                   # bot qayta ishga tushgan bo'lsa ham — haqiqiy holatni Telegram'dan so'raymiz
        try:
            conn = await bot.get_business_connection(conn_id)
            STATE["connected"] = bool(conn.is_enabled and conn.user and int(conn.user.id) == int(settings.owner_id))
            STATE["can_reply"] = bool(getattr(conn, "can_reply", False))
        except Exception as ex:  # noqa: BLE001
            log.warning("Business holatini olib bo'lmadi: %s", type(ex).__name__)
    last = topup.to_tashkent_time(STATE["last_event"]) if STATE["last_event"] else "hali yo'q"
    seen = "\n".join(f"• {topup.to_tashkent_time(t)} {w} ({'bot' if b else 'odam'}) {html.escape(x)}" for t, w, b, x in STATE["seen"]) or "hali xabar kelmadi"
    await message.answer(
        "🔗 <b>Telegram Business ko'prigi</b> (avto-to'lov)\n"
        f"Holat: <b>{'ulangan ✅' if STATE['connected'] else 'ulanmagan'}</b> · ruxsatlar: "
        f"<b>{'yoqiq ✅' if STATE.get('can_reply') else 'o' + chr(39) + 'chiq ⚠️'}</b> · oxirgi kirim xabari: {last}\n\n"
        "<b>Ulash (bir marta, Telegram Premium kerak):</b>\n"
        "1) Telegram → Sozlamalar → <b>Telegram Business</b> → <b>Chatbotlar</b>\n"
        f"2) <b>@{me.username}</b> ni tanlang\n"
        "3) «Chatlar» bo'limida <b>@HUMOcardbot</b> chatini qo'shing (yoki «Barcha chatlar»)\n"
        "4) Bot ruxsatlarining <b>hammasini yoqing</b> (javob berish, o'qish)\n\n"
        "Ulangach «✅ Business ulandi» xabari keladi. Faqat sizning (owner) akkauntingiz qabul qilinadi.\n\n"
        f"📥 <b>Oxirgi kelgan xabarlar</b> (Business orqali):\n{seen}\n\n"
        + ("" if conn_id else "⚠️ Ulanish ma'lumoti saqlanmagan: Chatbotlar sozlamasida botni olib tashlab, qayta qo'shing.\n\n") +
        "ℹ️ Business orqali xabar umuman kelmasa, HUMO bot xabarini shu botga <b>forward</b> qiling — bot uni o'zi o'qib to'lovni tasdiqlaydi.")
