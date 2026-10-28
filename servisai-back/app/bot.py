"""Telegram bot: do‘kon (sotib olish, hisob, buyurtmalar, do‘st taklif qilish) va saytga kirishni tasdiqlash.

Ishga tushirish: python -m app.bot
"""

import asyncio
import html
import logging
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.types import User as TgUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .accounts import AccountConflict, upsert_telegram_user
from .config import settings
from .database import SessionLocal
from .models import Order, OrderStatus, Product, TelegramLoginSession, TelegramLoginStatus, TopUp, User
from .notify import STATUS_LABELS, duration_label, format_price, notify_order_created, notify_topup_result
from .referrals import bot_link, ensure_code, friends_count, grant_rewards, notify_grants, notify_referral
from .schemas import MAX_ORDER_QUANTITY
from .shop import ShopError, place_order
from .stock import attach_sold_counts
from .topups import MAX_RECEIPT_SIZE, TopUpError, check_amount, submit_topup, topup_enabled
from .wallet import TopUpAlreadyReviewed, review_topup

log = logging.getLogger("servisai.bot")
dp = Dispatcher()

SUPPORT_URL = "https://t.me/fen1xmedia"
QUICK_AMOUNTS = [50_000, 100_000, 200_000, 500_000]
TOPUP_STATUS = {"pending": "⏳ tekshirilmoqda", "approved": "✅ tasdiqlandi", "rejected": "❌ rad etildi"}

CONTACT_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


class TopUpFlow(StatesGroup):
    amount = State()  # "Boshqa summa" — foydalanuvchi summani yozadi
    receipt = State()  # chek rasmi kutilmoqda


# ---------- Yordamchilar ----------


def site_url(path: str = "/") -> str | None:
    url = settings.frontend_url.rstrip("/") + path
    # Telegram localhost havolalarini qabul qilmaydi
    return None if url.startswith("http://localhost") or url.startswith("http://127.") else url


def site_button(text: str = "🌐 Saytga qaytish", path: str = "/profil") -> InlineKeyboardMarkup | None:
    url = site_url(path)
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]]) if url else None


def kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r])


def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


BACK = [btn("⬅️ Asosiy menyu", "m:home")]


async def get_user(session: AsyncSession, tg: TgUser, ref_code: str | None = None) -> User:
    """Bot foydalanuvchisini topadi yoki yaratadi (botdan ham to‘liq foydalanish mumkin)."""
    user = await session.scalar(select(User).where(User.telegram_id == tg.id))
    if user is None:
        user = await upsert_telegram_user(
            session, telegram_id=tg.id, first_name=tg.first_name, last_name=tg.last_name, username=tg.username, ref_code=ref_code
        )
        await session.commit()
        await notify_referral(user)
    return user


