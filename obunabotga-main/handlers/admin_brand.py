"""Admin: har bir brend (obuna) uchun o'z foyda foizi. Masalan CapCut — 40%, Claude — 25%.

Foiz qo'yilgan brendning HAMMA mahsuloti narxi = ta'minotchi tannarxi + shu foiz. Foiz qo'yilmagan brendlar umumiy qoida bilan
(💹 Foyda foizi: aqlli narx / bir xil foiz / ustama jadvali). Qo'lda qulflangan (🔒) narxlarga tegilmaydi.
"""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services import canboso, runtime

router = Router(name="admin_brand")


class BrandPct(StatesGroup):
    value = State()


def _admin(user) -> bool:
    return user.tg_id in settings.admins


def _mode_name() -> str:
    m = runtime.pricing_mode()
    return {"smart": "aqlli narx", "tiers": "ustama jadvali", "flat": f"bir xil {runtime.markup_percent():g}%"}.get(m, m)


async def _brands(session: AsyncSession) -> list[str]:
    from handlers.shop import shop_brands
    return await shop_brands(session)


async def _view(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    from keyboards.user_kb import BLUE, GREEN
    brands = await _brands(session)
    marks = runtime.brand_markups()
    btns = [InlineKeyboardButton(text=f"{b} · {marks[b]:g}%" if b in marks else f"{b} · umumiy",
                                 callback_data=f"a:bm:{i}", style=GREEN if b in marks else BLUE) for i, b in enumerate(brands)]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    if marks:
        rows.append([InlineKeyboardButton(text="🧹 Hamma foizlarni olib tashlash", callback_data="a:bmclr")])
    rows.append([InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="a:home", style=GREEN)])
    text = ("🏷 <b>Brend foizlari</b>\n\n"
            "Brendni bosing va foyda foizini yozing. Masalan <b>CapCut — 40</b>: CapCut'ning hamma tarifi "
            "<i>tannarx + 40%</i> bo'lib sotiladi.\n\n"
            f"«umumiy» — foiz qo'yilmagan, umumiy qoida bilan hisoblanadi (hozir: <b>{_mode_name()}</b>).\n"
            "🔒 qo'lda qo'yilgan narxlar o'zgarmaydi.")
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "a:bm")
async def show(call: CallbackQuery, user, session: AsyncSession, state: FSMContext):
    if not _admin(user):
        return await call.answer()
    await state.clear()
    text, kb = await _view(session)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data.regexp(r"^a:bm:\d+$"))
async def pick(call: CallbackQuery, user, session: AsyncSession, state: FSMContext):
    if not _admin(user):
        return await call.answer()
    brands = await _brands(session)
    i = int(call.data.split(":")[2])
    if i >= len(brands):
        return await call.answer("Ro'yxat o'zgargan, qayta oching.", show_alert=True)
    brand = brands[i]
    cur = runtime.brand_markups().get(brand)
    await state.set_state(BrandPct.value)
    await state.update_data(brand=brand)
    await call.message.edit_text(
        f"🏷 <b>{html.escape(brand)}</b> uchun foyda foizi\n\n"
        f"Hozir: <b>{f'{cur:g}%' if cur is not None else 'umumiy (' + _mode_name() + ')'}</b>\n\n"
        "Foizni raqam bilan yozing, masalan <code>40</code>.\n"
        "Umumiy qoidaga qaytarish uchun <code>-</code> yuboring.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:bm")]]))
    await call.answer()


@router.message(BrandPct.value)
async def save(message: Message, user, session: AsyncSession, state: FSMContext):
    if not _admin(user):
        return
    brand = (await state.get_data()).get("brand")
    raw = (message.text or "").strip().replace(",", ".").rstrip("%").strip()
    if not brand:
        await state.clear()
        return
    if raw == "-":
        pct = None
    else:
        try:
            pct = float(raw)
        except ValueError:
            return await message.answer("❌ Raqam yozing, masalan <code>40</code> (yoki <code>-</code>).")
        if not 0 <= pct <= 500:
            return await message.answer("❌ Foiz 0 dan 500 gacha bo'lsin.")
    await runtime.set_brand_markup(brand, pct)
    await state.clear()
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    done = f"✅ <b>{html.escape(brand)}</b>: " + (f"{pct:g}% qo'yildi" if pct is not None else "umumiy qoidaga qaytdi")
    text, kb = await _view(session)
    await message.answer(f"{done}. 🔄 {n} ta narx yangilandi.\n\n{text}", reply_markup=kb)


@router.callback_query(F.data == "a:bmclr")
async def clear_all(call: CallbackQuery, user, session: AsyncSession):
    if not _admin(user):
        return await call.answer()
    await runtime.set_value("brand_markup", None)
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    text, kb = await _view(session)
    try:
        await call.message.edit_text(f"🧹 Hamma brend foizlari olib tashlandi. 🔄 {n} ta narx yangilandi.\n\n{text}", reply_markup=kb)
    except TelegramBadRequest:
        pass
    await call.answer()
