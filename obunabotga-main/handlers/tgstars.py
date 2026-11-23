"""Telegram Stars va Premium sotish (Fragment orqali, TON hamyondan). Mijoz oqimi:

  Obunalar → ⭐ Stars / 👑 Premium → miqdor yoki muddat → kimga (o'ziga / boshqa @username) → tasdiqlash → yuborildi.

Pul balansdan oldin yechiladi; Fragment'da pul ketmagan xato bo'lsa — qaytariladi; natija noma'lum bo'lsa — qaytarilmaydi,
buyurtma «kutilmoqda» turadi va adminlarga xabar boradi (services/fragment_tg.py).
"""
from __future__ import annotations

import html
import logging
import math
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, OrderItem, OrderStatus, User
from keyboards.user_kb import BLUE, GREEN, RED, green_button
from locales.texts import money
from services import alerts, fragment_tg, tgshop as starsuno   # manba: Fragment (services/tgshop.py)

router = Router(name="tgstars")
log = logging.getLogger("uzshop.tgstars")

PRESETS = (50, 100, 250, 500, 1000, 2500)
BACK = "svc:back"
LOW_TON = 2.0                              # hamyonda shundan kam TON qolsa — adminga ogohlantirish
_last_low_alert: float | None = None      # oxirgi «hisob kam» ogohlantirishi vaqti (monotonic)


class TG(StatesGroup):
    amount = State()      # Stars miqdorini yozish
    target = State()      # boshqa foydalanuvchi username'i


