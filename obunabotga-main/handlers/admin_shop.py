"""Admin panel (do'kon): narxlar, mahsulot qo'llanmasi, mijozlarga xabarnomalar.

  • 💰 Narxlar — brend bo'yicha ro'yxat, har bir mahsulot narxini bir bosishda o'zgartirish (yoki avtomatikka qaytarish);
  • 📖 Qo'llanma — mahsulotga «qanday foydalaniladi / qanday kiriladi» matni («Qo'llanma» bo'limida va xarid xabarida chiqadi);
  • 🔔 Xabarnoma — yangi obuna / zaxira haqida mijozlarga xabarni yoqish, sinash, sozlash.
"""
from __future__ import annotations

import html
import io
import json
import logging
import time
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from database.models import Order, OrderStatus, PriceChange, Product, ProductImage, ProductSource, User
from keyboards.admin_kb import admin_main
from locales.texts import money
from services import canboso, guides, overrides, runtime
from services.announce import announce_events, price_line

router = Router(name="admin_shop")
log = logging.getLogger(__name__)

PAGE = 20
GUIDE_MAX = 3000


def _is_admin(user: User | None) -> bool:
    return bool(user) and user.tg_id in settings.admins


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])


class ShopEdit(StatesGroup):
    welcome = State()
    image = State()
    video = State()
    warranty = State()
    brand_emoji = State()
    price = State()
    guide = State()
    notify_min = State()
    support = State()


def _brand(p: Product) -> str:
    return p.brand or "Boshqa"


async def _brand_products(s: AsyncSession, pid: int) -> tuple[str, list[Product]]:
    """pid mahsulotining brendi va shu brenddagi barcha mahsulotlar (nom bo'yicha)."""
    base = await s.get(Product, pid)
    if not base:
        return "", []
    cond = Product.brand == base.brand if base.brand else Product.brand.is_(None)
    rows = list(await s.scalars(select(Product).where(cond).order_by(Product.price, Product.name)))
    return _brand(base), rows


# ─────────────────────────── 💰 Narxlar ───────────────────────────

@router.callback_query(F.data == "a:prices")
async def prices_home(call: CallbackQuery, user: User, session: AsyncSession):
    """Brendlar ro'yxati."""
    if not _is_admin(user):
        return await call.answer()
    prods = list(await session.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name)))
    first: dict[str, Product] = {}
    count: dict[str, int] = {}
    for p in prods:
        b = _brand(p)
        first.setdefault(b, p)
        count[b] = count.get(b, 0) + 1
    kb = InlineKeyboardBuilder()
    for b in sorted(first, key=str.lower):
        kb.button(text=f"{b} · {count[b]}", callback_data=f"a:pb:{first[b].id}:0")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home"))
    await call.message.edit_text(
        "💰 <b>Narxlar</b>\n\nBrendni tanlang, so'ng kerakli mahsulot narxini o'zgartiring.\n"
        "🔒 — narx qo'lda qo'yilgan (avtomatik yangilanishda o'zgarmaydi).",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("a:pb:"))
