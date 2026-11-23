"""/start va qolgan hamma narsa.

  • /start — salomlashuv + pastki menyu (Obunalar, Hisobni to'ldirish, Buyurtmalarim, Profil, Qo'llanma, Yordam)
    va «Obunalarni tanlang» ro'yxati (brend logotiplari — premium emoji);
  • boshqa hech kim qayta ishlamagan xabar — shu menyuni qayta ko'rsatadi.
Do'kon oqimi handlers/shop.py da.
"""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User
from handlers import shop
from keyboards.user_kb import main_menu
from locales.texts import t
from services import paynotify, runtime, topup
from services.subscription import missing_channels

router = Router(name="start")


def is_admin(user: User) -> bool:
    return user.tg_id in settings.admins


def welcome_text(user: User, lang: str, has_app: bool = True) -> str:
    """/start matni: admin saqlagan (premium emojili) matn, bo'lmasa standart. {name} — foydalanuvchi ismi."""
    name = html.escape(user.full_name or "")
    custom = runtime.welcome_html()
    return custom.replace("{name}", name) if custom else t(lang, "hello", name=name)


async def send_welcome(message: Message, user: User, lang: str, session: AsyncSession, product_id: int | None = None) -> None:
    """Salomlashuv (pastki menyu bilan) va obunalar ro'yxati. Havola ?start=p12 bo'lsa — shu mahsulot kartasi."""
    kb = main_menu(lang, is_admin(user))
    try:
        await message.answer(welcome_text(user, lang), reply_markup=kb)
    except TelegramBadRequest:       # admin yozgan matnda xato bo'lsa (masalan, yaroqsiz teg) — standart matn yuboriladi
        await message.answer(t(lang, "hello", name=html.escape(user.full_name or "")), reply_markup=kb)
    if product_id:
        p = await shop.repo.get_product(session, product_id)
        if p and p.is_active and shop.in_stock(p):
            return await shop.send_plan(message, p, user, lang)
    await shop.send_services(message, session, lang)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, user: User, lang: str, session: AsyncSession):
    # Majburiy obuna middleware'da tekshiriladi — bu yerga faqat a'zolar keladi.
    pid = None
    if command.args and command.args.startswith("p") and command.args[1:].isdigit():
        pid = int(command.args[1:])      # e'londagi havola: ?start=p12 → 12-mahsulot
    await send_welcome(message, user, lang, session, pid)


@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, user: User, lang: str, session: AsyncSession):
    """«Tekshirish» tugmasi: obuna bo'lgan bo'lsa — menyuga yo'naltiradi."""
    if await missing_channels(call.bot, user.tg_id, fresh=True):
        return await call.answer(t(lang, "sub_not_yet"), show_alert=True)
    try:
        await call.message.delete()
    except Exception:  # noqa: BLE001 — xabar allaqachon o'chgan bo'lishi mumkin
        pass
    await call.answer(t(lang, "sub_ok"))
    await send_welcome(call.message, user, lang, session)


# ─── Eng oxirgi router: boshqa hech kim qayta ishlamagan hamma narsa ───

fallback = Router(name="fallback")


@fallback.message(F.chat.type == "private")
async def any_message(message: Message, user: User, lang: str, session: AsyncSession):
    """Tushunilmagan yozuv yoki eski menyu tugmasi: yangi menyu va obunalar ro'yxati qayta chiqadi.
    Owner HUMO/bank kirim xabarini shu botga forward qilsa yoki yozsa — u kirim sifatida qayta ishlanadi (Business ishlamasa zaxira yo'l)."""
    text = message.text or message.caption or ""
    if text and paynotify.is_owner(user.tg_id) and topup.parse_credit(text).kind == "credit":
        out = await paynotify.process_incoming(message.bot, "forward", f"{message.chat.id}:{message.message_id}", text, "card")
        notes = {"matched": "✅ Kirim topildi va to'lov tasdiqlandi.",
                 "duplicate": "ℹ️ Bu xabar allaqachon ko'rilgan.",
                 "candidate": "⚠️ Mos buyurtmalar topildi — yuqoridagi xabarda tasdiqlang.",
                 "late": "⏰ Buyurtma muddati tugagan — yuqoridagi xabarda ko'rib chiqing.",
                 "unmatched": "❌ Shu summali faol buyurtma topilmadi (muddati o'tgan yoki summa boshqa)."}
        return await message.answer(notes.get(out.kind, "ℹ️ Kirim sifatida qabul qilinmadi."))
    await send_welcome(message, user, lang, session)


@fallback.callback_query()
async def any_callback(call: CallbackQuery, lang: str):
    """Eskirgan inline tugmalar."""
    await call.answer(t(lang, "stale_button"), show_alert=True)
