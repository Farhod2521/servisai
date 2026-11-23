"""Admin panel: kategoriya/mahsulot CRUD, zaxira, statistika, broadcast."""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import (
    Category, DeliveryType, Product, StockItem, User,
)
from keyboards.admin_kb import (
    admin_cat_actions, admin_cats, admin_main, admin_prod_actions,
    admin_prod_list, confirm_kb, section_kb,
)
from locales.texts import TEXTS, money, t
from services import canboso, overrides, panel, repo
from services.announce import announce_product
from services.catalog_sync import CatalogError, sync_catalog
from services.emoji import extract_custom_id

router = Router(name="admin")
log = logging.getLogger(__name__)


def _is_admin(user: User | None) -> bool:
    return bool(user) and user.tg_id in settings.admins


# ─────────────────────────── FSM holatlari ───────────────────────────

class CatAdd(StatesGroup):
    emoji = State()
    name = State()


class CatEdit(StatesGroup):
    rename = State()
    emoji = State()


class ProdAdd(StatesGroup):
    category = State()
    emoji = State()
    name = State()
    description = State()
    price = State()
    delivery = State()
    stock = State()


class ProdEdit(StatesGroup):
    name = State()
    price = State()
    desc = State()
    emoji = State()
    stock = State()


class Broadcast(StatesGroup):
    text = State()


# ─────────────────────────── Kirish ───────────────────────────