TX = {
    "uz": {
        "stars_title": "⭐ <b>Telegram Stars</b>\n\nKerakli miqdorni tanlang yoki o'zingiz yozing ({lo}–{hi}).\n💵 1 ta Stars ≈ <b>{unit}</b>",
        "prem_title": "👑 <b>Telegram Premium</b>\n\nMuddatni tanlang:",
        "custom": "➕ Boshqa miqdor",
        "ask_amount": "💬 Stars miqdorini yozing ({lo}–{hi}):",
        "bad_amount": "❌ Miqdor {lo} dan {hi} gacha butun son bo'lishi kerak.",
        "who": "👤 <b>Kimga yuboramiz?</b>\n\n{what}",
        "me": "👤 O'zimga (@{u})",
        "other": "👤 Boshqa foydalanuvchi",
        "ask_target": "💬 Qabul qiluvchining <b>@username</b> ini yozing:",
        "bad_target": "❌ Username noto'g'ri. Masalan: <code>@monk</code> (kamida 4 belgi, lotin harflari, raqam va _).",
        "no_username": "Sizda Telegram username yo'q. «Boshqa foydalanuvchi» orqali yozing.",
        "confirm": ("{what}\n👤 Kimga: <b>@{u}</b>\n\n💵 <b>Narxi:</b> {price}\n💳 <b>Hisobingiz:</b> {bal}\n\n"
                    "⚠️ Username to'g'riligini tekshiring: yuborilgan narsa qaytarilmaydi."),
        "price_changed": "⚠️ Narx yangilandi. Qayta tasdiqlang.\n\n",
        "buy": "Sotib olish", "cancel": "❌ Bekor qilish",
        "cancelled": "Bekor qilindi.",
        "busy": "⏳ Buyurtmangiz bajarilmoqda, biroz kuting...",
        "unavailable": "⚠️ Xizmat vaqtincha ishlamayapti. Birozdan so'ng urinib ko'ring.",
        "stale": "Bu tugma eskirgan. «Obunalar» ni qayta oching.",
        "ok": "✅ <b>Yuborildi!</b>\n\n{what}\n👤 @{u}\n\n💳 Hisobingiz: {bal}",
        "failed": "❌ <b>Buyurtma bajarilmadi</b>\n\n{why}\n\n💰 Pul hisobingizga qaytarildi. 💳 Hisobingiz: {bal}",
        "unknown": ("⏳ <b>Buyurtma tekshirilmoqda</b>\n\n{what}\n👤 @{u}\n\nNatija hali aniq emas. Administrator tekshirib, "
                    "tez orada hal qiladi. Qaytadan buyurtma bermang.\n💳 Hisobingiz: {bal}"),
        "not_enough": "❌ Hisobingizda mablag' yetarli emas.\n\n💵 Kerak: {need}\n💳 Mavjud: {have}\n➕ Yetmaydi: {diff}",
        "topup": "Hisobni to'ldirish",
        "reason": {"006": "Bunday @username topilmadi. Username'ni tekshirib, qayta urinib ko'ring."},
        "generic_fail": "Xizmat buyurtmani qabul qilmadi. Keyinroq urinib ko'ring.",
        "stars_what": "⭐ <b>{n} Telegram Stars</b>", "prem_what": "👑 <b>Telegram Premium · {n} oy</b>",
        "month_btn": "👑 {n} oy — {price}", "stars_btn": "⭐ {n} — {price}",
    },
    "ru": {
        "stars_title": "⭐ <b>Telegram Stars</b>\n\nВыберите количество или напишите своё ({lo}–{hi}).\n💵 1 Star ≈ <b>{unit}</b>",
        "prem_title": "👑 <b>Telegram Premium</b>\n\nВыберите срок:",
        "custom": "➕ Другое количество",
        "ask_amount": "💬 Напишите количество Stars ({lo}–{hi}):",
        "bad_amount": "❌ Количество — целое число от {lo} до {hi}.",
        "who": "👤 <b>Кому отправляем?</b>\n\n{what}",
        "me": "👤 Себе (@{u})", "other": "👤 Другому пользователю",
        "ask_target": "💬 Напишите <b>@username</b> получателя:",
        "bad_target": "❌ Неверный username. Пример: <code>@monk</code> (от 4 символов: латиница, цифры, _).",
        "no_username": "У вас нет username в Telegram. Выберите «Другому пользователю».",
        "confirm": ("{what}\n👤 Кому: <b>@{u}</b>\n\n💵 <b>Цена:</b> {price}\n💳 <b>Ваш счёт:</b> {bal}\n\n"
                    "⚠️ Проверьте username: отправленное не возвращается."),
        "price_changed": "⚠️ Цена обновилась. Подтвердите ещё раз.\n\n",
        "buy": "Купить", "cancel": "❌ Отмена", "cancelled": "Отменено.",
        "busy": "⏳ Заказ выполняется, подождите немного...",
        "unavailable": "⚠️ Сервис временно недоступен. Попробуйте позже.",
        "stale": "Кнопка устарела. Откройте «Подписки» заново.",
        "ok": "✅ <b>Отправлено!</b>\n\n{what}\n👤 @{u}\n\n💳 Ваш счёт: {bal}",
        "failed": "❌ <b>Заказ не выполнен</b>\n\n{why}\n\n💰 Деньги возвращены на счёт. 💳 Ваш счёт: {bal}",
        "unknown": ("⏳ <b>Заказ проверяется</b>\n\n{what}\n👤 @{u}\n\nРезультат пока неясен. Администратор проверит и решит. "
                    "Не заказывайте повторно.\n💳 Ваш счёт: {bal}"),
        "not_enough": "❌ Недостаточно средств.\n\n💵 Нужно: {need}\n💳 Есть: {have}\n➕ Не хватает: {diff}",
        "topup": "Пополнить счёт",
        "reason": {"006": "Такой @username не найден. Проверьте и попробуйте снова."},
        "generic_fail": "Сервис не принял заказ. Попробуйте позже.",
        "stars_what": "⭐ <b>{n} Telegram Stars</b>", "prem_what": "👑 <b>Telegram Premium · {n} мес.</b>",
        "month_btn": "👑 {n} мес. — {price}", "stars_btn": "⭐ {n} — {price}",
    },
}


def tx(lang: str, key: str, **kw):
    v = TX.get(lang, TX["uz"]).get(key, TX["uz"][key])
    return v.format(**kw) if kw and isinstance(v, str) else v


def entry_row(lang: str = "uz") -> list[InlineKeyboardButton]:
    """«Obunalar» ro'yxati tagidagi 2 ta tugma (kalit sozlangan bo'lsa)."""
    if not starsuno.configured():
        return []
    return [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="tg:stars", style=GREEN),
            InlineKeyboardButton(text="👑 Telegram Premium", callback_data="tg:prem", style=GREEN)]


def _what(lang: str, kind: str, qty: int) -> str:
    return tx(lang, "stars_what" if kind == "stars" else "prem_what", n=qty)


async def _quote(kind: str, qty: int) -> int:
    return await (starsuno.stars_price(qty) if kind == "stars" else starsuno.premium_price(qty))


async def _edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


def _back_row(lang: str, data: str = BACK) -> list[InlineKeyboardButton]:
    from locales.texts import t
    return [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=data, style=BLUE)]


# ─────────────────────────── Tanlash ───────────────────────────

