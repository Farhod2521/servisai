"""Admin panel (kengaytma): narx siyosati, buyurtmalar, foydalanuvchilar, premium emoji.

Asosiy kategoriya/mahsulot boshqaruvi handlers/admin.py da. Bu yerda:
  • 💹 foyda foizi va 💱 USD kursi (o'zgarsa barcha narxlar darhol qayta hisoblanadi);
  • 🧾 buyurtmalar: kutilayotganlarini qo'lda bajarish yoki pulni qaytarish;
  • 👥 foydalanuvchilar: qidirish, balans, bloklash;
  • 😀 premium emoji xaritasi.
"""
from __future__ import annotations

import html
import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from database.models import Order, OrderStatus, Product, User
from keyboards.admin_kb import admin_main
from locales.texts import money
from services import canboso, repo, runtime
from services.emoji import parse_emoji_pairs as emoji_pairs, premium_active

router = Router(name="admin_ext")
log = logging.getLogger(__name__)


def _is_admin(user: User | None) -> bool:
    return bool(user) and user.tg_id in settings.admins


def _back(target: str = "a:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data=target)]])


class Pricing(StatesGroup):
    markup = State()
    rate = State()
    tiers = State()


class OrderDone(StatesGroup):
    text = State()


class UserFind(StatesGroup):
    query = State()


class UserBal(StatesGroup):
    amount = State()


class EmojiMap(StatesGroup):
    collect = State()


# ─────────────────────────── Foyda foizi va kurs ───────────────────────────

@router.callback_query(F.data == "a:markup")
async def markup_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(Pricing.markup)
    smart = runtime.pricing_smart()
    tiers_on = runtime.pricing_mode() == "tiers"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Aqlli narx ✅" if smart else "🧠 Aqlli narxga qaytish", callback_data="a:smart")],
        [InlineKeyboardButton(text="📊 Ustama jadvali ✅" if tiers_on else "📊 Ustama jadvali", callback_data="a:tiers")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home")]])
    await call.message.edit_text(
        "💹 <b>Narx siyosati</b>\n\n"
        f"Hozir: <b>{'🧠 aqlli narx' if smart else '📊 ustama jadvali' if tiers_on else f'bir xil foiz — {runtime.markup_percent():g}%'}</b>\n\n"
        "<b>Aqlli narx</b>: asl narxga qarab — arzon mahsulotda foyda ko'proq (1.35$ → 3$), qimmatda kamroq (11.64$ → 16$ ChatGPT Plus); "
        "kafolati kam obunalar arzonroq; rasmiy narxi ma'lum obunalar rasmiy narxdan ~3–5$ arzon. 🔒 qo'lda qo'yilgan narxlarga tegilmaydi.\n\n"
        "<b>Ustama jadvali</b>: tannarxga qarab qat'iy ustama (masalan 1–10$ → +35 000 so'm).\n\n"
        "Hamma narxga <b>bir xil foiz</b> qo'ymoqchi bo'lsangiz — foizni yuboring (masalan <code>30</code>); aqlli narx o'chadi.",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data == "a:smart")
async def smart_on(call: CallbackQuery, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    await runtime.set_value("pricing", "smart")            # sukut endi ustama jadvali — aqlli narx aniq yoziladi
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    await call.message.edit_text(f"🧠 Aqlli narx yoqildi.\n🔄 {n} ta mahsulot narxi yangilandi (🔒 qo'lda narxlar o'zgarmadi).",
                                 reply_markup=_back())
    await call.answer()


@router.message(Pricing.markup)
async def markup_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    try:
        value = float((message.text or "").replace(",", ".").replace("%", "").strip())
        if not 0 <= value <= 500:
            raise ValueError
    except ValueError:
        return await message.answer("❌ 0 dan 500 gacha son yuboring. Masalan: <code>25</code>")
    await state.clear()
    await runtime.set_value("markup", f"{value:g}")
    await runtime.set_value("pricing", "flat")             # qo'lda foiz — bir xil foiz rejimi
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    await message.answer(f"✅ Bir xil foiz rejimi: <b>{value:g}%</b>\n🔄 {n} ta mahsulot narxi yangilandi.\n(Aqlli narxga qaytish: 💹 Foyda foizi → 🧠)", reply_markup=admin_main())


# ─────────────────────────── Ustama jadvali (tannarxga qarab qat'iy ustama) ───────────────────────────

def _tiers_text() -> str:
    rows, prev = [], 0.0
    for upto, markup in runtime.markup_tiers():
        label = f"{prev:g}$ – {upto:g}$" if upto is not None else f"{prev:g}$ dan yuqori"
        rows.append(f"• {label}: tannarx <b>+{markup:,}</b> so'm".replace(",", " "))
        prev = upto or prev
    return "\n".join(rows)


def _tiers_kb(on: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yoqilgan" if on else "▶️ Yoqish", callback_data="a:tiers_on")],
        [InlineKeyboardButton(text="✏️ Jadvalni o'zgartirish", callback_data="a:tiers_edit")],
        [InlineKeyboardButton(text="🧠 Aqlli narxga qaytish", callback_data="a:smart")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:markup")]])


@router.callback_query(F.data == "a:tiers")
async def tiers_view(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    on = runtime.pricing_mode() == "tiers"
    await call.message.edit_text(
        "📊 <b>Ustama jadvali</b>\n\nSotuv narxi = ta'minotchi tannarxi + quyidagi qat'iy ustama (so'm):\n\n"
        f"{_tiers_text()}\n\n"
        "Narx tannarx bilan birga o'zgaradi (cheklovsiz). 🔒 qo'lda qo'yilgan narxlarga tegilmaydi.\n"
        f"Holat: <b>{'yoqilgan ✅' if on else 'o‘chiq'}</b>",
        reply_markup=_tiers_kb(on))
    await call.answer()


@router.callback_query(F.data == "a:tiers_on")
async def tiers_on(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    await runtime.set_value("pricing", "tiers")
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    await call.message.edit_text(f"📊 Ustama jadvali yoqildi.\n🔄 {n} ta mahsulot narxi yangilandi (🔒 qo'lda narxlar o'zgarmadi).\n\n{_tiers_text()}",
                                 reply_markup=_tiers_kb(True))
    await call.answer()


@router.callback_query(F.data == "a:tiers_edit")
async def tiers_edit(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(Pricing.tiers)
    await call.message.edit_text(
        "✏️ <b>Jadvalni o'zgartirish</b>\n\nHar qatorga: <code>tannarx_USD_gacha  ustama_so'm</code>. "
        "Oxirgi qator — undan yuqorisi: <code>+  ustama</code>.\n\nMasalan:\n"
        "<code>10 35000\n30 50000\n60 80000\n100 130000\n+ 250000</code>",
        reply_markup=_back("a:tiers"))
    await call.answer()


@router.message(Pricing.tiers)
async def tiers_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    rows = runtime.parse_tiers(message.text or "")
    if rows is None:
        return await message.answer("❌ Format noto'g'ri. Har qatorga ikki son: <code>10 35000</code>; chegaralar o'sib borsin; "
                                    "oxirgi qator <code>+ 250000</code>.")
    await state.clear()
    await runtime.set_value("markup_tiers", json.dumps(rows))
    await runtime.set_value("pricing", "tiers")
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    await message.answer(f"✅ Ustama jadvali saqlandi va yoqildi.\n🔄 {n} ta mahsulot narxi yangilandi.\n\n{_tiers_text()}", reply_markup=_tiers_kb(True))


@router.callback_query(F.data == "a:rate")
async def rate_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(Pricing.rate)
    manual = runtime.usd_rate_override()
    try:
        current = f"{await canboso.usd_rate():,.2f}".replace(",", " ")
    except canboso.SupplierError:
        current = "noma'lum"
    await call.message.edit_text(
        f"💱 <b>USD kursi</b>\n\nHozir: <b>{current} so'm</b> "
        f"({'qo‘lda belgilangan' if manual > 0 else 'Markaziy bank, avtomatik'})\n\n"
        "Yangi kursni yuboring (masalan <code>12500</code>) yoki <code>0</code> — avtomatik (Markaziy bank).",
        reply_markup=_back(),
    )
    await call.answer()


@router.message(Pricing.rate)
async def rate_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    try:
        value = float((message.text or "").replace(" ", "").replace(",", "."))
        if value != 0 and not 1000 <= value <= 100000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ 1000 dan 100000 gacha son yoki <code>0</code> (avtomatik).")
    await state.clear()
    await runtime.set_value("usd_rate", None if value == 0 else f"{value:g}")
    n = await canboso.reprice_all(session) if settings.canboso_api_key else 0
    label = "avtomatik (Markaziy bank)" if value == 0 else f"{value:,.2f} so'm".replace(",", " ")
    extra = ""
    if settings.canboso_api_key:       # kurs endi bor: katalogni darhol yuklaymiz (kutib o'tirish shart emas)
        from services.catalog_sync import CatalogError, sync_catalog
        try:
            res = await sync_catalog(session)
            extra = f"\n📦 Katalog yuklandi: +{res.created} yangi, {res.updated} yangilandi."
        except CatalogError as ex:
            extra = f"\n⚠️ Katalog yuklanmadi: {html.escape(str(ex))}"
    await message.answer(f"✅ USD kursi: <b>{label}</b>\n🔄 {n} ta mahsulot narxi yangilandi.{extra}", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:p_auto:"))
async def product_auto(call: CallbackQuery, user: User, session: AsyncSession):
    """Mahsulotni qo'lda o'zgartirishlardan avtomatik rejimga qaytarish."""
    from services import overrides

    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p:
        return await call.answer("🚫", show_alert=True)
    overrides.unlock_all(p)
    if canboso.is_supplier_product(p):
        usd = canboso.product_meta(p).get("usd")
        if usd:
            p.supplier_price, p.price = canboso.sell_price_uzs(float(usd), await canboso.usd_rate(), p.name, p.brand or "", canboso.product_meta(p).get("warranty"))
    await session.commit()
    await call.message.edit_text(
        "↩️ Avtomatik rejimga qaytdi: narx qayta hisoblandi, nom va tavsif keyingi "
        "sinxronlashda (<code>/sync</code>) yangilanadi.",
        reply_markup=_back("a:home"),
    )
    await call.answer()


# ─────────────────────────── Buyurtmalar ───────────────────────────

_ST = {
    OrderStatus.PENDING: "⏳", OrderStatus.PAID: "🟡", OrderStatus.DELIVERED: "✅",
    OrderStatus.CANCELLED: "❌", OrderStatus.REFUNDED: "↩️",
}


@router.callback_query(F.data == "a:orders")
async def orders_list(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    rows = list(await session.scalars(
        select(Order).options(selectinload(Order.user))
        .order_by((Order.status == OrderStatus.PAID).desc(), Order.id.desc()).limit(20)
    ))
    kb = InlineKeyboardBuilder()
    for o in rows:
        kb.button(text=f"{_ST.get(o.status, '•')} #{o.id} · {money(o.total)} · {o.user.full_name[:16]}",
                  callback_data=f"a:order:{o.id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home"))
    await call.message.edit_text(
        "🧾 <b>Buyurtmalar</b>\n\n🟡 — qo'lda bajarilishi kutilmoqda (birinchi turadi)\n✅ bajarilgan · ❌ bekor · ↩️ qaytarilgan",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


async def _order_card(session: AsyncSession, oid: int):
    o = await session.scalar(
        select(Order).where(Order.id == oid).options(selectinload(Order.user), selectinload(Order.items))
    )
    if not o:
        return None, None
    lines = []
    for i in o.items:
        mark = {"failed": " ❌", "pending": " 🟡"}.get(i.status, "")
        lines.append(f"• {html.escape(i.product_name)} × {i.qty}{mark}")
        if i.customer_input:
            lines.append(f"  ✉️ Mijoz kiritgan: <code>{html.escape(i.customer_input)}</code>")
        if i.delivered_content:
            lines.append(f"  🔐 <code>{html.escape(i.delivered_content)}</code>")
        if i.supplier_ref:
            lines.append(f"  🏷 Ta'minotchi buyurtmasi: <code>{html.escape(i.supplier_ref)}</code>")
    text = (
        f"{_ST.get(o.status, '•')} <b>Buyurtma #{o.id}</b> — {o.status.value}\n"
        f"👤 {html.escape(o.user.full_name)} (<code>{o.user.tg_id}</code>)"
        + (f" @{html.escape(o.user.username)}" if o.user.username else "") + "\n"
        f"💵 {money(o.total)} · {o.created_at:%d.%m.%Y %H:%M}\n\n" + "\n".join(lines)
    )
    kb = InlineKeyboardBuilder()
    if o.status == OrderStatus.PAID:
        kb.button(text="✅ Bajarildi — ma'lumot yuborish", callback_data=f"a:o_done:{o.id}")
    if o.status in (OrderStatus.PAID, OrderStatus.DELIVERED):
        kb.button(text="↩️ Pulni qaytarish", callback_data=f"a:o_refund:{o.id}")
    kb.button(text="👤 Mijoz kabineti", callback_data=f"a:user:{o.user.tg_id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:orders"))
    return text, kb.as_markup()


@router.callback_query(F.data.startswith("a:order:"))
async def order_open(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    text, kb = await _order_card(session, int(call.data.split(":")[2]))
    if not text:
        return await call.answer("🚫", show_alert=True)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("a:o_done:"))
async def order_done_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(OrderDone.text)
    await state.update_data(oid=int(call.data.split(":")[2]))
    await call.message.edit_text(
        "✅ Mijozga yuboriladigan ma'lumotni yozing (akkaunt, kod yoki izoh).\n"
        "U buyurtmada saqlanadi va mijozga botdan yuboriladi.",
        reply_markup=_back("a:orders"),
    )
    await call.answer()


@router.message(OrderDone.text)
async def order_done_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    text = (message.text or "").strip()
    if not text:
        return await message.answer("❌ Matn yuboring.")
    data = await state.get_data()
    await state.clear()
    o = await session.scalar(
        select(Order).where(Order.id == data["oid"]).options(selectinload(Order.user), selectinload(Order.items))
    )
    if not o:
        return await message.answer("🚫 Buyurtma topilmadi.", reply_markup=admin_main())
    waiting = [i for i in o.items if i.status == "pending" or (i.status == "ok" and not i.delivered_content)]
    if waiting:
        waiting[0].delivered_content = text
    for i in waiting:
        i.status = "ok"
    o.status = OrderStatus.DELIVERED
    await session.commit()
    try:
        await message.bot.send_message(
            o.user.tg_id,
            f"✅ <b>Buyurtma #{o.id} bajarildi</b>\n\n<code>{html.escape(text)}</code>",
        )
        sent = "Mijozga yuborildi."
    except Exception:  # noqa: BLE001
        sent = "⚠️ Mijozga xabar yuborib bo'lmadi (botni bloklagan), lekin buyurtmada saqlandi."
    await message.answer(f"✅ Buyurtma #{o.id} bajarildi. {sent}", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:o_refund:"))
async def order_refund_ask(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    oid = int(call.data.split(":")[2])
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, qaytarilsin", callback_data=f"a:o_refund_do:{oid}")
    kb.button(text="❌ Yo'q", callback_data=f"a:order:{oid}")
    kb.adjust(1)
    await call.message.edit_text(f"⚠️ Buyurtma #{oid} puli mijoz balansiga qaytariladi. Davom etamizmi?",
                                 reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("a:o_refund_do:"))
async def order_refund_do(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    o = await session.scalar(
        select(Order).where(Order.id == int(call.data.split(":")[2]))
        .options(selectinload(Order.user), selectinload(Order.items))
    )
    if not o or o.status not in (OrderStatus.PAID, OrderStatus.DELIVERED):
        return await call.answer("Bu buyurtmani qaytarib bo'lmaydi", show_alert=True)
    o.user.balance += o.total
    o.status = OrderStatus.REFUNDED
    for i in o.items:
        i.status = "failed"
    await session.commit()
    try:
        await call.bot.send_message(
            o.user.tg_id,
            f"↩️ Buyurtma #{o.id} bekor qilindi, <b>{money(o.total)}</b> hisobingizga qaytarildi.",
        )
    except Exception:  # noqa: BLE001
        pass
    await call.message.edit_text(f"↩️ Buyurtma #{o.id}: {money(o.total)} qaytarildi.", reply_markup=_back("a:orders"))
    await call.answer()


# ─────────────────────────── Foydalanuvchilar ───────────────────────────

@router.callback_query(F.data == "a:users")
async def users_menu(call: CallbackQuery, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(UserFind.query)
    rows = list(await session.scalars(select(User).order_by(User.id.desc()).limit(10)))
    kb = InlineKeyboardBuilder()
    for u in rows:
        kb.button(text=f"{'🚫 ' if u.is_banned else ''}{u.full_name[:20]} · {money(u.balance)}", callback_data=f"a:user:{u.tg_id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home"))
    total = await session.scalar(select(func.count(User.id))) or 0
    await call.message.edit_text(
        f"👥 <b>Foydalanuvchilar</b> ({total})\n\nEng so'nggi 10 tasi pastda. Qidirish uchun "
        "<b>Telegram ID</b> yoki <b>@username</b> yuboring.",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


async def _user_card(session: AsyncSession, tg_id: int):
    u = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not u:
        return None, None
    orders = await session.scalar(select(func.count(Order.id)).where(Order.user_id == u.id)) or 0
    spent = await session.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(
        Order.user_id == u.id, Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))) or 0
    text = (
        f"👤 <b>{html.escape(u.full_name)}</b>"
        + (f" @{html.escape(u.username)}" if u.username else "") + "\n"
        f"🆔 <code>{u.tg_id}</code>\n💰 Balans: <b>{money(u.balance)}</b>\n"
        f"🧾 Buyurtmalar: {orders} · jami xarid: <b>{money(spent)}</b>\n📅 {u.created_at:%d.%m.%Y}\n"
        f"Holat: {'🚫 bloklangan' if u.is_banned else '✅ faol'}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🧾 Buyurtmalari ({orders})", callback_data=f"a:u_orders:{u.tg_id}")
    kb.button(text="➕ Balans qo'shish / ayirish", callback_data=f"a:u_bal:{u.tg_id}")
    kb.button(text="✅ Blokdan chiqarish" if u.is_banned else "🚫 Bloklash", callback_data=f"a:u_ban:{u.tg_id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:users"))
    return text, kb.as_markup()


@router.message(UserFind.query)
async def user_find(message: Message, user: User, state: FSMContext, session: AsyncSession):
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
        return await message.answer("🚫 Topilmadi. ID yoki @username ni tekshiring.")
    await state.clear()
    text, kb = await _user_card(session, found.tg_id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("a:user:"))
async def user_open(call: CallbackQuery, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    text, kb = await _user_card(session, int(call.data.split(":")[2]))
    if not text:
        return await call.answer("🚫", show_alert=True)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("a:u_ban:"))
async def user_ban(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    tg_id = int(call.data.split(":")[2])
    if tg_id in settings.admins:
        return await call.answer("Adminni bloklab bo'lmaydi", show_alert=True)
    u = await session.scalar(select(User).where(User.tg_id == tg_id))
    if u:
        u.is_banned = not u.is_banned
        await session.commit()
    text, kb = await _user_card(session, tg_id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅")


@router.callback_query(F.data.startswith("a:u_bal:"))
async def user_bal_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(UserBal.amount)
    await state.update_data(tg_id=int(call.data.split(":")[2]))
    await call.message.edit_text(
        "💵 Summani so'mda yuboring. Qo'shish uchun <code>50000</code>, ayirish uchun <code>-20000</code>.",
        reply_markup=_back("a:users"),
    )
    await call.answer()


@router.message(UserBal.amount)
async def user_bal_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    raw = (message.text or "").replace(" ", "")
    try:
        amount = int(raw)
        if amount == 0 or abs(amount) > 1_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Butun son yuboring (masalan <code>50000</code> yoki <code>-20000</code>).")
    data = await state.get_data()
    await state.clear()
    u = await session.scalar(select(User).where(User.tg_id == data["tg_id"]))
    if not u:
        return await message.answer("🚫 Topilmadi.", reply_markup=admin_main())
    if u.balance + amount < 0:
        return await message.answer(f"❌ Balans manfiy bo'lib qoladi (hozir {money(u.balance)}).", reply_markup=admin_main())
    await repo.add_balance(session, u, amount)
    if amount > 0:
        try:
            await message.bot.send_message(u.tg_id, f"✅ Hisobingiz <b>{money(amount)}</b> ga to'ldirildi.\n💰 Yangi hisob: <b>{money(u.balance)}</b>")
        except Exception:  # noqa: BLE001
            pass
    await message.answer(f"✅ {html.escape(u.full_name)}: yangi balans <b>{money(u.balance)}</b>", reply_markup=admin_main())


# ─────────────────────────── Premium emoji ───────────────────────────

def _emoji_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Hozirgi ro'yxat", callback_data="a:emoji_list")
    kb.button(text="🗑 Hammasini tozalash", callback_data="a:emoji_clear")
    kb.button(text="⬅️ Tayyor", callback_data="a:home")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "a:emoji")
async def emoji_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(EmojiMap.collect)
    warn = ""
    await call.message.edit_text(
        "😀 <b>Premium emoji</b>\n\n"
        "⚡ <b>Eng oson yo'l:</b> chiroyli emoji-paketning havolasini yuboring (masalan <code>https://t.me/addemoji/PaketNomi</code>). "
        "Bot kerakli emojilarni paketdan o'zi topib biriktiradi, ID qidirish shart emas. Bir necha havola yuborsangiz bo'ladi.\n\n"
        "Yoki menga <b>premium emojilar qo'shilgan xabar</b> yuboring (Telegram Premium kerak). "
        "Har bir premium emoji o'zining oddiy juftiga bog'lanadi (masalan, premium 🛍 → oddiy 🛍), "
        "shundan keyin botning <b>barcha matnlaridagi</b> shu emojilar premium bo'ladi.\n\n"
        f"Hozir saqlangan: <b>{len(runtime.user_emoji_map())}</b> ta.\n"
        "ID bilan ham bo'ladi: <code>📦 5312361253610475399</code> (emoji, probel, ID — har qatorga bittadan; ID ni @TgEmojis beradi).\n"
        "Bir necha xabar yuborishingiz mumkin; tugatgach «Tayyor» ni bosing.\n\n"
        "ℹ️ Botni yaratgan akkauntda (bot egasida) <b>Telegram Premium</b> bo'lsa yetarli — boshqa narsa shart emas. "
        "Tugmalar ichida premium emoji ishlamaydi (Telegram cheklovi)." + warn,
        reply_markup=_emoji_kb(),
    )
    await call.answer()


async def _import_packs(message: Message, names: list[str]) -> None:
    """Emoji paketi(lari)dan botga kerak emojilarning ID larini Telegram'ning o'zidan olib saqlaydi."""
    from aiogram.exceptions import TelegramAPIError
    from services.emoji import WANTED, pick_from_pack
    found: dict[str, str] = {}
    lines: list[str] = []
    for name in names:
        try:
            st = await message.bot.get_sticker_set(name)
        except TelegramAPIError:
            lines.append(f"❌ <code>{html.escape(name)}</code>: paket topilmadi")
            continue
        got = pick_from_pack(st.stickers)
        if not got:
            lines.append(f"⚠️ <b>{html.escape(st.title)}</b>: bu paketda kerakli emojilar yo'q (yoki oddiy stiker paketi, emoji paketi emas)")
            continue
        for ch, cid in got.items():
            found.setdefault(ch, cid)       # bir nechta paket bo'lsa — birinchisi ustun
        lines.append(f"✅ <b>{html.escape(st.title)}</b>: {' '.join(got)}")
    if found:
        merged = {**runtime.user_emoji_map(), **found}
        await runtime.set_value("emoji_map", json.dumps(merged, ensure_ascii=False))
        have = set(runtime.emoji_map())
        missing = [w for w in WANTED if w not in have and w + "\ufe0f" not in have]
        lines.append(f"\nJami saqlangan: <b>{len(merged)}</b> ta.")
        if missing:
            lines.append("Hali premium bo'lmaganlari: " + " ".join(missing) + "\n<i>Boshqa paket havolasini ham yuborsangiz, qolganlari to'ldiriladi.</i>")
        else:
            lines.append("🎉 Hamma kerakli emojilar premium bo'ldi!")
    await message.answer("\n".join(lines), reply_markup=_emoji_kb())


@router.message(EmojiMap.collect)
async def emoji_collect(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    from services.emoji import pack_names
    names = pack_names(message.text)
    if names:
        return await _import_packs(message, names)
    found = {}
    for ent in message.entities or []:
        if ent.type == "custom_emoji" and ent.custom_emoji_id:
            try:
                char = ent.extract_from(message.text or "").strip()
            except UnicodeDecodeError:      # noto'g'ri offset — bu emojini o'tkazib yuboramiz
                continue
            if char:
                found[char] = ent.custom_emoji_id
    if not found:       # premium emoji yo'q — «📦 5312361253610475399» (emoji + ID, @TgEmojis bergan) ko'rinishida ham bo'ladi
        found = emoji_pairs(message.text or "")
    if not found:
        return await message.answer("❌ Premium emoji topilmadi. Premium emoji bilan yozilgan xabar yuboring "
                                    "yoki «📦 5312361253610475399» (emoji va uning ID si) ko'rinishida yozing.",
                                    reply_markup=_emoji_kb())
    merged = {**runtime.user_emoji_map(), **found}
    await runtime.set_value("emoji_map", json.dumps(merged, ensure_ascii=False))
    note = "" if premium_active() else "\n(Hozircha premium vaqtincha o'chirilgan: Telegram ruxsat bermadi — bot egasida Telegram Premium bormi? 10 daqiqadan so'ng qayta uriniladi.)"
    await message.answer(
        f"✅ Saqlandi: {' '.join(found)}\nJami: <b>{len(merged)}</b> ta. Yana yuborishingiz mumkin.{note}",
        reply_markup=_emoji_kb(),
    )


@router.callback_query(F.data == "a:emoji_list")
async def emoji_list(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    m = runtime.user_emoji_map()
    await call.answer(("Saqlangan: " + " ".join(m))[:190] if m else "Hali hech narsa yo'q", show_alert=True)


@router.callback_query(F.data == "a:emoji_clear")
async def emoji_clear(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    await runtime.set_value("emoji_map", None)
    await call.answer("🗑 Tozalandi", show_alert=True)