async def prices_brand(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    _, _, pid, page = call.data.split(":")
    brand, rows = await _brand_products(session, int(pid))
    if not rows:
        return await call.answer("🚫", show_alert=True)
    page = max(0, min(int(page), (len(rows) - 1) // PAGE))
    kb = InlineKeyboardBuilder()
    for p in rows[page * PAGE:(page + 1) * PAGE]:
        lock = "🔒" if "price" in overrides.locked(p) else ""
        off = "" if p.is_active else "🚫 "
        kb.button(text=f"{off}{p.name[:34]} — {p.price:,}{lock}".replace(",", " "), callback_data=f"a:pp:{p.id}:{pid}")
    kb.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"a:pb:{pid}:{page - 1}"))
    if (page + 1) * PAGE < len(rows):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"a:pb:{pid}:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="⬅️ Brendlar", callback_data="a:prices"))
    await call.message.edit_text(
        f"💰 <b>{html.escape(brand)}</b> — {len(rows)} ta mahsulot\nNarxini o'zgartirmoqchi bo'lganingizni bosing:",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


def _price_card(p: Product) -> str:
    lock = "price" in overrides.locked(p)
    mode = "🔒 qo'lda" if lock else "(avtomatik)"
    text = (f"💰 <b>{html.escape(p.name)}</b>\n\n"
            f"Hozirgi narx: <b>{money(p.price)}</b> {mode}\n")
    if canboso.is_supplier_product(p) and p.supplier_price:
        profit = p.price - p.supplier_price
        text += (f"🏭 Ta'minotchi narxi: {money(p.supplier_price)}\n"
                 f"📈 Foyda: <b>{money(profit)}</b> ({profit / p.supplier_price * 100:.0f}%)\n")
        if profit < 0:
            text += "⚠️ <b>Narx ta'minotchi narxidan past — zarar!</b>\n"
    return text + "\nYangi narxni so'mda yuboring (masalan <code>59000</code>)."


@router.callback_query(F.data.startswith("a:pp:"))
async def price_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    _, _, pid, back = call.data.split(":")
    p = await session.get(Product, int(pid))
    if not p:
        return await call.answer("🚫", show_alert=True)
    await state.set_state(ShopEdit.price)
    await state.update_data(pid=p.id, back=int(back))
    rows = [[("⬅️ Orqaga", f"a:pb:{back}:0")]]
    if "price" in overrides.locked(p) and canboso.is_supplier_product(p):
        rows.insert(0, [("↩️ Avtomatik narxga qaytarish", f"a:pauto:{p.id}:{back}")])
    await call.message.edit_text(_price_card(p), reply_markup=_kb(rows))
    await call.answer()


@router.message(ShopEdit.price)
async def price_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    raw = (message.text or "").replace(" ", "").replace(",", "")
    if not raw.isdigit() or not 0 < int(raw) <= 1_000_000_000:
        return await message.answer("❌ Faqat raqam yuboring. Masalan: <code>59000</code>")
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    if not p:
        await state.clear()
        return await message.answer("🚫 Mahsulot topilmadi.", reply_markup=admin_main())
    old = p.price
    p.price = int(raw)
    overrides.lock(p, "price")          # avtomatik yangilash bu narxni o'zgartirmaydi
    if old != p.price:
        session.add(PriceChange(product_id=p.id, product_name=p.name, old_price=old, new_price=p.price,
                                old_supplier=p.supplier_price, new_supplier=p.supplier_price, source="admin"))
    await session.commit()
    await state.clear()
    warn = ""
    if p.supplier_price and p.price < p.supplier_price:
        warn = "\n⚠️ Narx ta'minotchi narxidan past — zarar bo'ladi!"
    await message.answer(
        f"✅ <b>{html.escape(p.name)}</b>\n{money(old)} → <b>{money(p.price)}</b> 🔒{warn}\n"
        "Botda darhol yangi narx ko'rinadi.",
        reply_markup=_kb([[("💰 Shu brend", f"a:pb:{data['back']}:0"), ("💰 Brendlar", "a:prices")]]),
    )


@router.callback_query(F.data.startswith("a:pauto:"))
async def price_auto(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Faqat narxni avtomatik hisobga qaytaradi (nom/tavsif qulfiga tegmaydi)."""
    if not _is_admin(user):
        return await call.answer()
    _, _, pid, back = call.data.split(":")
    p = await session.get(Product, int(pid))
    if not p:
        return await call.answer("🚫", show_alert=True)
    overrides.unlock(p, "price")
    before = p.price
    usd = canboso.product_meta(p).get("usd") if canboso.is_supplier_product(p) else None
    if usd:
        p.supplier_price, p.price = canboso.sell_price_uzs(float(usd), await canboso.usd_rate(), p.name, p.brand or "", canboso.product_meta(p).get("warranty"))
    if before != p.price:
        session.add(PriceChange(product_id=p.id, product_name=p.name, old_price=before, new_price=p.price,
                                old_supplier=p.supplier_price, new_supplier=p.supplier_price, source="admin"))
    await session.commit()
    await state.clear()
    await call.message.edit_text(
        f"↩️ <b>{html.escape(p.name)}</b>: narx avtomatik — <b>{money(p.price)}</b>.",
        reply_markup=_kb([[("💰 Shu brend", f"a:pb:{back}:0"), ("💰 Brendlar", "a:prices")]]),
    )
    await call.answer()


# ─────────────────────────── 📖 Qo'llanma ───────────────────────────

@router.callback_query(F.data.startswith("a:p_guide:"))
async def guide_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p:
        return await call.answer("🚫", show_alert=True)
    await state.set_state(ShopEdit.guide)
    await state.update_data(pid=p.id)
    cur = f"\n\nHozirgi qo'llanma:\n<blockquote>{html.escape(p.guide)}</blockquote>" if p.guide else "\n\nHozircha qo'llanma yo'q."
    await call.message.edit_text(
        f"📖 <b>Qo'llanma: {html.escape(p.name)}</b>\n\n"
        "Mijoz mahsulotni qanday ishlatishi / qanday kirishi haqida matn yuboring. "
        "Har qator — alohida qadam bo'ladi:\n"
        "<code>1) Saytga kiring\n2) Email va parolni kiriting\n3) Profilni tanlang</code>\n\n"
        "Botdagi «Qo'llanma» bo'limida va xariddan keyingi xabarda chiqadi.\n"
        f"O'chirish uchun <code>-</code> yuboring.{cur}",
        reply_markup=_kb([[("⬅️ Orqaga", f"a:prod:{p.id}")]]),
    )
    await call.answer()


@router.message(ShopEdit.guide)
async def guide_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    text = (message.text or "").strip()
    if not text:
        return await message.answer("❌ Matn yuboring (yoki o'chirish uchun <code>-</code>).")
    if len(text) > GUIDE_MAX:
        return await message.answer(f"❌ Juda uzun ({len(text)}). {GUIDE_MAX} belgigacha yozing.")
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    await state.clear()
    if not p:
        return await message.answer("🚫 Mahsulot topilmadi.", reply_markup=admin_main())
    p.guide = None if text == "-" else text
    await session.commit()
    rows = [[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]
    if p.guide and p.brand:
        rows.insert(0, [(f"📋 Hamma {p.brand} tariflariga qo'llash", f"a:guide_all:{p.id}")])
    await message.answer("🗑 Qo'llanma o'chirildi." if not p.guide else "✅ Qo'llanma saqlandi.", reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("a:guide_all:"))
async def guide_all(call: CallbackQuery, user: User, session: AsyncSession):
    """Shu qo'llanmani bir brenddagi barcha tariflarga (7 kun, 1 oy...) nusxalaydi."""
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p or not p.brand or not p.guide:
        return await call.answer("🚫", show_alert=True)
    n = 0
    for q in await session.scalars(select(Product).where(Product.brand == p.brand)):
        if q.guide != p.guide:
            q.guide = p.guide
            n += 1
    await session.commit()
    await call.message.edit_text(f"✅ {p.brand}: qo'llanma yana {n} ta tarifga qo'yildi.",
                                 reply_markup=_kb([[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]))
    await call.answer()


# ─────────────────────────── 🔔 Xabarnoma ───────────────────────────

async def _notify_view(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    total = await session.scalar(select(func.count()).select_from(User).where(User.is_banned.is_(False))) or 0
    on = await session.scalar(
        select(func.count()).select_from(User).where(User.is_banned.is_(False), User.notify.is_(True))) or 0
    state = runtime.notify_enabled()
    text = (
        "🔔 <b>Mijozlarga xabarnoma</b>\n\n"
        "Katalog har 3 daqiqada yangilanganda yangi obuna yoki zaxira to'ldirilsa, mijozlarga "
        "(belgi + nom, qo'shildi, zaxira, narx va «Sotib olish» tugmasi) xabar boradi.\n\n"
        f"Holat: <b>{'✅ yoqiq' if state else '🚫 o‘chiq'}</b>\n"
        f"Zaxira kamida <b>{runtime.notify_min()}</b> ta oshsa xabar beriladi "
        "(0 dan to'lganda va yangi mahsulotda — har doim)\n"
        f"Qabul qiluvchilar: <b>{on}</b> / {total}"
    )
    kb = _kb([
        [("🚫 O'chirish" if state else "✅ Yoqish", "a:ntf_toggle")],
        [("🔢 Minimal miqdor", "a:ntf_min"), ("🧪 Sinab ko'rish", "a:ntf_test")],
        [("⬅️ Orqaga", "a:home")],
    ])
    return text, kb


@router.callback_query(F.data == "a:notify")
async def notify_home(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    text, kb = await _notify_view(session)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "a:ntf_toggle")
async def notify_toggle(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    await runtime.set_value("notify_on", "0" if runtime.notify_enabled() else "1")
    text, kb = await _notify_view(session)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("✅")


@router.callback_query(F.data == "a:ntf_min")
async def notify_min_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ShopEdit.notify_min)
    await call.message.edit_text(
        f"🔢 Hozir: <b>{runtime.notify_min()}</b>\n\nZaxira kamida nechta oshganda xabar yuborilsin? "
        "(1 dan 1000 gacha son, masalan <code>5</code>)",
        reply_markup=_kb([[("⬅️ Orqaga", "a:notify")]]),
    )
    await call.answer()


@router.message(ShopEdit.notify_min)
async def notify_min_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 1000:
        return await message.answer("❌ 1 dan 1000 gacha son yuboring.")
    await runtime.set_value("notify_min", raw)
    await state.clear()
    text, kb = await _notify_view(session)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "a:ntf_test")
async def notify_test(call: CallbackQuery, user: User, session: AsyncSession):
    """Faqat adminning o'ziga namunani yuboradi (mijozlarga emas)."""
    if not _is_admin(user):
        return await call.answer()
    p = await session.scalar(select(Product).where(
        Product.is_active.is_(True), Product.source == ProductSource.API).order_by(Product.id.desc()).limit(1))
    if not p:
        return await call.answer("Faol mahsulot yo'q", show_alert=True)
    await call.answer("Namuna yuborilmoqda…")
    stock = p.stock_qty or 10
    await announce_events(call.bot, [{"id": p.id, "kind": "restock", "added": min(10, stock), "stock": stock}],
                          only_to=[user.tg_id])


# ─────────────────────────── 🏷 Brend emojilari ───────────────────────────

def _lines_with_emoji(message: Message) -> list[tuple[str, str, str]]:
    """Xabardagi har qator uchun (brend nomi, custom_emoji_id, oddiy emoji). Offsetlar UTF-16 birligida."""
    text = message.text or ""
    raw = text.encode("utf-16-le")
    ents = [e for e in (message.entities or []) if e.type == "custom_emoji" and e.custom_emoji_id]
    out, pos = [], 0
    for line in text.split("\n"):
        start = pos
        end = start + len(line.encode("utf-16-le")) // 2
        pos = end + 1
        mine = [e for e in ents if start <= e.offset < end]
        if not mine:
            continue
        name = line
        for e in sorted(mine, key=lambda x: -x.offset):         # emojilarni qatordan olib tashlaymiz
            a, b = (e.offset - start) * 2, (e.offset - start + e.length) * 2
            lb = line.encode("utf-16-le")
            name = (lb[:a] + lb[b:]).decode("utf-16-le")
            line = name
        first = mine[0]
        char = raw[first.offset * 2:(first.offset + first.length) * 2].decode("utf-16-le", "ignore").strip()
        out.append((name.strip(" \t-–—:"), first.custom_emoji_id, char))
    return out


async def _brands(session: AsyncSession) -> list[str]:
    rows = await session.scalars(select(Product.brand).where(Product.brand.is_not(None), Product.is_active.is_(True)).distinct())
    return sorted({b for b in rows if b}, key=str.lower)


@router.callback_query(F.data == "a:bemoji")
async def bemoji_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ShopEdit.brand_emoji)
    brands = await _brands(session)
    have = runtime.brand_emoji()
    todo = [b for b in brands if b not in have]
    await call.message.edit_text(
        "🏷 <b>Brend emojilari</b>\n\n"
        "Yangi obuna / zaxira xabarlarida har bir mahsulot o'z brendining <b>premium emojisi</b> bilan chiqadi.\n\n"
        "Har qatorga <b>brend nomi</b> va yoniga <b>premium emoji</b> yozib yuboring (bir xabarda ko'plab qator mumkin):\n"
        "<code>CapCut ✂️\nChatGPT 🤖\nSpotify 🎧</code>\n"
        "(emoji sifatida premium emoji tanlang). Boshqa brendga tegilmaydi.\n\n"
        f"Saqlangan: <b>{len(have)}</b> ta\n"
        + (f"Emojisiz brendlar: {', '.join(todo[:60])}" if todo else "✅ Hamma brendda emoji bor"),
        reply_markup=_kb([[("📋 Saqlanganlar", "a:bemoji_list"), ("🗑 Tozalash", "a:bemoji_clear")],
                          [("⬅️ Tayyor", "a:home")]]),
    )
    await call.answer()


@router.message(ShopEdit.brand_emoji)
async def bemoji_save(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        return
    rows = _lines_with_emoji(message)
    if not rows:
        return await message.answer("❌ Premium emoji topilmadi. Har qatorda brend nomi + premium emoji bo'lsin.")
    known = {b.lower(): b for b in await _brands(session)}
    cur = runtime.brand_emoji()
    saved, unknown = [], []
    for name, cid, char in rows:
        brand = known.get(name.lower())
        if not brand:
            unknown.append(name or "—")
            continue
        cur[brand] = {"id": cid, "char": char or "⭐"}
        saved.append(f"{char} {brand}")
    await runtime.set_value("brand_emoji", json.dumps(cur, ensure_ascii=False))
    text = (f"✅ Saqlandi: {', '.join(saved)}" if saved else "❌ Hech narsa saqlanmadi.")
    if unknown:
        text += f"\n⚠️ Bunday brend yo'q: {html.escape(', '.join(unknown))}\nBrend nomini aynan ro'yxatdagidek yozing."
    await message.answer(text + "\n\nYana yuborishingiz mumkin.",
                         reply_markup=_kb([[("⬅️ Tayyor", "a:home")]]))


@router.callback_query(F.data == "a:bemoji_list")
async def bemoji_list(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    have = runtime.brand_emoji()
    await call.answer(("Saqlangan: " + ", ".join(f"{v.get('char', '')}{b}" for b, v in have.items()))[:190]
                      if have else "Hali hech narsa yo'q", show_alert=True)


@router.callback_query(F.data == "a:bemoji_clear")
async def bemoji_clear(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    await runtime.set_value("brand_emoji", None)
    await call.answer("🗑 Tozalandi", show_alert=True)


# ─────────────────────────── 🛡 Kafolat matni ───────────────────────────

@router.callback_query(F.data.startswith("a:p_warr:"))
async def warr_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p:
        return await call.answer("🚫", show_alert=True)
    await state.set_state(ShopEdit.warranty)
    await state.update_data(pid=p.id)
    auto = guides.warranty_note(Product(brand=p.brand, source=p.source, external_id=p.external_id,
                                        supplier_data=p.supplier_data, warranty_note=None))
    await call.message.edit_text(
        f"🛡 <b>Kafolat matni: {html.escape(p.name)}</b>\n\n"
        "Mijoz botda <b>shu obunani tanlaganda va xariddan keyin</b> ko'radigan matn. Masalan:\n"
        "<code>12 soat ichida login va parollarni almashtirib olasiz, hech qanday muammo bo'lmaydi</code>\n\n"
        f"Hozir: <blockquote>{html.escape(p.warranty_note or auto or 'yo‘q (matn chiqmaydi)')}</blockquote>"
        f"{'' if p.warranty_note else '(avtomatik — ta’minotchi muddatidan)'}\n\n"
        "Yangi matnni yuboring. <code>-</code> — o'zimiz yozgan matnni o'chirib, avtomatikka qaytarish.",
        reply_markup=_kb([[("⬅️ Orqaga", f"a:prod:{p.id}")]]),
    )
    await call.answer()


@router.message(ShopEdit.warranty)
async def warr_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    text = (message.text or "").strip()
    if not text or len(text) > 600:
        return await message.answer("❌ Matn yuboring (600 belgigacha) yoki <code>-</code>.")
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    await state.clear()
    if not p:
        return await message.answer("🚫 Mahsulot topilmadi.", reply_markup=admin_main())
    p.warranty_note = None if text == "-" else text
    rows = [[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]
    if p.warranty_note and p.brand:
        rows.insert(0, [(f"📋 Hamma {p.brand} tariflariga qo'llash", f"a:warr_all:{p.id}")])
    await session.commit()
    await message.answer("✅ Kafolat matni saqlandi." if p.warranty_note else "↩️ Avtomatik matnga qaytdi.",
                         reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("a:warr_all:"))
async def warr_all(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p or not p.brand or not p.warranty_note:
        return await call.answer("🚫", show_alert=True)
    n = 0
    for q in await session.scalars(select(Product).where(Product.brand == p.brand)):
        if q.warranty_note != p.warranty_note:
            q.warranty_note = p.warranty_note
            n += 1
    await session.commit()
    await call.message.edit_text(f"✅ {p.brand}: kafolat matni yana {n} ta tarifga qo'yildi.",
                                 reply_markup=_kb([[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]))
    await call.answer()


# ─────────────────────────── 🎬 Video qo'llanma ───────────────────────────

@router.callback_query(F.data.startswith("a:p_video:"))
async def video_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p:
        return await call.answer("🚫", show_alert=True)
    await state.set_state(ShopEdit.video)
    await state.update_data(pid=p.id)
    cur = ("havola: " + html.escape(p.guide_video)) if (p.guide_video or "").startswith("http") else (
        "yuklangan video ✅" if p.guide_video else "yo'q")
    await call.message.edit_text(
        f"🎬 <b>Video qo'llanma: {html.escape(p.name)}</b>\n\n"
        "<b>Videoni shu yerga yuboring</b> (Telegram'ga yuklangan fayl, 20 MB gacha) yoki video <b>havolasini</b> "
        "(YouTube va h.k.) yuboring.\n"
        "• botdagi «Qo'llanma» bo'limida video ham yuboriladi;\n"
        "• xariddan keyin video mijozga botda avtomatik yuboriladi.\n\n"
        f"Hozir: {cur}\nO'chirish uchun <code>-</code> yuboring.",
        reply_markup=_kb([[("⬅️ Orqaga", f"a:prod:{p.id}")]]),
    )
    await call.answer()


@router.message(ShopEdit.video)
async def video_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    ref = None
    if message.video:
        ref = "tg:" + message.video.file_id
    elif message.animation:
        ref = "tg:" + message.animation.file_id
    elif message.document and (message.document.mime_type or "").startswith("video/"):
        ref = "tg:" + message.document.file_id
    else:
        text = (message.text or "").strip()
        if text == "-":
            ref = ""
        elif text.startswith(("http://", "https://")) and len(text) <= 500 and " " not in text:
            ref = text
    if ref is None:
        return await message.answer("❌ Video fayl yoki http(s) havola yuboring (o'chirish uchun <code>-</code>).")
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    await state.clear()
    if not p:
        return await message.answer("🚫 Mahsulot topilmadi.", reply_markup=admin_main())
    p.guide_video = ref or None
    await session.commit()
    rows = [[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]
    if ref and p.brand:
        rows.insert(0, [(f"📋 Hamma {p.brand} tariflariga qo'llash", f"a:video_all:{p.id}")])
    await message.answer("✅ Video qo'llanma saqlandi." if ref else "🗑 Video qo'llanma o'chirildi.", reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("a:video_all:"))
async def video_all(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p or not p.brand or not p.guide_video:
        return await call.answer("🚫", show_alert=True)
    n = 0
    for q in await session.scalars(select(Product).where(Product.brand == p.brand)):
        if q.guide_video != p.guide_video:
            q.guide_video = p.guide_video
            n += 1
    await session.commit()
    await call.message.edit_text(f"✅ {p.brand}: video qo'llanma yana {n} ta tarifga qo'yildi.",
                                 reply_markup=_kb([[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]))
    await call.answer()


# ─────────────────────────── 👤 Mijoz kabineti: buyurtmalari ───────────────────────────

@router.callback_query(F.data.startswith("a:u_orders:"))
async def user_orders(call: CallbackQuery, user: User, session: AsyncSession):
    """Mijozning barcha buyurtmalari: nima olgan, qachon, qancha. Birini ochsangiz login/parol ko'rinadi."""
    if not _is_admin(user):
        return await call.answer()
    tg_id = int(call.data.split(":")[2])
    u = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not u:
        return await call.answer("🚫", show_alert=True)
    rows = list(await session.scalars(
        select(Order).where(Order.user_id == u.id).options(selectinload(Order.items))
        .order_by(Order.id.desc()).limit(30)))
    icon = {OrderStatus.DELIVERED: "✅", OrderStatus.PAID: "🟡", OrderStatus.CANCELLED: "❌", OrderStatus.REFUNDED: "↩️"}
    kb = InlineKeyboardBuilder()
    for o in rows:
        names = ", ".join(i.product_name for i in o.items)[:28]
        kb.button(text=f"{icon.get(o.status, '•')} #{o.id} · {o.created_at:%d.%m} · {money(o.total)} · {names}",
                  callback_data=f"a:order:{o.id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Mijoz kabineti", callback_data=f"a:user:{tg_id}"))
    await call.message.edit_text(
        f"🧾 <b>{html.escape(u.full_name)}</b> buyurtmalari ({len(rows)})\n\n"
        "Buyurtmani bossangiz: nima olgani, kiritgan emaili, <b>login/parol</b> va ta'minotchi buyurtma kodi ko'rinadi.",
        reply_markup=kb.as_markup() if rows else _kb([[("⬅️ Mijoz kabineti", f"a:user:{tg_id}")]]),
    )
    await call.answer()


# ─────────────────────────── 📈 Narx o'zgarishlari ───────────────────────────

CHG_PAGE = 10


@router.callback_query(F.data.startswith("a:pchg:"))
async def price_changes(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Qaysi obunalarning narxi o'zgargani (ta'minotchi narxi, kurs yoki admin). Birini bossangiz — mahsulot kartasi."""
    if not _is_admin(user):
        return await call.answer()
    await state.clear()
    _, _, hours, page = call.data.split(":")
    hours, page = int(hours), int(page)
    since = datetime.utcnow() - timedelta(hours=hours)
    total = await session.scalar(select(func.count()).select_from(PriceChange).where(PriceChange.created_at >= since)) or 0
    page = max(0, min(page, max(total - 1, 0) // CHG_PAGE))
    rows = list(await session.scalars(
        select(PriceChange).where(PriceChange.created_at >= since)
        .order_by(PriceChange.id.desc()).offset(page * CHG_PAGE).limit(CHG_PAGE)))
    kb = InlineKeyboardBuilder()
    lines = []
    for c in rows:
        arrow = "🔺" if c.new_price > c.old_price else "🔻"
        who = {"admin": " ✏️"}.get(c.source, "")
        lines.append(f"{price_line(c.product_name, c.old_price, c.new_price)}{who} · {c.created_at:%d.%m %H:%M}")
        if c.product_id:
            kb.button(text=f"{arrow} {c.product_name[:30]} → {c.new_price:,}".replace(",", " "),
                      callback_data=f"a:prod:{c.product_id}")
    kb.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"a:pchg:{hours}:{page - 1}"))
    if (page + 1) * CHG_PAGE < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"a:pchg:{hours}:{page + 1}"))
    if nav:
        kb.row(*nav)
    other = 168 if hours == 24 else 24
    kb.row(InlineKeyboardButton(text="📅 7 kun" if hours == 24 else "🕐 24 soat", callback_data=f"a:pchg:{other}:0"),
           InlineKeyboardButton(text="🔔 Ogohlantirish: " + ("yoqiq" if runtime.price_alert_enabled() else "o‘chiq"),
                                callback_data=f"a:pchg_alert:{hours}"))
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home"))
    await call.message.edit_text(
        f"📈 <b>Narx o'zgarishlari</b> — oxirgi {'24 soat' if hours == 24 else '7 kun'}: <b>{total}</b> ta\n\n"
        + ("\n".join(lines) if lines else "O'zgarish yo'q.")
        + "\n\n🔺 qimmatlashdi · 🔻 arzonlashdi · ✏️ siz o'zgartirgansiz\nMahsulotni bosing: narx yoki 🖼 rasm qo'yish.",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("a:pchg_alert:"))
async def price_alert_toggle(call: CallbackQuery, user: User):
    if not _is_admin(user):
        return await call.answer()
    await runtime.set_value("price_alert", "0" if runtime.price_alert_enabled() else "1")
    await call.answer("🔔 Ogohlantirish yoqildi" if runtime.price_alert_enabled() else "🔕 Ogohlantirish o'chirildi", show_alert=True)


# ─────────────────────────── 🖼 Mahsulot rasmi ───────────────────────────

IMG_MAX = 3_000_000


@router.callback_query(F.data.startswith("a:p_img:"))
async def image_start(call: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    if not p:
        return await call.answer("🚫", show_alert=True)
    await state.set_state(ShopEdit.image)
    await state.update_data(pid=p.id)
    has = bool(await session.get(ProductImage, p.id))
    await call.message.edit_text(
        f"🖼 <b>Rasm: {html.escape(p.name)}</b>\n\n"
        "Mahsulot rasmini yuboring (oddiy rasm sifatida). U kanal e'lonlarida chiqadi va "
        "yangi obuna / zaxira xabarlariga qo'shiladi.\n"
        "Kvadrat rasm yaxshi chiqadi.\n\n"
        f"Hozir: {'rasm bor ✅' if has else 'yo‘q'}\nO'chirish uchun <code>-</code> yuboring.",
        reply_markup=_kb([[("⬅️ Orqaga", f"a:prod:{p.id}")]]),
    )
    await call.answer()


async def _save_image(session: AsyncSession, p: Product, data: bytes, mime: str, file_id: str | None) -> None:
    img = await session.get(ProductImage, p.id)
    if img:
        img.data, img.mime, img.tg_file_id, img.updated_at = data, mime, file_id, datetime.utcnow()
    else:
        session.add(ProductImage(product_id=p.id, data=data, mime=mime, tg_file_id=file_id))
    p.image_url = f"/media/p/{p.id}?v={int(time.time())}"
    overrides.lock(p, "image")           # ta'minotchi/sinxronlash bu rasmni almashtirmaydi


@router.message(ShopEdit.image)
async def image_save(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if not _is_admin(user):
        return
    data = await state.get_data()
    p = await session.get(Product, data["pid"])
    if not p:
        await state.clear()
        return await message.answer("🚫 Mahsulot topilmadi.", reply_markup=admin_main())
    rows = [[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]
    if (message.text or "").strip() == "-":
        img = await session.get(ProductImage, p.id)
        if img:
            await session.delete(img)
        if (p.image_url or "").startswith("/media/"):
            p.image_url = None
        overrides.unlock(p, "image")
        await session.commit()
        await state.clear()
        return await message.answer("🗑 Rasm o'chirildi.", reply_markup=_kb(rows))
    file_id, mime, size = None, "image/jpeg", 0
    if message.photo:
        ph = message.photo[-1]
        for cand in reversed(message.photo):            # eng kattasi emas, 1280 px gacha bo'lgani yetarli
            if (cand.file_size or 0) <= IMG_MAX:
                ph = cand
                break
        file_id, size = ph.file_id, ph.file_size or 0
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id, mime, size = message.document.file_id, message.document.mime_type, message.document.file_size or 0
    if not file_id:
        return await message.answer("❌ Rasm yuboring (yoki o'chirish uchun <code>-</code>).")
    if size > IMG_MAX:
        return await message.answer("❌ Rasm juda katta (3 MB gacha).")
    buf = io.BytesIO()
    await message.bot.download(file_id, destination=buf)
    await _save_image(session, p, buf.getvalue(), mime, file_id)
    await session.commit()
    await state.clear()
    if p.brand:
        rows.insert(0, [(f"📋 Hamma {p.brand} tariflariga qo'yish", f"a:img_all:{p.id}")])
    await message.answer("✅ Rasm saqlandi.", reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("a:img_all:"))
async def image_all(call: CallbackQuery, user: User, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    p = await session.get(Product, int(call.data.split(":")[2]))
    img = await session.get(ProductImage, p.id) if p else None
    if not p or not p.brand or not img:
        return await call.answer("🚫", show_alert=True)
    n = 0
    for q in await session.scalars(select(Product).where(Product.brand == p.brand, Product.id != p.id)):
        await _save_image(session, q, img.data, img.mime, img.tg_file_id)
        n += 1
    await session.commit()
    await call.message.edit_text(f"✅ {p.brand}: rasm yana {n} ta tarifga qo'yildi.",
                                 reply_markup=_kb([[("📦 Mahsulotga qaytish", f"a:prod:{p.id}")]]))
    await call.answer()


# ─────────────────────────── 👋 /start salomlashuvi ───────────────────────────

WELCOME_MAX = 3500


@router.callback_query(F.data == "a:welcome")
async def welcome_start(call: CallbackQuery, user: User, state: FSMContext):
    """Hozirgi salomlashuvni ko'rsatadi; admin uni nusxalab, tahrirlab (premium emoji qo'shib) qayta yuboradi."""
    if not _is_admin(user):
        return await call.answer()
    from handlers.start import welcome_text
    from keyboards.user_kb import open_app_kb
    await state.set_state(ShopEdit.welcome)
    await call.message.edit_text(
        "👋 <b>/start salomlashuvi</b>\n\n"
        "Pastdagi xabar hozir mijozlar ko'radigan matn. Uni <b>nusxalab</b>, tahrirlang (premium emoji, qalin yozuv va h.k. qo'shing) "
        "va <b>menga qayta yuboring</b> — shu matn saqlanadi.\n"
        "• Ismingiz o'rniga avtomatik «mijoz ismi» qo'yiladi.\n"
        "• Standart matnga qaytish uchun <code>-</code> yuboring.",
        reply_markup=_kb([[("⬅️ Orqaga", "a:home")]]),
    )
    try:
        await call.message.answer(welcome_text(user, "uz", bool(open_app_kb("uz"))))
    except Exception:  # noqa: BLE001
        pass
    await call.answer()


@router.message(ShopEdit.welcome)
async def welcome_save(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    raw = (message.text or "").strip()
    if raw == "-":
        await runtime.set_value("welcome_html", None)
        await state.clear()
        return await message.answer("↩️ Standart salomlashuv qaytdi.", reply_markup=_kb([[("⬅️ Admin panel", "a:home")]]))
    if not message.text or len(message.text) > WELCOME_MAX:
        return await message.answer(f"❌ Matn yuboring ({WELCOME_MAX} belgigacha). Rasm yoki fayl emas, faqat matn.")
    body = message.html_text                       # premium emoji (<tg-emoji>), qalin, havola va h.k. saqlanadi
    for name in {user.full_name or "", message.from_user.full_name if message.from_user else ""}:
        if name.strip():
            body = body.replace(html.escape(name, quote=False), "{name}")     # admin ismi → «mijoz ismi»
    await runtime.set_value("welcome_html", body)
    await state.clear()
    from handlers.start import welcome_text
    await message.answer("✅ Saqlandi. Mijozlarga shunday ko'rinadi:", reply_markup=_kb([[("⬅️ Admin panel", "a:home")]]))
    try:
        await message.answer(welcome_text(user, "uz", True))
    except Exception:  # noqa: BLE001
        await message.answer("⚠️ Matnda yaroqsiz belgilash bor — mijozlarga standart matn yuboriladi. Qayta yuborib ko'ring.")


@router.message(Command("kanal"))
async def channel_test(message: Message, user: User):
    """/kanal — kanalga sinov posti yuboradi va qaysi yo'l ishlaganini ko'rsatadi (premium emojilar uchun)."""
    if not _is_admin(user):
        return
    from services import announce, cardbridge
    chat = settings.announce_chat
    if not chat:
        return await message.answer("❌ Kanal sozlanmagan (ANNOUNCE_CHANNEL_ID).")
    me = await message.bot.get_me()
    text = ("🧪 <b>Sinov posti</b>\n"
            f"{announce.e('🤖', '6134246530380472478')} ChatGPT · {announce.e('💎', '5796314805564346672')} Gemini · "
            f"{announce.e('✂️', '5364339557712020484')} CapCut\n"
            f"{announce.e('➕', '5393194986252542669')} Qo'shildi: <b>1</b>\n"
            f"{announce.e('💵', '5879991085001871624')} Narxi: <b>1 000 so'm</b>")
    ok = await announce.post_to_channel(message.bot, text, me.username)
    c = announce.CHANNEL
    mode = {"user": "👤 Premium akkaunt (TG_SESSION) nomidan — premium emojilar ko'rinadi"
                    + (" + yashil «Sotib olish» tugmasi" if not c["error"] else " (tugma o'rniga matnli havola)"),
            "bot": "🤖 Bot nomidan (premium emoji faqat bot egasida Premium bo'lsa chiqadi)",
            "xato": "❌ Yuborilmadi"}.get(c["mode"], c["mode"])
    lines = [f"{'✅' if ok else '❌'} Kanal: <code>{html.escape(str(chat))}</code>", f"Yo'l: {mode}"]
    if c["error"]:
        lines.append(f"Sabab: <code>{html.escape(c['error'])}</code>")
    if settings.announce_via_user and cardbridge.CLIENT is None:
        lines.append("ℹ️ TG_SESSION ulanmagan — Premium akkaunt orqali yuborib bo'lmaydi.")
    if "Tugma qo'yilmadi" in c["error"]:
        lines.append("👉 Botni kanalda admin qiling va «Boshqalarning xabarlarini tahrirlash» huquqini bering — shunda yashil tugma qo'shiladi.")
    elif c["error"] and ("ChatAdmin" in c["error"] or "Forbidden" in c["error"] or "Admin" in c["error"]):
        lines.append("👉 TG_SESSION akkauntini kanalga admin qiling (post yuborish huquqi bilan).")
    await message.answer("\n".join(lines))


@router.callback_query(F.data == "a:support")
async def support_start(call: CallbackQuery, user: User, state: FSMContext):
    if not _is_admin(user):
        return await call.answer()
    await state.set_state(ShopEdit.support)
    cur = runtime.support_username()
    await call.message.edit_text(
        "🆘 <b>Yordam markazi</b>\n\n"
        f"Hozir: {'@' + html.escape(cur) if cur else 'ko‘rsatilmagan'}\n"
        "Botdagi «Yordam» tugmasi, xariddan keyingi «yozish» tugmasi, kafolat murojaati va to'lov xabarlari shu akkauntga olib boradi.\n\n"
        "Yangi username yuboring (masalan <code>@Servisaiuz</code>).\n<code>-</code> — standart (.env) qiymatga qaytarish.",
        reply_markup=_kb([[("⬅️ Admin panel", "a:home")]]),
    )
    await call.answer()


@router.message(ShopEdit.support)
async def support_save(message: Message, user: User, state: FSMContext):
    if not _is_admin(user):
        return
    raw = (message.text or "").strip()
    if raw == "-":
        await runtime.set_value("support", None)
        await state.clear()
        return await message.answer(f"↩️ Standart qiymat: @{html.escape(runtime.support_username() or '—')}",
                                    reply_markup=_kb([[("⬅️ Admin panel", "a:home")]]))
    name = raw.replace("https://t.me/", "").lstrip("@").strip("/ ")
    import re as _re
    if not _re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", name):
        return await message.answer("❌ Username noto'g'ri. Masalan: <code>@Servisaiuz</code> (4–32 belgi: harf, raqam, _).")
    await runtime.set_value("support", name)
    await state.clear()
    await message.answer(f"✅ Yordam markazi: @{html.escape(name)}\nBotda va xabarlarda darhol shu akkaunt chiqadi.",
                         reply_markup=_kb([[("⬅️ Admin panel", "a:home")]]))


@router.callback_query(F.data.startswith("a:sale:"))
async def sale_report_view(call: CallbackQuery, user: User):
    """📈 Savdo hisoboti: bugun / 10 kun / 30 kun — nechta savdo, nima ko'p olingan, foyda."""
    if not _is_admin(user):
        return await call.answer()
    from services import stats
    days = int(call.data.split(":")[2])
    if days not in stats.PERIODS:
        return await call.answer()
    row = [InlineKeyboardButton(text=("• " if d == days else "") + ("Bugun" if d == 1 else f"{d} kun"), callback_data=f"a:sale:{d}")
           for d in stats.PERIODS]
    markup = InlineKeyboardMarkup(inline_keyboard=[row, [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="a:home")]])
    try:
        bal = await canboso.balance_line() if settings.canboso_api_key else ""
        await call.message.edit_text(stats.report_text(await stats.report(days)) + (f"\n\n{bal}" if bal else ""), reply_markup=markup)
    except Exception:  # noqa: BLE001 — matn o'zgarmagan bo'lsa Telegram xato beradi
        pass
    await call.answer()
