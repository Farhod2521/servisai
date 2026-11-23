"""Admin: ta'minotchi (API) ro'yxatidan istalgan mahsulotni do'konga qo'shish va olib tashlash.

Do'kon qoidalarga (services/curation.py) to'g'ri keladigan mahsulotlarni o'zi qo'yadi. Qoidalarga to'g'ri kelmaganlarini yoki
menyuda yo'q brendlarni admin shu yerdan qo'lda qo'shadi: ular qoidalarga qaramasdan do'konda ko'rinadi (brend menyuga o'zi qo'shiladi).
"""
from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Product
from locales.texts import money
from services import curation, overrides, runtime
from services.catalog_sync import CatalogError, sync_catalog

router = Router(name="admin_api")
log = logging.getLogger("uzshop.admin_api")

PAGE = 6
BACK = "a:s:shop"


def _is_admin(user) -> bool:
    return user.tg_id in settings.admins


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


async def _edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:       # «message is not modified»
        pass


def _rules_text() -> str:
    return ("<i>Qoidalar: obunalar — kafolat kamida %d kun · API — faqat $%s, kafolati bor (kamida 24 soat). "
            "Qolgan brendlar menyuda yo'q.</i>" % (curation.SUB_MIN_WARRANTY_DAYS, " va $".join(str(x) for x in sorted(curation.API_AMOUNTS))))


def _brands(rows: list[dict]) -> list[str]:
    return sorted({r["brand"] or "—" for r in rows})


@router.callback_query(F.data.regexp(r"^a:api:\d+:-?\d+$"))
async def api_list(call: CallbackQuery, user, session: AsyncSession):
    if not _is_admin(user):
        return await call.answer()
    _, _, page_s, b_s = call.data.split(":")
    await _render_list(call, int(page_s), int(b_s))
    await call.answer()


async def _render_list(call: CallbackQuery, page: int, bi: int) -> None:
    """Do'konda ko'rinmaydigan API mahsulotlari: sahifalab, brend bo'yicha filtr bilan."""
    rows = curation.hidden_items()
    if not curation.CATALOG:
        await _edit(call, "🌐 <b>API'dan qo'shish</b>\n\nKatalog hali yuklanmagan. Bosh sahifadagi «📦 Katalog» qismini tekshiring "
                          "yoki «🔄 Katalogni yangilash» ni bosing.", InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Orqaga", BACK)]]))
        return
    brands = _brands(rows)
    label = "hamma brend"
    if 0 <= bi < len(brands):
        label = brands[bi]
        rows = [r for r in rows if (r["brand"] or "—") == label]
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    page = min(max(page, 0), pages - 1)
    chunk = rows[page * PAGE:(page + 1) * PAGE]
    force = runtime.api_force()
    lines = [f"🌐 <b>API'dan qo'shish</b> · {html.escape(label)}",
             f"Do'konda yo'qlari: <b>{len(rows)}</b> ta · sahifa {page + 1}/{pages}", "", _rules_text(), ""]
    if not chunk:
        lines.append("Bu yerda qo'shiladigan mahsulot qolmadi. 👌")
    for i, r in enumerate(chunk, 1):
        w = r["warranty"] or "kafolat ko'rsatilmagan"
        lines.append(f"<b>{i}.</b> {html.escape(r['name'])} · <b>${r['usd']:g}</b> → {money(r['price'])}\n"
                     f"   🛡 {html.escape(w)} · zaxira {r['available']}\n   ⚠️ <i>{html.escape(r['reason'])}</i>")
    rows_kb = [[_btn(f"➕ {i}", f"a:apiadd:{r['id']}") for i, r in enumerate(chunk[:3], 1)],
               [_btn(f"➕ {i}", f"a:apiadd:{r['id']}") for i, r in enumerate(chunk[3:], 4)]]
    rows_kb = [r for r in rows_kb if r]
    nav = []
    if page > 0:
        nav.append(_btn("◀️", f"a:api:{page - 1}:{bi}"))
    if page < pages - 1:
        nav.append(_btn("▶️", f"a:api:{page + 1}:{bi}"))
    if nav:
        rows_kb.append(nav)
    rows_kb.append([_btn("🏷 Brend tanlash", "a:apibr"), _btn(f"📋 Qo'shilganlar ({len(force)})", "a:apix")])
    rows_kb.append([_btn("⬅️ Orqaga", BACK)])
    await _edit(call, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows_kb))


@router.callback_query(F.data == "a:apibr")
async def api_brands(call: CallbackQuery, user):
    if not _is_admin(user):
        return await call.answer()
    rows = curation.hidden_items()
    brands = _brands(rows)
    counts = {b: sum(1 for r in rows if (r["brand"] or "—") == b) for b in brands}
    kb = [[_btn(f"📋 Hammasi ({len(rows)})", "a:api:0:-1")]]
    pair: list[InlineKeyboardButton] = []
    for i, b in enumerate(brands[:40]):
        pair.append(_btn(f"{b} ({counts[b]})", f"a:api:0:{i}"))
        if len(pair) == 2:
            kb.append(pair)
            pair = []
    if pair:
        kb.append(pair)
    kb.append([_btn("⬅️ Orqaga", "a:api:0:-1")])
    await _edit(call, "🏷 <b>Brendni tanlang</b>\n\nDo'konda yo'q mahsulotlar brend bo'yicha:", InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("a:apiadd:"))