@router.message(F.text.in_({t(l, "menu_admin") for l in TEXTS}))
async def admin_entry(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    await state.clear()
    text, c = await panel.home_view(session)
    await message.answer(text, reply_markup=admin_main(c))


@router.callback_query(F.data == "a:home")
async def admin_home(call: CallbackQuery, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    text, c = await panel.home_view(session)
    try:
        await call.message.edit_text(text, reply_markup=admin_main(c))
    except TelegramBadRequest:       # «message is not modified»: hech narsa o'zgarmagan
        pass
    await call.answer()


@router.callback_query(F.data.regexp(r"^a:s:(shop|price|pay|msg|report|settings|tg)$"))
async def admin_section(call: CallbackQuery, user: User, state: FSMContext):
    """Bo'lim sahifasi: nima qilish mumkinligi bir qarashda."""
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    key = call.data.split(":")[2]
    await call.message.edit_text(panel.section_text(key), reply_markup=section_kb(key))
    await call.answer()


# ─────────────────────────── Statistika ───────────────────────────

@router.callback_query(F.data == "a:stats")
async def admin_stats(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    s = await repo.stats(session)
    bal = await canboso.fetch_balance() if settings.canboso_api_key else None
    await call.message.edit_text(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🧾 Buyurtmalar: <b>{s['orders']}</b>\n"
        f"💰 Tushum: <b>{money(s['revenue'])}</b>\n"
        f"📦 Faol mahsulotlar: <b>{s['products']}</b>\n"
        f"🗃 Zaxirada: <b>{s['in_stock']}</b>\n"
        f"🟡 Qo'lda bajarilishi kutilayotgan buyurtmalar: <b>{s['pending_orders']}</b>"
        + (f"\n💳 Ta'minotchi hamyoni: <b>${bal:,.2f}</b>" if bal is not None else ""),
        reply_markup=admin_main(),
    )
    await call.answer()


# ─────────────────────────── Kategoriyalar ───────────────────────────

@router.callback_query(F.data == "a:cats")
async def cats_list(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    cats = list(await session.scalars(select(Category).order_by(Category.sort_order, Category.id)))
    await call.message.edit_text(
        "📂 <b>Kategoriyalar</b>\n\nTahrirlash uchun tanlang:",
        reply_markup=admin_cats(cats),
    )
    await call.answer()


@router.callback_query(F.data.startswith("a:cat:"))
async def cat_open(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    cat = await session.get(Category, int(call.data.split(":")[2]))
    if not cat:
        return await call.answer("🚫", show_alert=True)
    count = len(await repo.category_products(session, cat.id))
    await call.message.edit_text(
        f"{cat.emoji} <b>{cat.name_uz}</b>\n\n"
        f"📦 Mahsulotlar: {count}\n"
        f"Holat: {'✅ faol' if cat.is_active else '🚫 o‘chiq'}",
        reply_markup=admin_cat_actions(cat),
    )
    await call.answer()


@router.callback_query(F.data == "a:cat_add")
async def cat_add_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(CatAdd.emoji)
    await call.message.edit_text("😀 Kategoriya uchun emoji yuboring (masalan: 🤖)")
    await call.answer()


@router.message(CatAdd.emoji)
async def cat_add_emoji(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    await state.update_data(emoji=(message.text or "📦").strip()[:32])
    await state.set_state(CatAdd.name)
    await message.answer("✏️ Kategoriya nomini yuboring:")


@router.message(CatAdd.name)
async def cat_add_name(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    cat = Category(emoji=data["emoji"], name_uz=(message.text or "").strip()[:128])
    session.add(cat)
    await session.commit()
    await state.clear()
    await message.answer(
        f"✅ Kategoriya qo'shildi: {cat.emoji} <b>{cat.name_uz}</b>",
        reply_markup=admin_main(),
    )


@router.callback_query(F.data.startswith("a:cat_rename:"))
async def cat_rename_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(CatEdit.rename)
    await state.update_data(cat_id=int(call.data.split(":")[2]))
    await call.message.edit_text("✏️ Yangi nomni yuboring:")
    await call.answer()


@router.message(CatEdit.rename)
async def cat_rename_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    cat = await session.get(Category, data["cat_id"])
    if cat:
        cat.name_uz = (message.text or "").strip()[:128]
        await session.commit()
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:cat_emoji:"))
async def cat_emoji_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(CatEdit.emoji)
    await state.update_data(cat_id=int(call.data.split(":")[2]))
    await call.message.edit_text("😀 Yangi emojini yuboring:")
    await call.answer()


@router.message(CatEdit.emoji)
async def cat_emoji_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    cat = await session.get(Category, data["cat_id"])
    if cat:
        cat.emoji = (message.text or "📦").strip()[:32]
        # Premium emoji yuborilgan bo'lsa, uning id sini saqlaymiz
        cat.custom_emoji_id = extract_custom_id(message.entities)
        await session.commit()
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:cat_toggle:"))
async def cat_toggle(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    cat = await session.get(Category, int(call.data.split(":")[2]))
    if cat:
        cat.is_active = not cat.is_active
        await session.commit()
        await call.message.edit_reply_markup(reply_markup=admin_cat_actions(cat))
    await call.answer("✅")


@router.callback_query(F.data.startswith("a:cat_del:"))
async def cat_del_ask(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    cid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "⚠️ Kategoriya va undagi <b>barcha mahsulotlar</b> o'chiriladi. Davom etamizmi?",
        reply_markup=confirm_kb("cat", cid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("a:confirm:cat:"))
async def cat_del_do(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    cid = int(call.data.split(":")[3])
    cat = await session.get(Category, cid)
    if cat:
        await session.delete(cat)
        await session.commit()
    await call.message.edit_text("🗑 O'chirildi.", reply_markup=admin_main())
    await call.answer()


# ─────────────────────────── Mahsulotlar ───────────────────────────

@router.callback_query(F.data == "a:prods")
async def prods_pick_cat(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    cats = list(await session.scalars(select(Category).order_by(Category.sort_order)))
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c.emoji} {c.name_uz}", callback_data=f"a:cat_prods:{c.id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home"))
    await call.message.edit_text("📦 Kategoriyani tanlang:", reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("a:cat_prods:"))
async def cat_prods(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    cid = int(call.data.split(":")[2])
    products = list(await session.scalars(
        select(Product).where(Product.category_id == cid).order_by(Product.id)
    ))
    if not products:
        await call.message.edit_text("📭 Bu kategoriyada mahsulot yo'q.", reply_markup=admin_main())
        return await call.answer()
    await call.message.edit_text("📦 Mahsulotni tanlang:", reply_markup=admin_prod_list(products, cid))
    await call.answer()


def _supplier_line(p: Product) -> str:
    """Ta'minotchi mahsuloti uchun: ta'minotchi narxi va sizning foydangiz."""
    if not canboso.is_supplier_product(p) or not p.supplier_price:
        return ""
    profit = p.price - p.supplier_price
    pct = profit / p.supplier_price * 100 if p.supplier_price else 0
    usd = canboso.product_meta(p).get("usd")
    return (f"🏭 Ta'minotchi: {money(p.supplier_price)}" + (f" (${usd:g})" if usd else "") +
            f" · foyda <b>{money(profit)}</b> ({pct:.0f}%)\n")


@router.callback_query(F.data.startswith("a:prod:"))
async def prod_open(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await repo.get_product(session, int(call.data.split(":")[2]))
    if not p:
        return await call.answer("🚫", show_alert=True)
    stock = await repo.stock_count(session, p)
    await call.message.edit_text(
        f"{p.emoji} <b>{p.name}</b>\n\n"
        f"{p.description or '—'}\n\n"
        f"📖 Qo'llanma: {'bor ✅' if p.guide else 'tayyor matn'} · 🎬 Video: {'bor ✅' if p.guide_video else 'yo‘q'}\n"
        f"🛡 Kafolat matni: {'o‘zingiz yozgansiz ✅' if p.warranty_note else 'avtomatik'}\n"
        f"💵 {money(p.price)}{' 🔒' if 'price' in overrides.locked(p) else ''}\n"
        f"{_supplier_line(p)}"
        f"📦 Zaxira: {'♾' if p.unlimited else stock}\n"
        f"🚚 Yetkazish: {p.delivery_type.value}\n"
        f"Holat: {'✅ faol' if p.is_active else '🚫 o‘chiq'}",
        reply_markup=admin_prod_actions(p),
    )
    await call.answer()


@router.callback_query(F.data == "a:prod_add")
async def prod_add_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    cats = list(await session.scalars(select(Category).order_by(Category.sort_order)))
    if not cats:
        await call.message.edit_text("⚠️ Avval kategoriya qo'shing.", reply_markup=admin_main())
        return await call.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c.emoji} {c.name_uz}", callback_data=f"a:np_cat:{c.id}")
    kb.adjust(1)
    await state.set_state(ProdAdd.category)
    await call.message.edit_text("📂 Qaysi kategoriyaga?", reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(ProdAdd.category, F.data.startswith("a:np_cat:"))
async def prod_add_cat(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.update_data(category_id=int(call.data.split(":")[2]))
    await state.set_state(ProdAdd.emoji)
    await call.message.edit_text("😀 Mahsulot emojisini yuboring:")
    await call.answer()


@router.message(ProdAdd.emoji)
async def prod_add_emoji(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    custom_id = extract_custom_id(message.entities)
    await state.update_data(emoji=(message.text or "🔹").strip()[:32], custom_emoji_id=custom_id)
    await state.set_state(ProdAdd.name)
    await message.answer("✏️ Mahsulot nomini yuboring:")


@router.message(ProdAdd.name)
async def prod_add_name(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    await state.update_data(name=(message.text or "").strip()[:255])
    await state.set_state(ProdAdd.description)
    await message.answer("📝 Tavsifini yuboring (yoki <code>-</code> deb yuboring):")


@router.message(ProdAdd.description)
async def prod_add_desc(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    desc = (message.text or "").strip()
    await state.update_data(description="" if desc == "-" else desc)
    await state.set_state(ProdAdd.price)
    await message.answer("💵 Narxini so'mda yuboring (masalan: <code>25000</code>):")


@router.message(ProdAdd.price)
async def prod_add_price(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit():
        return await message.answer("❌ Faqat raqam yuboring.")
    await state.update_data(price=int(raw))
    await state.set_state(ProdAdd.delivery)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡️ Avtomatik (zaxiradan)", callback_data="a:np_d:auto")
    kb.button(text="👤 Qo'lda (admin bajaradi)", callback_data="a:np_d:manual")
    kb.adjust(1)
    await message.answer("🚚 Yetkazish turini tanlang:", reply_markup=kb.as_markup())


@router.callback_query(ProdAdd.delivery, F.data.startswith("a:np_d:"))
async def prod_add_delivery(
    call: CallbackQuery, user: User, state: FSMContext, session: AsyncSession
):
    if not _is_admin(user):
        return await call.answer()
    mode = call.data.split(":")[2]
    data = await state.get_data()
    product = Product(
        category_id=data["category_id"],
        emoji=data["emoji"],
        custom_emoji_id=data.get("custom_emoji_id"),
        name=data["name"],
        description=data["description"],
        price=data["price"],
        delivery_type=DeliveryType.AUTO if mode == "auto" else DeliveryType.MANUAL,
        unlimited=(mode == "manual"),
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)

    if mode == "auto":
        await state.set_state(ProdAdd.stock)
        await state.update_data(product_id=product.id)
        await call.message.edit_text(
            "📥 Endi zaxirani yuboring.\n\n"
            "Har bir qator — bitta sotiladigan birlik.\n"
            "Tugatgach <code>/done</code> yuboring."
        )
    else:
        await state.clear()
        await call.message.edit_text(
            f"✅ Mahsulot qo'shildi: {product.emoji} <b>{product.name}</b>",
            reply_markup=admin_main(),
        )
        await announce_product(call.bot, session, product)
    await call.answer()


@router.message(ProdAdd.stock, Command("done"))
async def prod_add_stock_done(
    message: Message, user: User, state: FSMContext, session: AsyncSession
):
    if not _is_admin(user):
        return
    data = await state.get_data()
    await state.clear()
    product = await repo.get_product(session, data["product_id"])
    await message.answer(
        f"✅ Tayyor: {product.emoji} <b>{product.name}</b>", reply_markup=admin_main()
    )
    if product:
        await announce_product(message.bot, session, product)


@router.message(ProdAdd.stock)
async def prod_add_stock(
    message: Message, user: User, state: FSMContext, session: AsyncSession
):
    if not _is_admin(user):
        return
    data = await state.get_data()
    lines = [x.strip() for x in (message.text or "").splitlines() if x.strip()]
    for line in lines:
        session.add(StockItem(product_id=data["product_id"], content=line))
    await session.commit()
    await message.answer(
        f"📥 {len(lines)} ta birlik qo'shildi.\n"
        f"Yana yuborishingiz mumkin yoki <code>/done</code> bosing."
    )


# ─── Mahsulotni tahrirlash ───

@router.callback_query(F.data.startswith("a:p_price:"))
async def p_price_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ProdEdit.price)
    await state.update_data(pid=int(call.data.split(":")[2]))
    await call.message.edit_text("💵 Yangi narxni so'mda yuboring:")
    await call.answer()


@router.message(ProdEdit.price)
async def p_price_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit():
        return await message.answer("❌ Faqat raqam.")
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    if p:
        p.price = int(raw)
        overrides.lock(p, "price")          # sinxronlash bu narxni o'zgartirmaydi
        await session.commit()
    await state.clear()
    await message.answer("✅ Narx yangilandi.", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:p_name:"))
async def p_name_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ProdEdit.name)
    await state.update_data(pid=int(call.data.split(":")[2]))
    await call.message.edit_text("✏️ Yangi nomni yuboring:")
    await call.answer()


@router.message(ProdEdit.name)
async def p_name_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    if p:
        p.name = (message.text or "").strip()[:255]
        overrides.lock(p, "name")
        await session.commit()
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:p_desc:"))
async def p_desc_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ProdEdit.desc)
    await state.update_data(pid=int(call.data.split(":")[2]))
    await call.message.edit_text("📝 Yangi tavsifni yuboring:")
    await call.answer()


@router.message(ProdEdit.desc)
async def p_desc_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    if p:
        p.description = (message.text or "").strip()
        overrides.lock(p, "description")
        await session.commit()
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:p_emoji:"))
async def p_emoji_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ProdEdit.emoji)
    await state.update_data(pid=int(call.data.split(":")[2]))
    await call.message.edit_text("😀 Yangi emojini yuboring (premium emoji ham bo'ladi):")
    await call.answer()


@router.message(ProdEdit.emoji)
async def p_emoji_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    if p:
        p.emoji = (message.text or "🔹").strip()[:32]
        p.custom_emoji_id = extract_custom_id(message.entities)
        overrides.lock(p, "emoji")
        await session.commit()
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=admin_main())


@router.callback_query(F.data.startswith("a:p_stock:"))
async def p_stock_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ProdEdit.stock)
    await state.update_data(pid=int(call.data.split(":")[2]))
    await call.message.edit_text(
        "📥 Zaxira qatorlarini yuboring (har qator — bitta birlik).\n"
        "Tugatgach <code>/done</code>."
    )
    await call.answer()


@router.message(ProdEdit.stock, Command("done"))
async def p_stock_done(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    await state.clear()
    await message.answer("✅ Zaxira yangilandi.", reply_markup=admin_main())


@router.message(ProdEdit.stock)
async def p_stock_add(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    lines = [x.strip() for x in (message.text or "").splitlines() if x.strip()]
    for line in lines:
        session.add(StockItem(product_id=data["pid"], content=line))
    await session.commit()
    await message.answer(f"📥 {len(lines)} ta qo'shildi. Yana yoki <code>/done</code>.")


@router.callback_query(F.data.startswith("a:p_toggle:"))
async def p_toggle(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if p:
        p.is_active = not p.is_active
        if canboso.is_supplier_product(p):   # admin qarori sinxronlashda ham saqlansin
            (overrides.unlock if p.is_active else overrides.lock)(p, "hidden")
        await session.commit()
        await call.message.edit_reply_markup(reply_markup=admin_prod_actions(p))
    await call.answer("✅")


@router.callback_query(F.data.startswith("a:p_del:"))
async def p_del_ask(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    pid = int(call.data.split(":")[2])
    await call.message.edit_text(
        "⚠️ Mahsulot va uning zaxirasi o'chiriladi. Davom etamizmi?",
        reply_markup=confirm_kb("prod", pid),
    )
    await call.answer()


@router.callback_query(F.data.startswith("a:confirm:prod:"))
async def p_del_do(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[3]))
    note = "🗑 O'chirildi."
    if p and canboso.is_supplier_product(p):
        # Ta'minotchi mahsuloti o'chirilsa, keyingi sinxronlash uni qayta qo'shib yuborardi — yashiramiz
        p.is_active = False
        overrides.lock(p, "hidden")
        await session.commit()
        note = "🚫 Ta'minotchi mahsuloti do'konda yashirildi (tarix saqlanadi). Qaytarish: mahsulot sahifasida «Yoqish»."
    elif p:
        await session.delete(p)
        await session.commit()
    await call.message.edit_text(note, reply_markup=admin_main())
    await call.answer()


@router.callback_query(F.data.startswith("a:p_announce:"))
async def p_announce(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await repo.get_product(session, int(call.data.split(":")[2]))
    if p:
        p.announced = False
        await session.commit()
        sent = await announce_product(call.bot, session, p, force=True)
        await call.answer(f"📢 {sent} ta manzilga yuborildi", show_alert=True)
    else:
        await call.answer("🚫", show_alert=True)


# ─────────────────────────── Katalog sinxronizatsiyasi ───────────────────────────

@router.callback_query(F.data == "a:sync")
async def catalog_sync_run(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()

    if not settings.catalog_enabled:
        return await call.answer(
            "⚠️ CATALOG_API_URL sozlanmagan.\n"
            "Render → Environment ga qo'shing.",
            show_alert=True,
        )

    await call.answer("🔄 Yuklanmoqda...")
    status = await call.message.edit_text(
        "🔄 Ta'minotchi katalogi yuklanmoqda...\n<i>Bu bir necha soniya olishi mumkin.</i>"
    )

    try:
        result = await sync_catalog(session)
    except CatalogError as ex:
        return await status.edit_text(
            f"❌ <b>Katalog yangilanmadi</b>\n\n{ex}", reply_markup=admin_main()
        )
    except Exception as ex:  # noqa: BLE001
        log.exception("Katalog sinxronizatsiyasi")
        return await status.edit_text(
            f"❌ <b>Kutilmagan xato</b>\n\n<code>{ex}</code>", reply_markup=admin_main()
        )

    await status.edit_text(result.report(), reply_markup=admin_main())


@router.message(Command("sync"))
async def catalog_sync_cmd(message: Message, user: User, session: AsyncSession):
    """/sync — katalogni terminal orqali yangilash."""
    if not _is_admin(user):
        return
    if not settings.catalog_enabled:
        return await message.answer("⚠️ CATALOG_API_URL sozlanmagan.")
    try:
        result = await sync_catalog(session)
    except CatalogError as ex:
        return await message.answer(f"❌ {ex}")
    await message.answer(result.report())


# ─────────────────────────── Broadcast ───────────────────────────

@router.callback_query(F.data == "a:bc")
async def bc_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(Broadcast.text)
    await call.message.edit_text("📢 Yubormoqchi bo'lgan xabarni yuboring:")
    await call.answer()


@router.message(Broadcast.text)
async def bc_send(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    await state.clear()
    ids = await repo.all_user_ids(session)
    ok = fail = 0
    status = await message.answer(f"📤 Yuborilmoqda... 0/{len(ids)}")
    for i, uid in enumerate(ids, 1):
        try:
            await message.copy_to(uid)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # Telegram limiti: ~20 msg/sek
        if i % 25 == 0:
            try:
                await status.edit_text(f"📤 Yuborilmoqda... {i}/{len(ids)}")
            except Exception:
                pass
    await status.edit_text(f"✅ Yuborildi: {ok}\n❌ Xato: {fail}", reply_markup=admin_main())


# ─────────────────────────── To'lovni tasdiqlash ───────────────────────────

@router.message(Command("approve"))
async def approve_payment(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("Foydalanish: <code>/approve &lt;payment_id&gt;</code>")
    payment = await repo.mark_payment_paid(session, int(parts[1]))
    if not payment:
        return await message.answer("🚫 To'lov topilmadi.")
    await message.answer(
        f"✅ To'lov #{payment.id} tasdiqlandi. {money(payment.amount)} qo'shildi."
    )
    from services import feed
    await feed.topup(message.bot, payment.user.tg_id, payment.amount, f"PAY-{payment.id}", payment.user.username)
    try:
        await message.bot.send_message(
            payment.user.tg_id,
            t(payment.user.lang, "topup_ok",
              amount=money(payment.amount), balance=money(payment.user.balance)),
        )
    except Exception:
        pass


@router.message(Command("addbalance"))
async def add_balance_cmd(message: Message, user: User, session: AsyncSession):
    """/addbalance <tg_id> <summa> — qo'lda balans qo'shish."""
    if not _is_admin(user):
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].lstrip("-").isdigit() or not parts[2].isdigit():
        return await message.answer("Foydalanish: <code>/addbalance &lt;tg_id&gt; &lt;summa&gt;</code>")
    target = await session.scalar(select(User).where(User.tg_id == int(parts[1])))
    if not target:
        return await message.answer("🚫 Foydalanuvchi topilmadi.")
    await repo.add_balance(session, target, int(parts[2]))
    await message.answer(f"✅ {money(int(parts[2]))} qo'shildi. Yangi hisob: {money(target.balance)}")
    try:
        await message.bot.send_message(
            target.tg_id,
            t(target.lang, "topup_ok", amount=money(int(parts[2])), balance=money(target.balance)),
        )
    except Exception:
        pass
