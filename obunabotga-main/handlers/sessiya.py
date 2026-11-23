"""Owner: Telegram sessiyasini botning o'zida olish (/sessiya). Avto-to'lov (@HUMOcardbot xabarlarini o'qish) uchun.

Faqat bot egasi (TELEGRAM_OWNER_ID). Kod va parol yozilgan xabarlar darhol o'chiriladi.
"""
from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import settings
from services import cardbridge, paynotify, runtime, tglogin

router = Router(name="sessiya")
log = logging.getLogger("uzshop.sessiya")


class Ses(StatesGroup):
    phone = State()
    code = State()
    password = State()


def _cancel_kb() -> InlineKeyboardMarkup:
    from keyboards.user_kb import RED
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ses:cancel", style=RED)]])


def _owner(user) -> bool:
    return paynotify.is_owner(getattr(user, "tg_id", None))


async def _wipe(message: Message) -> None:
    """Kod/parol yozilgan xabarni o'chiradi (chatda qolmasin)."""
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("sessiya"))
async def start(message: Message, user, state: FSMContext):
    if not _owner(user):
        return
    await state.clear()
    st = cardbridge.STATE
    have = "ulangan ✅" if st.get("connected") else ("sozlangan, ulanmoqda…" if runtime.tg_session() else "yo'q")
    if not tglogin.configured():
        return await message.answer("⚠️ Render → Environment'da <code>TG_API_ID</code> va <code>TG_API_HASH</code> yo'q. "
                                    "Ularni my.telegram.org → API development tools dan oling, so'ng qayta /sessiya yozing.")
    if settings.public_url:
        # Asosiy usul: brauzerdagi bir martalik sahifa — kod Telegram chatiga yozilmaydi (aks holda Telegram uni «eskirgan» qiladi)
        from keyboards.user_kb import GREEN
        link = f"{settings.public_url}/sessiya/{tglogin.new_link(user.tg_id)}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔑 Sessiya olish (brauzerda)", url=link, style=GREEN)]])
        return await message.answer(
            f"🔑 <b>Telegram sessiya</b> (avto-to'lov uchun)\nHozirgi holat: <b>{have}</b>\n\n"
            "Tugmani bosing — ochilgan sahifada telefon raqam, kod va (bo'lsa) 2FA parolni yozasiz. "
            "Kod <b>shu sahifaga</b> yoziladi, Telegram chatiga emas.\n"
            "Havola 15 daqiqa va faqat bir marta ishlaydi. Uni hech kimga yubormang.\n\n"
            "<i>Bu akkaunt @HUMOcardbot xabarlarini oladigan akkaunt bo'lishi kerak (alohida, ikkinchi akkaunt yaxshi).</i>", reply_markup=kb)
    await state.set_state(Ses.phone)
    await message.answer(
        f"🔑 <b>Telegram sessiya</b> (avto-to'lov uchun)\nHozirgi holat: <b>{have}</b>\n\n"
        "Bu akkaunt <b>@HUMOcardbot</b> xabarlarini oladigan Telegram akkaunt bo'lishi kerak (alohida, ikkinchi akkaunt yaxshi).\n\n"
        "📱 Shu akkauntning telefon raqamini yozing: <code>+998901234567</code>",
        reply_markup=_cancel_kb())


@router.callback_query(F.data == "ses:cancel")
async def cancel(call: CallbackQuery, user, state: FSMContext):
    if not _owner(user):
        return await call.answer()
    await tglogin.cancel(user.tg_id)
    await state.clear()
    await call.message.answer("Bekor qilindi.")
    await call.answer()


@router.message(Ses.phone, F.text)
async def got_phone(message: Message, user, state: FSMContext):
    if not _owner(user):
        return
    try:
        phone = await tglogin.begin(user.tg_id, message.text or "")
    except tglogin.LoginError as ex:
        return await message.answer(f"❌ {html.escape(str(ex), quote=False)}", reply_markup=_cancel_kb())
    await state.set_state(Ses.code)
    await message.answer(
        f"📨 <b>{html.escape(phone)}</b> raqamli Telegram'ga kod yuborildi (Telegram ilovasida «Telegram» chatiga).\n\n"
        "Kodni <b>raqamlar orasiga bo'sh joy qo'yib</b> yozing: <code>1 2 3 4 5</code>\n"
        "⚠️ Bo'sh joysiz yozsangiz Telegram kodni bekor qiladi.", reply_markup=_cancel_kb())


@router.message(Ses.code, F.text)
async def got_code(message: Message, user, state: FSMContext):
    if not _owner(user):
        return
    raw = message.text or ""
    await _wipe(message)
    try:
        res = await tglogin.submit_code(user.tg_id, raw)
    except tglogin.LoginError as ex:
        return await message.answer(f"❌ {html.escape(str(ex), quote=False)}", reply_markup=_cancel_kb())
    if res == "password":
        await state.set_state(Ses.password)
        return await message.answer("🔐 Akkauntda 2 bosqichli parol (2FA) bor. Uni yozing — yozganingizdan keyin xabar o'chiriladi.",
                                    reply_markup=_cancel_kb())
    await _done(message, state)


@router.message(Ses.password, F.text)
async def got_password(message: Message, user, state: FSMContext):
    if not _owner(user):
        return
    raw = message.text or ""
    await _wipe(message)
    try:
        await tglogin.submit_password(user.tg_id, raw)
    except tglogin.LoginError as ex:
        return await message.answer(f"❌ {html.escape(str(ex), quote=False)}", reply_markup=_cancel_kb())
    await _done(message, state)


async def _done(message: Message, state: FSMContext) -> None:
    await state.clear()
    cardbridge.STATE["connected_at"] = None      # qayta ulanganda ownerga «ulandi» xabari kelsin
    cardbridge.start(message.bot)               # yangi session bilan ko'prikni qayta yoqamiz
    await message.answer("✅ <b>Sessiya saqlandi.</b> Ko'prik ishga tushirilmoqda — bir necha soniyada «ulandi» xabari keladi.\n\n"
                         "Sinash: botdan 1 000 so'm to'ldirish so'rang va aniq summani o'tkazing.\n"
                         "ℹ️ Baza vaqtinchalik (SQLite) bo'lsa, Render yangilanganda sessiyani qayta olish kerak bo'ladi.")