async def api_add(call: CallbackQuery, user, session: AsyncSession):
    """Mahsulotni do'konga qo'shadi (qoidalarga qaramasdan) va katalogni darhol yangilaydi."""
    if not _is_admin(user):
        return await call.answer()
    ext = call.data.split(":", 2)[2]
    force = runtime.api_force()
    force.add(ext)
    await runtime.set_api_force(force)
    p = await session.scalar(select(Product).where(Product.external_id == ext))
    if p is not None:
        overrides.unlock(p, "hidden")
        await session.commit()
    note = "✅ Qo'shildi"
    try:
        await sync_catalog(session)
    except CatalogError as ex:
        note = "✅ Ro'yxatga qo'shildi, katalog keyingi yangilanishda yuklanadi (%s)" % str(ex)[:120]
    item = curation.CATALOG.get(ext)
    if item:
        item["shown"] = True
    await call.answer(note, show_alert=len(note) > 40)
    await _render_list(call, 0, -1)


@router.callback_query(F.data == "a:apix")
async def api_added(call: CallbackQuery, user, session: AsyncSession):
    """Admin qo'shgan mahsulotlar: olib tashlash."""
    if not _is_admin(user):
        return await call.answer()
    force = sorted(runtime.api_force())
    lines = ["📋 <b>Admin qo'shgan mahsulotlar</b>", ""]
    kb: list[list[InlineKeyboardButton]] = []
    if not force:
        lines.append("Hali hech narsa qo'shilmagan. «🌐 API'dan qo'shish» orqali qo'shasiz.")
    for ext in force[:30]:
        p = await session.scalar(select(Product).where(Product.external_id == ext))
        info = curation.CATALOG.get(ext) or {}
        name = (p.name if p else info.get("name")) or ext
        lines.append(f"• {html.escape(name)}")
        kb.append([_btn(f"❌ {name[:40]}", f"a:apidel:{ext}")])
    kb.append([_btn("🌐 API'dan qo'shish", "a:api:0:-1")])
    kb.append([_btn("⬅️ Orqaga", BACK)])
    await _edit(call, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("a:apidel:"))
async def api_remove(call: CallbackQuery, user, session: AsyncSession):
    """Qo'shilgan mahsulotni do'kondan olib tashlaydi (yashiradi). Kerak bo'lsa qayta qo'shish mumkin."""
    if not _is_admin(user):
        return await call.answer()
    ext = call.data.split(":", 2)[2]
    force = runtime.api_force()
    force.discard(ext)
    await runtime.set_api_force(force)
    p = await session.scalar(select(Product).where(Product.external_id == ext))
    if p is not None:
        p.is_active = False
        overrides.lock(p, "hidden")
        await session.commit()
    item = curation.CATALOG.get(ext)
    if item:
        item["shown"], item["reason"] = False, item["reason"] or "Admin olib tashlagan"
    await call.answer("🗑 Do'kondan olib tashlandi")
    await api_added(call, user, session)


@router.message(Command("apimatn"))
async def api_texts(message: Message, user):
    """Admin: ta'minotchi katalogidagi brend mahsulotlarining asl nomi, kafolati va (bo'lsa) yo'riqnoma matnlari.
    Masalan: /apimatn gemini — qo'llanmalarni to'g'ri yozish uchun ta'minotchi matnini ko'rish."""
    if not _is_admin(user):
        return
    q = (message.text or "").split(maxsplit=1)[1].strip().lower() if len((message.text or "").split(maxsplit=1)) > 1 else ""
    if not curation.CATALOG:
        return await message.answer("Katalog hali yuklanmagan. Bir ozdan keyin urinib ko'ring.")
    if not q:
        brands = sorted({r["brand"] for r in curation.CATALOG.values() if r["brand"]})
        return await message.answer("Brendni yozing, masalan: <code>/apimatn gemini</code>\n\nBor brendlar: " + html.escape(", ".join(brands)))
    rows = [r for r in curation.CATALOG.values() if q in (r["brand"] or "").lower() or q in r["raw"].lower()]
    if not rows:
        return await message.answer("Bunday brend/mahsulot ta'minotchi ro'yxatida topilmadi.")
    chunks, cur = [], ""
    for r in sorted(rows, key=lambda r: (r["brand"] or "", r["raw"])):
        block = [f"• <b>{html.escape(r['raw'])}</b> · ${r['usd']:g} · zaxira {r['available']}",
                 f"  🛡 {html.escape(r['warranty'] or 'kafolat yozilmagan')} · " + ("do'konda ✅" if r["shown"] else "do'konda yo'q: " + html.escape(r["reason"] or "—"))]
        block += [f"  📄 {html.escape(t[:600])}" for t in (r.get("info") or [])[:4]]
        text = "\n".join(block) + "\n\n"
        if len(cur) + len(text) > 3500:
            chunks.append(cur)
            cur = ""
        cur += text
    chunks.append(cur)
    for c in chunks[:6]:
        await message.answer(c.strip())
    if len(chunks) > 6:
        await message.answer(f"… yana {len(rows)} dan ko'pi bor, aniqroq nom yozing.")
