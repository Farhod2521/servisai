"""Admin tezkor amallari: majburiy obuna (kanallar) va ID bilan hisob to'ldirish.

To'lovlarni tasdiqlash — handlers/pay.py dagi «To'lovlar ro'yxati» (✅ Tasdiqlash / ❌ Rad etish tugmalari).
"""
from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User
from handlers.admin_ext import UserBal
from services import runtime

router = Router(name="admin_quick")
log = logging.getLogger("uzshop.admin_quick")

HOME = "a:home"


class FSub(StatesGroup):
    channel = State()


class FastBal(StatesGroup):
    who = State()


def _is_admin(user: User) -> bool:
    return user.tg_id in settings.admins


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])


# ─────────────────────────── Majburiy obuna ───────────────────────────

def _fsub_view() -> tuple[str, InlineKeyboardMarkup]:
    chans = runtime.force_sub_channels()
    if chans:
        lines = ["📢 <b>Majburiy obuna</b>", "", "Mijoz botdan foydalanishdan oldin shu kanallarga a'zo bo'lishi kerak:"]
        lines += [f"• <code>{html.escape(c)}</code>" for c in chans]
    else:
        lines = ["📢 <b>Majburiy obuna</b>", "", "Hozir <b>o'chiq</b>: hamma botdan erkin foydalanadi.",
                 "Yoqish uchun kanal qo'shing."]
    lines += ["", "ℹ️ Bot qo'shiladigan kanalda <b>ADMIN</b> bo'lishi shart."]
    rows = [[(f"❌ {c}", f"a:fsub_del:{i}")] for i, c in enumerate(chans)]
    rows.append([("➕ Kanal qo'shish", "a:fsub_add")])
    rows.append([("🏠 Bosh sahifa", HOME)])
    return "\n".join(lines), _kb(rows)


@router.callback_query(F.data == "a:fsub")
async def fsub_menu(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    text, kb = _fsub_view()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "a:fsub_add")
async def fsub_add(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(FSub.channel)
    await call.message.edit_text(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Kanalning <code>@username</code> yoki havolasini (<code>https://t.me/kanal</code>) yuboring.\n"
        "Shaxsiy (yopiq) kanal bo'lsa — kanaldagi istalgan xabarni shu yerga <b>forward</b> qiling.\n\n"
        "⚠️ Avval botni o'sha kanalga <b>administrator</b> qiling.",
        reply_markup=_kb([[("⬅️ Orqaga", "a:fsub")]]),
    )
    await call.answer()


def _channel_ref(message: Message) -> str | None:
    """Xabardan kanal manzili: forward qilingan kanal, @username yoki t.me havolasi. Bo'lmasa None."""
    chat = getattr(message, "forward_from_chat", None)
    if chat is None and getattr(message, "forward_origin", None) is not None:
        chat = getattr(message.forward_origin, "chat", None)
    if chat is not None:
        return f"@{chat.username}" if chat.username else str(chat.id)
    raw = (message.text or "").strip().replace(" ", "")
    if not raw:
        return None
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.startswith(prefix):
            raw = "@" + raw[len(prefix):].split("/")[0].split("?")[0]
            break
    if raw.lstrip("-").isdigit():
        return raw
    raw = raw if raw.startswith("@") else "@" + raw
    return raw if len(raw) > 2 and raw[1:].replace("_", "").isalnum() else None


@router.message(FSub.channel)
async def fsub_save(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    ref = _channel_ref(message)
    if not ref:
        return await message.answer("❌ Kanalni tushunmadim. <code>@kanal_username</code> yozing yoki kanaldan xabar forward qiling.")
    try:
        chat = await message.bot.get_chat(int(ref) if ref.lstrip("-").isdigit() else ref)
    except TelegramAPIError:
        return await message.answer("❌ Kanal topilmadi. Username'ni tekshiring (yopiq kanal bo'lsa — kanaldan xabar forward qiling).")
    try:
        me = await message.bot.get_chat_member(chat.id, (await message.bot.me()).id)
        is_admin = me.status in ("administrator", "creator")
    except TelegramAPIError:
        is_admin = False
    if not is_admin:
        return await message.answer(f"⚠️ Bot <b>{html.escape(chat.title or ref)}</b> kanalida administrator emas. "
                                    "Avval botni kanalga admin qiling, so'ng kanalni qayta yuboring.")
    ref = f"@{chat.username}" if chat.username else str(chat.id)
    chans = runtime.force_sub_channels()
    if ref not in chans:
        await runtime.set_force_sub([*chans, ref])
    await state.clear()
    text, kb = _fsub_view()
    await message.answer(f"✅ <b>{html.escape(chat.title or ref)}</b> qo'shildi.\n\n" + text, reply_markup=kb)


@router.callback_query(F.data.startswith("a:fsub_del:"))
async def fsub_del(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    chans = runtime.force_sub_channels()
    try:
        removed = chans.pop(int(call.data.split(":")[2]))
    except (ValueError, IndexError):
        return await call.answer("Ro'yxat o'zgargan. Qayta oching.", show_alert=True)
    await runtime.set_force_sub(chans)
    text, kb = _fsub_view()
    await call.message.edit_text(f"🗑 <code>{html.escape(removed)}</code> olib tashlandi.\n\n" + text, reply_markup=kb)
    await call.answer()


# ─────────────────────────── ID bilan hisob to'ldirish ───────────────────────────

@router.callback_query(F.data == "a:fastbal")
async def fastbal_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(FastBal.who)
    await call.message.edit_text(
        "💰 <b>Hisobni to'ldirish</b>\n\nMijozning <b>Telegram ID</b> raqamini (yoki @username) yuboring.\n"
        "<i>Mijoz ID sini botdagi «Profil» bo'limidan ko'radi.</i>",
        reply_markup=_kb([[("🏠 Bosh sahifa", HOME)]]),
    )
    await call.answer()


@router.message(FastBal.who)
async def fastbal_who(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    q = (message.text or "").strip().lstrip("@")
    if not q:
        return
    if q.isdigit():
        found = await session.scalar(select(User).where(User.tg_id == int(q)))
    else:
        found = await session.scalar(select(User).where(func.lower(User.username) == q.lower()))
    if not found:
        return await message.answer("🚫 Bunday mijoz topilmadi. U botga kamida bir marta /start bosgan bo'lishi kerak. ID ni tekshiring.")
    await state.set_state(UserBal.amount)             # summani mavjud «balans» bosqichi qabul qiladi
    await state.update_data(tg_id=found.tg_id)
    await message.answer(
        f"👤 <b>{html.escape(found.full_name or '—')}</b>" + (f" @{html.escape(found.username)}" if found.username else "") +
        f"\n🆔 <code>{found.tg_id}</code>\n💳 Hozirgi hisob: <b>{found.balance:,}</b> so'm".replace(",", " ") +
        "\n\n💵 Summani so'mda yuboring. Qo'shish uchun <code>50000</code>, ayirish uchun <code>-20000</code>.",
        reply_markup=_kb([[("🏠 Bosh sahifa", HOME)]]),
    )