@router.callback_query(F.data == "tg:stars")
async def stars_menu(call: CallbackQuery, lang: str, state: FSMContext):
    await state.clear()
    if not starsuno.configured():
        return await call.answer(tx(lang, "unavailable"), show_alert=True)
    try:
        unit = await starsuno.star_unit_price()
        prices = {n: await starsuno.stars_price(n) for n in PRESETS}
    except starsuno.SupplierError as ex:
        await _supplier_down(call.bot, ex)
        return await call.answer(tx(lang, "unavailable"), show_alert=True)
    btns = [InlineKeyboardButton(text=tx(lang, "stars_btn", n=n, price=money(p)), callback_data=f"tg:sa:{n}", style=GREEN)
            for n, p in prices.items()]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton(text=tx(lang, "custom"), callback_data="tg:sa:x", style=BLUE)])
    rows.append(_back_row(lang))
    unit_sell = math.ceil(unit * (1 + starsuno.markup_percent() / 100))
    text = tx(lang, "stars_title", lo=starsuno.MIN_STARS, hi=starsuno.MAX_STARS, unit=money(unit_sell))
    await _edit(call, text, InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "tg:prem")
async def prem_menu(call: CallbackQuery, lang: str, state: FSMContext):
    await state.clear()
    if not starsuno.configured():
        return await call.answer(tx(lang, "unavailable"), show_alert=True)
    try:
        months = sorted(await starsuno.premium_prices())
        prices = {m: await starsuno.premium_price(m) for m in months}
    except starsuno.SupplierError as ex:
        await _supplier_down(call.bot, ex)
        return await call.answer(tx(lang, "unavailable"), show_alert=True)
    rows = [[InlineKeyboardButton(text=tx(lang, "month_btn", n=m, price=money(p)), callback_data=f"tg:pm:{m}", style=GREEN)]
            for m, p in prices.items()]
    rows.append(_back_row(lang))
    await _edit(call, tx(lang, "prem_title"), InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


async def _ask_who(target: CallbackQuery | Message, user: User, lang: str, state: FSMContext, kind: str, qty: int) -> None:
    await state.set_state(None)
    await state.update_data(kind=kind, qty=qty)
    rows = []
    if user.username:
        rows.append([InlineKeyboardButton(text=tx(lang, "me", u=user.username), callback_data="tg:me", style=GREEN)])
    rows.append([InlineKeyboardButton(text=tx(lang, "other"), callback_data="tg:other", style=BLUE)])
    rows.append(_back_row(lang, "tg:stars" if kind == "stars" else "tg:prem"))
    text = tx(lang, "who", what=_what(lang, kind, qty))
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(target, CallbackQuery):
        await _edit(target, text, kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data.regexp(r"^tg:sa:\d+$"))
async def stars_amount(call: CallbackQuery, user: User, lang: str, state: FSMContext):
    n = int(call.data.split(":")[2])
    if not starsuno.MIN_STARS <= n <= starsuno.MAX_STARS:
        return await call.answer(tx(lang, "stale"), show_alert=True)
    await _ask_who(call, user, lang, state, "stars", n)


@router.callback_query(F.data == "tg:sa:x")
async def stars_custom(call: CallbackQuery, lang: str, state: FSMContext):
    await state.set_state(TG.amount)
    await call.message.answer(tx(lang, "ask_amount", lo=starsuno.MIN_STARS, hi=starsuno.MAX_STARS))
    await call.answer()


@router.message(TG.amount, F.text)
async def stars_amount_text(message: Message, user: User, lang: str, state: FSMContext):
    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit() or not starsuno.MIN_STARS <= int(raw) <= starsuno.MAX_STARS:
        return await message.answer(tx(lang, "bad_amount", lo=starsuno.MIN_STARS, hi=starsuno.MAX_STARS))
    await _ask_who(message, user, lang, state, "stars", int(raw))


@router.callback_query(F.data.regexp(r"^tg:pm:\d+$"))
async def prem_month(call: CallbackQuery, user: User, lang: str, state: FSMContext):
    m = int(call.data.split(":")[2])
    if m not in starsuno.MONTHS:
        return await call.answer(tx(lang, "stale"), show_alert=True)
    await _ask_who(call, user, lang, state, "premium", m)


# ─────────────────────────── Kimga + tasdiqlash ───────────────────────────

async def _confirm_view(user: User, lang: str, kind: str, qty: int, target: str, note: str = "") -> tuple[str, InlineKeyboardMarkup, int]:
    price = await _quote(kind, qty)
    text = note + tx(lang, "confirm", what=_what(lang, kind, qty), u=html.escape(target), price=money(price), bal=money(user.balance))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [green_button(tx(lang, "buy"), None, "🛒", callback_data="tg:ok")],
        [InlineKeyboardButton(text=tx(lang, "cancel"), callback_data="tg:no", style=RED)],
    ])
    return text, kb, price


