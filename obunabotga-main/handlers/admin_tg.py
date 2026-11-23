"""Admin: Telegram Stars / Premium (Fragment) holati va ustama foizi."""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import settings
from locales.texts import money
from services import runtime, starsuno

router = Router(name="admin_tg")


class TGMarkup(StatesGroup):
    percent = State()


def _admin(user) -> bool:
    return user.tg_id in settings.admins


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    from keyboards.user_kb import BLUE, GREEN
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d, style=GREEN if d == "a:home" else BLUE)
                                                  for t, d in r] for r in rows])


async def _status() -> str:
    from services import fragment_tg, tgshop
    lines = ["⭐ <b>Stars / Premium</b> · manba: <b>Fragment</b>", ""]
    if not fragment_tg.configured():
        lines += ["❌ Fragment sozlanmagan — Stars/Premium sotilmaydi.",
                  "Render → Environment ga yozing: FRAGMENT_SEED, FRAGMENT_API_KEY, FRAGMENT_COOKIES."]
        return "\n".join(lines)
    err = await fragment_tg.check()                        # Fragment hozir javob beryaptimi (keshsiz)
    lines.append(f"❌ <b>Fragment ishlamayapti</b>\nSabab: <b>{html.escape(err)}</b>" if err else "✅ Fragment ishlayapti")
    lines.append("")
    info = await fragment_tg.wallet_info()
    if info is None:
        lines.append(f"⚠️ Hamyonni o'qib bo'lmadi: {html.escape(fragment_tg.STATE.get('last_error') or '—')}")
    else:
        ton, addr = info
        lines.append(f"💎 Hamyon: <b>{ton:g} TON</b>" + ("  ⚠️ <b>kam, to'ldiring!</b>" if ton < 2 else ""))
        if addr:
            lines.append(f"   manzil: <code>{html.escape(addr)}</code>\n   (fragment.com'da ulangan hamyon manzili bilan bir xil bo'lsin)")
        if fragment_tg.STATE.get("wallet_version"):
            lines.append(f"   hamyon turi: {html.escape(fragment_tg.STATE['wallet_version'])}")
    if err:
        return "\n".join(lines)
    pct = starsuno.markup_percent()
    lines.append(f"💹 Ustama (foyda): <b>{pct:g}%</b>")
    try:
        unit = await tgshop.star_unit_price()
        prem = await tgshop.premium_prices()
    except starsuno.SupplierError as ex:
        lines.append(f"⚠️ Narxlar olinmadi: {html.escape(str(ex))}")
        return "\n".join(lines)
    lines += ["", f"⭐ 1 Stars: tannarx {unit:.0f} → sotuv {unit * (1 + pct / 100):.0f} so'm",
              f"   100 Stars: {money(starsuno.sell_price(unit * 100))}"]
    for m in sorted(prem):
        lines.append(f"👑 {m} oy: tannarx {money(prem[m])} → sotuv <b>{money(starsuno.sell_price(prem[m]))}</b>")
    return "\n".join(lines)


async def _edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "a:tg")
async def tg_status(call: CallbackQuery, user, state: FSMContext):
    if not _admin(user):
        return await call.answer()
    await state.clear()
    await _edit(call, await _status(), _kb([[("💹 Ustama foizi", "a:tgm"), ("🔃 Yangilash", "a:tg")], [("🏠 Bosh sahifa", "a:home")]]))
    await call.answer()


@router.callback_query(F.data == "a:tgm")
async def tg_markup(call: CallbackQuery, user, state: FSMContext):
    if not _admin(user):
        return await call.answer()
    await state.set_state(TGMarkup.percent)
    await _edit(call, f"💹 <b>Stars/Premium ustamasi</b>\n\nHozir: <b>{starsuno.markup_percent():g}%</b>\n\n"
                      "Yangi foizni yozing (masalan <code>10</code>). Tannarxga shuncha qo'shiladi.",
                _kb([[("⬅️ Orqaga", "a:tg")]]))
    await call.answer()


@router.message(TGMarkup.percent, F.text)
async def tg_markup_save(message: Message, user, state: FSMContext):
    if not _admin(user):
        return
    raw = (message.text or "").strip().replace(",", ".").rstrip("%")
    try:
        pct = float(raw)
    except ValueError:
        return await message.answer("❌ Raqam yozing, masalan <code>10</code>.")
    if not 0 <= pct <= 300:
        return await message.answer("❌ Foiz 0 dan 300 gacha bo'lsin.")
    await runtime.set_value("tg_markup", f"{pct:g}")
    await state.clear()
    await message.answer(f"✅ Ustama <b>{pct:g}%</b> qilib saqlandi.\n\n" + await _status(),
                         reply_markup=_kb([[("🏠 Bosh sahifa", "a:home")]]))
