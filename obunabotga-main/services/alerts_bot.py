"""Hisobot botining o'zi: adminlar unda /start, /bugun, /kun10, /kun30 yoki tugmalar bilan savdo + foyda hisobotini ko'radi.

Webhook orqali ishlaydi (asosiy bot bilan bir serverda), shuning uchun deploy paytida «ikki nusxa» to'qnashuvi bo'lmaydi.
Har kuni 23:55 (Toshkent) kunlik hisobot avtomatik yuboriladi.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import settings
from services import alerts, stats

log = logging.getLogger("uzshop.alerts_bot")
router = Router(name="alerts_bot")
DAILY_AT = (23, 55)          # Toshkent vaqti


def _secret() -> str:
    return hashlib.sha256(settings.alert_bot_token.encode()).hexdigest()[:32]


def path() -> str:
    return f"/alert/{_secret()[:16]}"


def _is_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in alerts.recipients()


def kb(active: int) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=("• " if d == active else "") + ("Bugun" if d == 1 else f"{d} kun"), callback_data=f"st:{d}")
           for d in stats.PERIODS]
    return InlineKeyboardMarkup(inline_keyboard=[row])


async def _show(days: int) -> str:
    from services import canboso
    text = stats.report_text(await stats.report(days))
    try:
        bal = await canboso.balance_line()
    except Exception:  # noqa: BLE001
        bal = ""
    return text + (f"\n\n{bal}" if bal else "")


@router.message(Command("start", "stat", "bugun"))
async def cmd_today(message: Message):
    if not _is_admin(message.from_user.id if message.from_user else None):
        return await message.answer("Bu bot faqat do'kon adminlari uchun.")
    await message.answer("▶️ <b>Hisobot boti</b> ulandi. Savdolar, foyda, to'lovlar va xatolar shu yerga keladi.\n\n" + await _show(1), reply_markup=kb(1))


@router.message(Command("hisob"))
async def cmd_balance(message: Message):
    """/hisob — ta'minotchidagi hamyon qoldig'i."""
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    from services import canboso
    line = await canboso.balance_line()
    await message.answer(line or "Ta'minotchi hamyonini olib bo'lmadi (kalit sozlanmagan yoki ta'minotchi javob bermadi).")


@router.message(Command("kun10"))
async def cmd_10(message: Message):
    if _is_admin(message.from_user.id if message.from_user else None):
        await message.answer(await _show(10), reply_markup=kb(10))


@router.message(Command("kun30"))
async def cmd_30(message: Message):
    if _is_admin(message.from_user.id if message.from_user else None):
        await message.answer(await _show(30), reply_markup=kb(30))


@router.callback_query(F.data.startswith("st:"))
async def cb_period(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        return await call.answer()
    days = int(call.data.split(":")[1])
    if days not in stats.PERIODS:
        return await call.answer()
    try:
        await call.message.edit_text(await _show(days), reply_markup=kb(days))
    except Exception:  # noqa: BLE001 — matn o'zgarmagan bo'lsa Telegram xato beradi
        pass
    await call.answer()


def setup(app) -> None:
    """Asosiy web-ilovaga hisobot botining webhook yo'lini ulaydi (token berilmasa — hech narsa)."""
    if not alerts.enabled():
        return
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler
    dp = Dispatcher()
    dp.include_router(router)
    SimpleRequestHandler(dispatcher=dp, bot=alerts.get_bot(), secret_token=_secret()).register(app, path=path())
    app["alert_dp"] = dp


async def start(main_bot) -> None:
    """Webhook o'rnatish, buyruqlar ro'yxati, ulanganlik xabari. Xatolar botni to'xtatmaydi."""
    if not alerts.enabled():
        return
    ab = alerts.get_bot()
    for attempt in range(1, 4):
        try:
            await ab.set_webhook(settings.public_url + path(), secret_token=_secret(),
                                 allowed_updates=["message", "callback_query"])
            await ab.set_my_commands([BotCommand(command="bugun", description="Bugungi savdo va foyda"),
                                      BotCommand(command="kun10", description="Oxirgi 10 kun"),
                                      BotCommand(command="kun30", description="Oxirgi 30 kun"),
                                      BotCommand(command="hisob", description="Ta'minotchi hamyoni")])
            break
        except Exception as ex:  # noqa: BLE001
            log.warning("Hisobot boti webhooki o'rnatilmadi (%d/3): %s", attempt, type(ex).__name__)
            await asyncio.sleep(3 * attempt)
    await alerts.hello(main_bot)


def _seconds_until_daily(now: datetime | None = None) -> float:
    local = (now or datetime.utcnow()) + stats.TZ
    target = local.replace(hour=DAILY_AT[0], minute=DAILY_AT[1], second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return (target - local).total_seconds()


async def daily_loop(main_bot) -> None:
    """Har kuni 23:55 da kunlik hisobot adminlarga yuboriladi."""
    if not alerts.enabled():
        return
    while True:
        await asyncio.sleep(_seconds_until_daily())
        try:
            await alerts.broadcast(main_bot, "🌙 <b>Kunlik hisobot</b>\n\n" + await _show(1))
        except Exception:  # noqa: BLE001
            log.exception("Kunlik hisobot yuborilmadi")
        await asyncio.sleep(90)
