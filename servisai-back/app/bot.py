"""Telegram bot: saytga kirish/ro‘yxatdan o‘tishni tasdiqlaydi va buyurtmalarni ko‘rsatadi.

Ishga tushirish: python -m app.bot
"""

import asyncio
import html
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from .accounts import AccountConflict, upsert_telegram_user
from .config import settings
from .database import SessionLocal
from .models import Order, TelegramLoginSession, TelegramLoginStatus, User
from .notify import STATUS_LABELS, format_price

log = logging.getLogger("servisai.bot")
dp = Dispatcher()

CONTACT_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def site_button(text: str = "🌐 Saytga qaytish", path: str = "/profil") -> InlineKeyboardMarkup | None:
    url = settings.frontend_url.rstrip("/") + path
    # Telegram localhost havolalarini qabul qilmaydi
    if url.startswith("http://localhost") or url.startswith("http://127."):
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


async def confirm_login(message: Message, token: str) -> None:
    tg = message.from_user
    async with SessionLocal() as session:
        login = await session.get(TelegramLoginSession, token, with_for_update=True)
        if (
            login is None
            or login.status != TelegramLoginStatus.pending
            or login.expires_at < datetime.now(timezone.utc)
        ):
            await message.answer("⚠️ Havola eskirgan yoki allaqachon ishlatilgan. Saytda «Telegram orqali kirish» tugmasini qayta bosing.")
            return

        link_to = await session.get(User, login.link_user_id) if login.link_user_id else None
        try:
            user = await upsert_telegram_user(
                session,
                telegram_id=tg.id,
                first_name=tg.first_name,
                last_name=tg.last_name,
                username=tg.username,
                link_to=link_to,
            )
        except AccountConflict as e:
            login.error = str(e)
            await session.commit()
            await message.answer(f"⚠️ {e}.")
            return

        login.user_id = user.id
        login.status = TelegramLoginStatus.confirmed
        await session.commit()
        has_phone = bool(user.phone)

    text = (
        f"✅ <b>{html.escape(tg.first_name)}</b>, Telegram profilingiz ulandi!"
        if link_to
        else f"✅ Xush kelibsiz, <b>{html.escape(tg.first_name)}</b>! Siz servisai.uz saytiga muvaffaqiyatli kirdingiz."
    )
    await message.answer(text + "\n\nBrauzerdagi sahifaga qayting — u avtomatik yangilanadi.", reply_markup=site_button())
    if not has_phone:
        await message.answer(
            "Buyurtmalar bo‘yicha tezroq bog‘lanishimiz uchun telefon raqamingizni yuboring (ixtiyoriy).",
            reply_markup=CONTACT_KEYBOARD,
        )


@dp.message(CommandStart(deep_link=True))
async def start_with_token(message: Message, command: CommandObject) -> None:
    await confirm_login(message, command.args)


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "👋 Assalomu alaykum! Bu <b>servisai.uz</b> rasmiy boti.\n\n"
        "Saytga kirish uchun saytdagi «Tizimga kirish» → «Telegram orqali kirish» tugmasini bosing.\n\n"
        "/orders — mening buyurtmalarim",
        reply_markup=site_button("🌐 Saytni ochish", "/"),
    )


@dp.message(Command("orders"))
async def my_orders(message: Message) -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if user is None:
            await message.answer("Siz hali ro‘yxatdan o‘tmagansiz. Saytda «Telegram orqali kirish» tugmasini bosing.")
            return
        orders = (
            await session.scalars(
                select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(10)
            )
        ).all()

    if not orders:
        await message.answer("Sizda hali buyurtmalar yo‘q.", reply_markup=site_button("🛍 Servislarni ko‘rish", "/mahsulotlar"))
        return
    lines = [
        f"<b>{o.number}</b> · {html.escape(o.product_name)} · {format_price(o.price)} so‘m\n{STATUS_LABELS[o.status]}"
        for o in orders
    ]
    await message.answer("🧾 <b>Oxirgi buyurtmalaringiz</b>\n\n" + "\n\n".join(lines), reply_markup=site_button("📋 Barchasini ko‘rish"))


@dp.message(F.contact)
async def save_contact(message: Message) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o‘zingizning raqamingizni yuboring.")
        return
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if user is None:
            await message.answer("Avval saytda «Telegram orqali kirish» tugmasini bosing.", reply_markup=ReplyKeyboardRemove())
            return
        phone = message.contact.phone_number
        user.phone = phone if phone.startswith("+") else f"+{phone}"
        await session.commit()
    await message.answer("📱 Raqamingiz saqlandi. Rahmat!", reply_markup=ReplyKeyboardRemove())


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.telegram_bot_token:
        log.error("TELEGRAM_BOT_TOKEN berilmagan — bot ishga tushmaydi")
        # Konteyner qayta-qayta restart bo‘lmasligi uchun kutib turamiz
        await asyncio.Event().wait()
    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