@router.callback_query(F.data == "tg:me")
async def to_me(call: CallbackQuery, user: User, lang: str, state: FSMContext):
    data = await state.get_data()
    name = starsuno.valid_username(user.username or "")
    if not data.get("kind") or not name:
        return await call.answer(tx(lang, "no_username") if data.get("kind") else tx(lang, "stale"), show_alert=True)
    await _show_confirm_cb(call, user, lang, state, data, name)


@router.callback_query(F.data == "tg:other")
async def to_other(call: CallbackQuery, lang: str, state: FSMContext):
    data = await state.get_data()
    if not data.get("kind"):
        return await call.answer(tx(lang, "stale"), show_alert=True)
    await state.set_state(TG.target)
    await call.message.answer(tx(lang, "ask_target"))
    await call.answer()


@router.message(TG.target, F.text)
async def target_text(message: Message, user: User, lang: str, state: FSMContext):
    name = starsuno.valid_username(message.text or "")
    if not name:
        return await message.answer(tx(lang, "bad_target"))
    data = await state.get_data()
    if not data.get("kind"):
        await state.clear()
        return await message.answer(tx(lang, "stale"))
    try:
        text, kb, price = await _confirm_view(user, lang, data["kind"], data["qty"], name)
    except starsuno.SupplierError:
        return await message.answer(tx(lang, "unavailable"))
    await state.set_state(None)
    await state.update_data(target=name, price=price)
    await message.answer(text, reply_markup=kb)


async def _show_confirm_cb(call, user, lang, state, data, name) -> None:
    try:
        text, kb, price = await _confirm_view(user, lang, data["kind"], data["qty"], name)
    except starsuno.SupplierError:
        return await call.answer(tx(lang, "unavailable"), show_alert=True)
    await state.update_data(target=name, price=price)
    await _edit(call, text, kb)
    await call.answer()


@router.callback_query(F.data == "tg:no")
async def cancel(call: CallbackQuery, lang: str, state: FSMContext):
    await state.clear()
    await _edit(call, tx(lang, "cancelled"))
    await call.answer()


# ─────────────────────────── Bajarish ───────────────────────────

@router.callback_query(F.data == "tg:ok")
async def confirm(call: CallbackQuery, session: AsyncSession, user: User, lang: str, state: FSMContext):
    data = await state.get_data()
    kind, qty, target, quoted = data.get("kind"), data.get("qty"), data.get("target"), data.get("price")
    if not (kind and qty and target and quoted):
        await state.clear()
        return await call.answer(tx(lang, "stale"), show_alert=True)
    await state.clear()                       # ikki marta bosilsa ikkinchisi «eskirgan» bo'ladi — ikki marta yuborilmaydi
    try:
        price = await _quote(kind, qty)
    except starsuno.SupplierError:
        return await call.answer(tx(lang, "unavailable"), show_alert=True)
    if price != quoted:                       # narx o'zgargan: yangi narxni ko'rsatib, qayta tasdiqlatamiz
        text, kb, price = await _confirm_view(user, lang, kind, qty, target, tx(lang, "price_changed"))
        await state.update_data(kind=kind, qty=qty, target=target, price=price)
        await _edit(call, text, kb)
        return await call.answer()
    await call.answer()
    await _execute(call.message, session, user, lang, kind, qty, target, price)