async def show(target: Message | CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Tugma bosilganda xabarni joyida yangilaydi, aks holda yangi xabar yuboradi."""
    if isinstance(target, CallbackQuery):
        await target.answer()
        try:
            await target.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
            return
        except Exception:  # xabar o‘zgarmagan yoki rasm bilan — yangisini yuboramiz
            await target.message.answer(text, reply_markup=markup, disable_web_page_preview=True)
            return
    await target.answer(text, reply_markup=markup, disable_web_page_preview=True)


# ---------- Asosiy menyu ----------


def menu_markup() -> InlineKeyboardMarkup:
    site = site_url("/")
    return kb(
        [btn("🛍 Sotib olish", "m:buy"), btn("📦 Buyurtmalarim", "m:orders")],
        [btn("💰 Hisobim", "m:wallet"), btn("🎁 Do‘st taklif qilish", "m:ref")],
        [btn("👤 Profil", "m:profile"), btn("❓ Qanday ishlaydi", "m:how")],
        [InlineKeyboardButton(text="🆘 Yordam", url=SUPPORT_URL)]
        + ([InlineKeyboardButton(text="🌐 Sayt", url=site)] if site else []),
    )


def menu_text(user: User) -> str:
    return (
        f"👋 Xush kelibsiz, <b>{html.escape(user.full_name or 'do‘stim')}</b>!\n"
        "<i>Premium raqamli obunalar — tez, ishonchli va arzon.</i>\n\n"
        f"💰 Balans: <code>{format_price(user.balance)} so‘m</code>\n\n"
        "⚡ Tez yetkazish · ✅ Rasmiy hisoblar · 🤝 24/7 yordam\n"
        "💳 Uzcard · Humo · Click/Payme <i>(tez kunda)</i>\n\n"
        "Quyidagi bo‘limlardan birini tanlang 👇"
    )


async def send_menu(target: Message | CallbackQuery, tg: TgUser, ref_code: str | None = None) -> None:
    async with SessionLocal() as session:
        user = await get_user(session, tg, ref_code)
        text = menu_text(user)
    await show(target, text, menu_markup())


async def confirm_login(message: Message, token: str) -> None:
    """Saytdagi «Telegram orqali kirish»: bir martalik token bilan kelgan /start."""
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
                ref_code=login.ref_code,
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
    await notify_referral(user)

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
async def start_with_args(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    args = command.args or ""
    if args.lower().startswith("ref_"):
        # Do‘st taklif havolasi: t.me/<bot>?start=ref_KOD
        await send_menu(message, message.from_user, ref_code=args)
    else:
        await confirm_login(message, args)


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_menu(message, message.from_user)


@dp.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_menu(message, message.from_user)


@dp.callback_query(F.data == "m:home")
async def home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_menu(callback, callback.from_user)


# ---------- Sotib olish ----------


def product_cb(prefix: str, product_id: str, qty: int | None = None) -> str | None:
    data = f"{prefix}:{product_id}" + (f":{qty}" if qty is not None else "")
    # Telegram callback_data 64 baytdan oshmasligi kerak
    return data if len(data.encode()) <= 64 else None


@dp.callback_query(F.data == "m:buy")
async def buy_list(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        products = (
            await session.scalars(select(Product).where(Product.is_active).order_by(Product.sort_order, Product.name))
        ).all()
    rows = []
    for p in products:
        data = product_cb("p", p.id)
        label = f"{'❌ ' if p.stock == 0 else ''}{p.name} — {format_price(p.price)} so‘m"
        if data:
            rows.append([btn(label, data)])
    text = "🛍 <b>Servislar</b>\n\nKerakli servisni tanlang:" if rows else "Hozircha servislar yo‘q."
    await show(callback, text, kb(*rows, BACK))


async def product_view(target: CallbackQuery, product_id: str, qty: int) -> None:
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if product is None or not product.is_active:
            await target.answer("Servis topilmadi", show_alert=True)
            return
        await attach_sold_counts(session, [product])
    p = product
    max_qty = min(p.stock if p.stock is not None else MAX_ORDER_QUANTITY, MAX_ORDER_QUANTITY)
    qty = max(1, min(qty, max_qty)) if max_qty > 0 else 1

    price = f"<b>{format_price(p.price)} so‘m</b> / {duration_label(p.durations[0], p.duration_unit)}"
    if p.old_price:
        discount = round((1 - p.price / p.old_price) * 100)
        price += f"  <s>{format_price(p.old_price)}</s>  🔥 −{discount}%"
    lines = [f"<b>{html.escape(p.name)}</b>"]
    if p.description:
        lines.append(html.escape(p.description))
    lines.append("")
    lines.append(f"💵 Narx: {price}")
    lines.append(f"⏱ Yetkazish: {'⚡ darhol, avtomatik' if p.instant_delivery else html.escape(p.delivery_time)}")
    if p.stock is not None:
        lines.append("📦 <b>Tugagan</b>" if p.stock == 0 else f"📦 Qoldi: {p.stock} ta")
    if p.sold_count:
        lines.append(f"🛒 Sotilgan: {p.sold_count} ta")
    if p.features:
        lines.append("\n✨ <b>Nimalar kiradi:</b>")
        lines += [f"• {html.escape(f)}" for f in p.features]
    if p.notes.strip():
        lines.append("\n⚠️ <b>Muhim:</b>")
        lines += [html.escape(n.strip()) for n in p.notes.split("\n") if n.strip()]

    rows = []
    if p.stock == 0:
        rows.append([InlineKeyboardButton(text="🆘 Admin bilan bog‘lanish", url=SUPPORT_URL)])
    else:
        minus, plus, buy = product_cb("q", p.id, qty - 1), product_cb("q", p.id, qty + 1), product_cb("b", p.id, qty)
        rows.append([btn("➖", minus or "noop"), btn(f"{qty} ta", "noop"), btn("➕", plus or "noop")])
        rows.append([btn(f"✅ Sotib olish — {format_price(p.price * qty)} so‘m", buy or "noop")])
    rows.append([btn("⬅️ Servislar", "m:buy"), btn("🏠 Menyu", "m:home")])
    await show(target, "\n".join(lines), kb(*rows))


@dp.callback_query(F.data.startswith("p:"))
async def product_open(callback: CallbackQuery) -> None:
    await product_view(callback, callback.data[2:], 1)


@dp.callback_query(F.data.startswith("q:"))
async def product_qty(callback: CallbackQuery) -> None:
    product_id, raw = callback.data[2:].rsplit(":", 1)
    await product_view(callback, product_id, int(raw))


@dp.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@dp.callback_query(F.data.startswith("b:"))
async def buy_confirm(callback: CallbackQuery) -> None:
    product_id, raw = callback.data[2:].rsplit(":", 1)
    qty = int(raw)
    async with SessionLocal() as session:
        user = await get_user(session, callback.from_user)
        product = await session.get(Product, product_id)
    if product is None or not product.is_active:
        await callback.answer("Servis topilmadi", show_alert=True)
        return
    total = product.price * qty
    text = (
        "🧾 <b>Buyurtmani tasdiqlang</b>\n\n"
        f"{html.escape(product.name)} × {qty} ta\n"
        f"Jami: <b>{format_price(total)} so‘m</b>\n"
        f"Balansingiz: {format_price(user.balance)} so‘m"
    )
    if user.balance < total:
        text += f"\n\n⚠️ Hisobingizda yana <b>{format_price(total - user.balance)} so‘m</b> yetishmayapti."
        markup = kb([btn("💳 Hisobni to‘ldirish", "m:wallet")], [btn("⬅️ Orqaga", product_cb("q", product_id, qty) or "m:buy")])
    else:
        markup = kb(
            [btn("✅ Tasdiqlash va to‘lash", product_cb("ok", product_id, qty) or "noop")],
            [btn("⬅️ Orqaga", product_cb("q", product_id, qty) or "m:buy")],
        )
    await show(callback, text, markup)


@dp.callback_query(F.data.startswith("ok:"))
async def buy_place(callback: CallbackQuery) -> None:
    product_id, raw = callback.data[3:].rsplit(":", 1)
    qty = int(raw)
    await callback.answer("⏳ Bajarilmoqda...")
    async with SessionLocal() as session:
        user = await get_user(session, callback.from_user)
        product = await session.get(Product, product_id)
        if product is None:
            await show(callback, "Servis topilmadi.", kb(BACK))
            return
        delivery_time = product.delivery_time
        try:
            order = await place_order(session, user, product, quantity=qty)
        except ShopError as e:
            markup = kb([btn("💳 Hisobni to‘ldirish", "m:wallet")], BACK) if e.need_topup else kb([btn("⬅️ Servislar", "m:buy")], BACK)
            await show(callback, f"⚠️ {html.escape(e.message)}", markup)
            return
        await session.commit()
        await session.refresh(order)
        user = await session.get(User, user.id)

    if order.status == OrderStatus.completed and order.delivery_info:
        items = "\n".join(f"<code>{html.escape(line)}</code>" for line in order.delivery_info.split("\n"))
        text = (
            f"🎉 <b>Tabriklaymiz! Buyurtmangiz tayyor</b>\n\n{html.escape(order.product_name)}"
            f"{f' × {order.quantity}' if order.quantity > 1 else ''} · {order.number}\n\n"
            f"📦 <b>Sizning ma’lumotlaringiz</b> (bosib nusxalang):\n{items}\n\n"
            f"💰 Qolgan balans: {format_price(user.balance)} so‘m"
        )
    else:
        text = (
            f"✅ <b>Buyurtma qabul qilindi!</b> {order.number}\n\n"
            f"{html.escape(order.product_name)}{f' × {order.quantity}' if order.quantity > 1 else ''} — {format_price(order.price)} so‘m\n\n"
            f"⏱ Yetkazib berish vaqti: <b>{html.escape(delivery_time)}</b>\n"
            "Tayyor bo‘lgach ma’lumotlarni shu yerga va saytdagi «Buyurtmalarim» bo‘limiga yuboramiz.\n\n"
            f"💰 Qolgan balans: {format_price(user.balance)} so‘m"
        )
    await show(callback, text, kb([btn("📦 Buyurtmalarim", "m:orders"), btn("🛍 Yana xarid", "m:buy")], BACK))
    # Mijoz natijani shu yerda ko‘rdi — Telegram xabari faqat adminga
    await notify_order_created(order, user, delivery_time, notify_user=False)


# ---------- Buyurtmalar ----------


async def orders_view(target: Message | CallbackQuery, tg: TgUser) -> None:
    async with SessionLocal() as session:
        user = await get_user(session, tg)
        orders = (
            await session.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(10))
        ).all()
    if not orders:
        await show(target, "📦 Sizda hali buyurtmalar yo‘q.", kb([btn("🛍 Sotib olish", "m:buy")], BACK))
        return
    blocks = []
    for o in orders:
        block = (
            f"<b>{o.number}</b> · {html.escape(o.product_name)}{f' × {o.quantity}' if o.quantity > 1 else ''}"
            f" · {format_price(o.price)} so‘m\n{STATUS_LABELS[o.status]}"
        )
        if o.delivery_info:
            block += "\n" + "\n".join(f"<code>{html.escape(line)}</code>" for line in o.delivery_info.split("\n")[:5])
        blocks.append(block)
    site = site_url("/profil?tab=buyurtmalar")
    await show(
        target,
        "📦 <b>Oxirgi buyurtmalaringiz</b>\n\n" + "\n\n".join(blocks),
        kb([InlineKeyboardButton(text="📋 Saytda barchasi", url=site)] if site else [], BACK),
    )


@dp.callback_query(F.data == "m:orders")
async def orders_cb(callback: CallbackQuery) -> None:
    await orders_view(callback, callback.from_user)


@dp.message(Command("orders"))
async def orders_cmd(message: Message) -> None:
    await orders_view(message, message.from_user)


# ---------- Hisob va to‘ldirish ----------


async def wallet_view(target: Message | CallbackQuery, tg: TgUser) -> None:
    async with SessionLocal() as session:
        user = await get_user(session, tg)
        topups = (
            await session.scalars(select(TopUp).where(TopUp.user_id == user.id).order_by(TopUp.created_at.desc()).limit(3))
        ).all()
    text = f"💰 <b>Hisobim</b>\n\nBalans: <b>{format_price(user.balance)} so‘m</b>\nXaridlar shu hisobdan to‘lanadi."
    if topups:
        text += "\n\n<b>Oxirgi to‘ldirishlar:</b>\n" + "\n".join(
            f"• {format_price(t.amount)} so‘m — {TOPUP_STATUS[t.status.value]}" for t in topups
        )
    if not topup_enabled():
        await show(target, text + "\n\nHisobni to‘ldirish hozircha mavjud emas.", kb(BACK))
        return
    text += "\n\n➕ <b>Hisobni to‘ldirish</b> — summani tanlang:\n<i>Click / Payme orqali avtomatik to‘lov — tez kunda</i>"
    amounts = [btn(format_price(a), f"t:{a}") for a in QUICK_AMOUNTS]
    await show(target, text, kb(amounts[:2], amounts[2:], [btn("✍️ Boshqa summa", "t:other")], BACK))


@dp.callback_query(F.data == "m:wallet")
async def wallet_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await wallet_view(callback, callback.from_user)


@dp.message(Command("balans", "balance"))
async def wallet_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await wallet_view(message, message.from_user)


async def ask_receipt(target: Message | CallbackQuery, state: FSMContext, amount: int) -> None:
    await state.set_state(TopUpFlow.receipt)
    await state.update_data(amount=amount)
    card = settings.payment_card_number or "—"
    holder = f"\n{html.escape(settings.payment_card_holder)}" if settings.payment_card_holder else ""
    await show(
        target,
        f"💳 <b>{format_price(amount)} so‘m</b> ni quyidagi kartaga o‘tkazing:\n\n"
        f"<code>{html.escape(card)}</code>{holder}\n<i>(raqamni bosib nusxalang)</i>\n\n"
        "📸 So‘ng <b>chek rasmini</b> (skrinshot yoki PDF) shu yerga yuboring.\n"
        "Admin tekshirgach, mablag‘ hisobingizga tushadi.",
        kb([btn("❌ Bekor qilish", "m:wallet")]),
    )


@dp.callback_query(F.data.startswith("t:"))
async def topup_amount(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data[2:]
    if value == "other":
        await state.set_state(TopUpFlow.amount)
        await show(
            callback,
            f"✍️ Summani yozing (so‘mda), masalan: <code>150000</code>\n"
            f"Eng kami: {format_price(settings.topup_min_amount)} so‘m",
            kb([btn("❌ Bekor qilish", "m:wallet")]),
        )
        return
    await ask_receipt(callback, state, int(value))


@dp.message(TopUpFlow.amount, F.text)
async def topup_custom_amount(message: Message, state: FSMContext) -> None:
    digits = "".join(ch for ch in message.text if ch.isdigit())
    try:
        amount = int(digits)
        check_amount(amount)
    except ValueError:
        await message.answer("Iltimos, summani raqam bilan yozing, masalan: 150000")
        return
    except TopUpError as e:
        await message.answer(f"⚠️ {e.message}")
        return
    await ask_receipt(message, state, amount)


@dp.message(TopUpFlow.receipt, F.photo | F.document)
async def topup_receipt(message: Message, state: FSMContext) -> None:
    amount = (await state.get_data()).get("amount")
    if message.photo:
        file_id, content_type, size = message.photo[-1].file_id, "image/jpeg", message.photo[-1].file_size
    else:
        file_id, content_type, size = message.document.file_id, message.document.mime_type, message.document.file_size
    if size and size > MAX_RECEIPT_SIZE:
        await message.answer("⚠️ Chek hajmi 10 MB dan oshmasligi kerak.")
        return
    buffer = await message.bot.download(file_id, destination=BytesIO())
    async with SessionLocal() as session:
        user = await get_user(session, message.from_user)
        try:
            await submit_topup(session, user, amount, buffer.getvalue(), content_type)
        except TopUpError as e:
            await message.answer(f"⚠️ {e.message}")
            return
    await state.clear()
    await message.answer(
        f"✅ <b>Chek yuborildi!</b>\n\n{format_price(amount)} so‘m — admin tekshirmoqda. "
        "Tasdiqlangach, shu yerga xabar keladi va mablag‘ hisobingizga tushadi.",
        reply_markup=kb(BACK),
    )


@dp.message(TopUpFlow.receipt)
async def topup_receipt_wrong(message: Message) -> None:
    await message.answer("📸 Iltimos, to‘lov chekining <b>rasmini</b> yoki PDF faylini yuboring.", reply_markup=kb([btn("❌ Bekor qilish", "m:wallet")]))


# ---------- Do‘st taklif qilish ----------


async def referral_view(target: Message | CallbackQuery, tg: TgUser) -> None:
    from .routers.referrals import _rewards  # sayt API bilan bir xil hisob

    async with SessionLocal() as session:
        user = await get_user(session, tg)
        code = await ensure_code(session, user)
        await session.commit()
        count = await friends_count(session, user.id)
        rewards = await _rewards(session, user, count)
    link = bot_link(code) or ""
    lines = [
        "🎁 <b>Do‘stlaringizni taklif qiling va sovg‘a oling!</b>\n",
        "Sizning shaxsiy havolangiz:",
        f"<code>{html.escape(link)}</code>",
        "",
        f"👥 Taklif qilgan do‘stlaringiz: <b>{count} ta</b>",
    ]
    if rewards:
        lines.append("\n<b>Sovg‘alar:</b>")
        for r in rewards:
            mark = "✅" if r.granted else ("🎉" if r.achieved else "⏳")
            state = "olindi" if r.granted else ("olish mumkin!" if r.achieved else f"{min(count, r.required_friends)}/{r.required_friends}")
            lines.append(f"{mark} {r.required_friends} ta do‘st → <b>{html.escape(r.product_name)}</b>" f"{f' × {r.quantity}' if r.quantity > 1 else ''} — {state}")
    else:
        lines.append("\nSovg‘alar tez orada e’lon qilinadi.")
    lines.append("\nDo‘stingiz havola orqali botga yoki saytga birinchi marta kirsa, sizga hisoblanadi.")
    share = f"https://t.me/share/url?url={quote(link)}&text={quote('servisai.uz — premium AI servislar arzon narxda! 🎁')}"
    rows = [[InlineKeyboardButton(text="📤 Do‘stlarga ulashish", url=share)]] if link else []
    if any(r.achieved and not r.granted for r in rewards):
        rows.append([btn("🎁 Sovg‘ani olish", "claim")])
    await show(target, "\n".join(lines), kb(*rows, BACK))


@dp.callback_query(F.data == "m:ref")
async def referral_cb(callback: CallbackQuery) -> None:
    await referral_view(callback, callback.from_user)


@dp.callback_query(F.data == "claim")
async def claim_cb(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user(session, callback.from_user)
        _, grants = await grant_rewards(session, user)
        await session.commit()
    if not grants:
        await callback.answer("Hozircha olinadigan sovg‘a yo‘q", show_alert=True)
        return
    await callback.answer("🎉 Sovg‘a berildi!")
    await notify_grants(user, grants)
    await referral_view(callback.message, callback.from_user)


# ---------- Profil va ma’lumot ----------


@dp.callback_query(F.data == "m:profile")
async def profile_cb(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_user(session, callback.from_user)
        orders = await session.scalar(select(func.count(Order.id)).where(Order.user_id == user.id))
        friends = await friends_count(session, user.id)
    text = (
        "👤 <b>Profil</b>\n\n"
        f"Ism: {html.escape(user.full_name or '—')}\n"
        + (f"Telegram: @{html.escape(user.telegram_username)}\n" if user.telegram_username else "")
        + f"Telefon: {html.escape(user.phone) if user.phone else '—'}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ro‘yxatdan o‘tgan: {user.created_at:%d.%m.%Y}\n\n"
        f"💰 Balans: {format_price(user.balance)} so‘m\n"
        f"📦 Buyurtmalar: {orders} ta\n"
        f"👥 Taklif qilgan do‘stlar: {friends} ta"
    )
    rows = [] if user.phone else [[btn("📱 Telefon raqamni qo‘shish", "phone")]]
    await show(callback, text, kb(*rows, BACK))


@dp.callback_query(F.data == "phone")
async def phone_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Pastdagi tugma orqali raqamingizni yuboring 👇", reply_markup=CONTACT_KEYBOARD)


@dp.callback_query(F.data == "m:how")
async def how_cb(callback: CallbackQuery) -> None:
    await show(
        callback,
        "❓ <b>Qanday ishlaydi?</b>\n\n"
        "1️⃣ <b>Hisobni to‘ldiring</b> — «💰 Hisobim» bo‘limida summani tanlab, kartaga o‘tkazing va chekni yuboring.\n"
        "2️⃣ <b>Servisni tanlang</b> — «🛍 Sotib olish» bo‘limidan kerakli servis va sonini tanlang.\n"
        "3️⃣ <b>Ma’lumotni oling</b> — avtomatik servislar darhol, qolganlari odatda 10 daqiqa – 1 soat ichida yetkaziladi.\n\n"
        "🎁 Do‘stlaringizni taklif qilsangiz — bepul servislar sovg‘a!",
        kb([btn("🛍 Sotib olish", "m:buy"), btn("💰 Hisobim", "m:wallet")], BACK),
    )


@dp.message(F.contact)
async def save_contact(message: Message) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o‘zingizning raqamingizni yuboring.")
        return
    async with SessionLocal() as session:
        user = await get_user(session, message.from_user)
        phone = message.contact.phone_number
        user.phone = phone if phone.startswith("+") else f"+{phone}"
        await session.commit()
    await message.answer("📱 Raqamingiz saqlandi. Rahmat!", reply_markup=ReplyKeyboardRemove())
    await send_menu(message, message.from_user)


# ---------- Admin: chekni tasdiqlash ----------


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_telegram_id_list or str(user_id) == settings.telegram_admin_chat_id.strip()


@dp.callback_query(F.data.startswith("topup:"))
async def review_topup_callback(callback: CallbackQuery) -> None:
    """Admin chatidagi chek ostidagi «Tasdiqlash / Rad etish» tugmalari."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda bu amal uchun ruxsat yo‘q", show_alert=True)
        return
    _, action, raw_id = callback.data.split(":")
    approve = action == "approve"
    admin = callback.from_user
    reviewer = f"@{admin.username}" if admin.username else admin.full_name

    async with SessionLocal() as session:
        try:
            topup = await review_topup(session, int(raw_id), approve=approve, reviewer=reviewer)
        except LookupError:
            await callback.answer("So‘rov topilmadi", show_alert=True)
            return
        except TopUpAlreadyReviewed:
            await callback.answer("Bu so‘rov allaqachon ko‘rib chiqilgan", show_alert=True)
            await callback.message.edit_reply_markup(reply_markup=None)
            return
        await session.commit()
        user = await session.get(User, topup.user_id)

    result = (
        f"\n\n✅ <b>Tasdiqlandi</b> ({html.escape(reviewer)})\nYangi balans: {format_price(user.balance)} so‘m"
        if approve
        else f"\n\n❌ <b>Rad etildi</b> ({html.escape(reviewer)})"
    )
    caption = (callback.message.html_text or "") + result
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=None)
    except Exception:  # xabar juda eski yoki caption o‘zgarmagan bo‘lsa
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Tasdiqlandi" if approve else "Rad etildi")
    await notify_topup_result(topup, user)


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