async def _execute(message: Message, session: AsyncSession, user: User, lang: str, kind: str, qty: int, target: str, price: int) -> None:
    bot = message.bot
    if user.balance < price:
        kb = InlineKeyboardMarkup(inline_keyboard=[[green_button(tx(lang, "topup"), None, "💳", callback_data="pay:menu")]])
        return await _edit_msg(message, tx(lang, "not_enough", need=money(price), have=money(user.balance), diff=money(price - user.balance)), kb)
    what_plain = f"{qty} Telegram Stars" if kind == "stars" else f"Telegram Premium · {qty} oy"
    order = Order(user_id=user.id, total=price, status=OrderStatus.PAID)
    session.add(order)
    await session.flush()
    item = OrderItem(order_id=order.id, product_id=None, product_name=f"{'⭐' if kind == 'stars' else '👑'} {what_plain}",
                     price=price, qty=1, status="pending", customer_input=f"@{target}")
    session.add(item)
    user.balance -= price
    await session.commit()                     # pul yechildi va buyurtma yozildi — tashqi so'rovdan OLDIN
    await _edit_msg(message, tx(lang, "busy"))

    res = await (starsuno.buy_stars(target, qty) if kind == "stars" else starsuno.buy_premium(target, qty))
    what = _what(lang, kind, qty)
    if res.kind == "ok":
        item.status, item.delivered_content = "ok", f"@{target} ← {what_plain}"
        order.status = OrderStatus.DELIVERED
        await session.commit()
        await _edit_msg(message, tx(lang, "ok", what=what, u=html.escape(target), bal=money(user.balance)))
        await _after_ok(bot, user, order, what_plain, target, res)
    elif res.kind == "failed":
        user.balance += price
        order.total -= price
        item.status, item.delivered_content = "failed", ""
        order.status = OrderStatus.CANCELLED
        await session.commit()
        why = tx(lang, "reason").get(res.code) or tx(lang, "generic_fail")
        await _edit_msg(message, tx(lang, "failed", why=why, bal=money(user.balance)))
        if res.code in starsuno.ADMIN_CODES or not res.code:
            src = starsuno.NAMES[starsuno.provider_key()]
            await _alert(bot, f"⚠️ <b>{src}: buyurtma rad etildi</b> (#{order.id})\n{html.escape(res.message)}"
                              + (f"\n💳 {src} hisobini (hamyonini) to'ldiring!" if res.code == "003" else
                                 f"\n🔑 {src} sozlamalarini (.env dagi kalit/cookie) tekshiring." if res.code in ("001", "002") else ""))
    else:
        await session.commit()                 # pending, pul qaytarilmaydi
        await _edit_msg(message, tx(lang, "unknown", what=what, u=html.escape(target), bal=money(user.balance)))
        await _alert(bot, f"❓ <b>{starsuno.NAMES[starsuno.provider_key()]}: natija noma'lum</b> — buyurtma #{order.id}\n"
                          f"👤 {html.escape(user.full_name or '—')} (<code>{user.tg_id}</code>)\n"
                          f"📦 {html.escape(what_plain)} → @{html.escape(target)} · {money(price)}\n"
                          f"⚠️ {html.escape(res.message or '—')} {('(' + res.code + ')') if res.code else ''}\n\n"
                          "Pul <b>qaytarilmadi</b> (yuborilgan bo'lishi mumkin). Fragment hamyoni tarixini (Tonkeeper) va @{} ni tekshiring. "
                          "Yuborilmagan bo'lsa — «💰 ID bilan hisob to'ldirish» orqali mijozga pulini qaytaring.".format(html.escape(target)))


async def _edit_msg(msg: Message, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await msg.answer(text, reply_markup=kb)


_last_down_alert = 0.0


async def _supplier_down(bot, ex: Exception) -> None:
    """Mijoz «xizmat ishlamayapti» ko'rdi — adminga aniq sabab (30 daqiqada bir marta)."""
    global _last_down_alert
    log.warning("Stars/Premium narxini olib bo'lmadi: %s", ex)
    if time.monotonic() - _last_down_alert < 1800 and _last_down_alert:
        return
    _last_down_alert = time.monotonic()
    await _alert(bot, f"⚠️ <b>Fragment ishlamayapti — Stars/Premium sotilmayapti</b> (mijoz «xizmat ishlamayapti» ko'rdi).\n"
                      f"Sabab: {html.escape(str(ex))}\n\nTekshirish: ⚙️ Admin panel → ⭐ Stars / Premium → 📊 Holat va narxlar.")


async def _alert(bot, text: str) -> None:
    try:
        await alerts.broadcast(bot, text)
    except Exception:  # noqa: BLE001 — ogohlantirish yuborilmasa ham buyurtma oqimi buzilmasin
        log.exception("Admin ogohlantirishi yuborilmadi")


async def _after_ok(bot, user: User, order: Order, what_plain: str, target: str, res) -> None:
    """Adminga savdo xabari va Fragment hamyonida TON kamayib qolsa ogohlantirish (6 soatda bir marta)."""
    global _last_low_alert
    await _alert(bot, f"⭐ <b>Savdo #{order.id}</b>: {html.escape(what_plain)} → @{html.escape(target)}\n"
                      f"👤 {html.escape(user.full_name or '—')} (<code>{user.tg_id}</code>) · {money(order.total)}")
    if _last_low_alert is not None and time.monotonic() - _last_low_alert < 6 * 3600:
        return
    ton = await fragment_tg.wallet_ton()
    if ton is not None and ton < LOW_TON:
        _last_low_alert = time.monotonic()
        await _alert(bot, f"⚠️ <b>Fragment hamyonida TON kam: {ton:g} TON</b>\n"
                          "Tonkeeper hamyoniga TON tashlang, aks holda Stars/Premium buyurtmalari bajarilmaydi.")
