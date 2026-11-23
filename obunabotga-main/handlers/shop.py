"""Do'kon: obunalar, hisobni to'ldirish, buyurtmalar, profil, qo'llanma, yordam.

Pastki menyu tugmalari har qanday holatda ishlaydi (kutilayotgan email/akkaunt kiritish bekor bo'ladi).
Obunalar ro'yxati ta'minotchi katalogidan (har 5 daqiqada yangilanadi) olinadi: zaxirasi bor brend — yashil,
tugagan — qizil tugma. Brend logotipi — premium emoji.
"""
from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from database.models import Category, Product, ProductSource, User
from keyboards.user_kb import BLUE, RED, green_button, main_menu, menu_labels, service_button
from locales.texts import LANGS, money, t
from services import brand_emoji, canboso, cards, curation, fulfillment, overrides, repo, runtime, topup
from services.emoji import e as emoji_html, premium_ok
from services.guides import guide_of, has_video
from services.notify import _steps, notify_admins_order, order_success_text
from webapp.api import _deliver_video, _extras, _send_videos

router = Router(name="shop")
log = logging.getLogger("uzshop.shop")

# Do'konda ko'rsatiladigan obunalar (brend nomi services/canboso.py dagi bilan bir xil). Tartib shu.
SERVICES = list(curation.BASE_BRANDS)
MENU_BRANDS = {*curation.BASE_BRANDS, *curation.EXTRA_BRANDS}     # menyuda o'zi chiqadigan brendlar (admin qo'shmasdan)
LABELS = menu_labels()


class Buy(StatesGroup):
    email = State()
    accounts = State()


# ─────────────────────────── Katalog yordamchilari ───────────────────────────

def sold_out_visible(p: Product) -> bool:
    """Ta'minotchida bor, lekin zaxirasi tugagan (qizil ko'rinadi). Admin yashirgan yoki ro'yxatdan chiqqanlar kirmaydi."""
    return (not p.is_active) and p.source == ProductSource.API and p.stock_qty == 0 and "hidden" not in overrides.locked(p)


async def brand_products(s: AsyncSession, brand: str) -> list[Product]:
    """Brendning mahsulotlari: faol + (tugagan, lekin ta'minotchida hali bor). Asosiy 10 ta brenddan tashqari brendlarda —
    faqat admin qo'lda qo'shganlari."""
    q = (select(Product).join(Category, Category.id == Product.category_id)
         .where(Category.is_active.is_(True), Product.brand == brand)
         .options(selectinload(Product.stock)).order_by(Product.price, Product.id))
    if brand not in MENU_BRANDS:
        q = q.where(Product.external_id.in_(runtime.api_force() or {""}))
    return [p for p in await s.scalars(q) if p.is_active or sold_out_visible(p)]


async def shop_brands(s: AsyncSession) -> list[str]:
    """Menyudagi brendlar: faqat ko'rsatiladigan mahsuloti BOR brendlar (sotuvda — yashil, hammasi tugagan — qizil).
    Mahsuloti umuman yo'q brend menyuda ko'rinmaydi. Tartib: asosiy 10 ta, qo'shimcha AI brendlar, admin qo'shganlari."""
    force = runtime.api_force()
    rows = await s.scalars(select(Product).join(Category, Category.id == Product.category_id)
                           .where(Category.is_active.is_(True), Product.brand.is_not(None)))
    live = {p.brand for p in rows
            if (p.brand in MENU_BRANDS or p.external_id in force) and (p.is_active or sold_out_visible(p))}
    base = [b for b in SERVICES if b in live]
    extras = [b for b in curation.EXTRA_BRANDS if b in live and b not in SERVICES]
    other = sorted(b for b in live if b not in SERVICES and b not in curation.EXTRA_BRANDS)
    return [*base, *extras, *other]


def in_stock(p: Product) -> bool:
    """Sotib olish mumkinmi: faol (yashirilmagan) va zaxirasi bor."""
    n = repo.stock_of(p)
    return p.is_active and (n is None or n > 0)


async def availability(s: AsyncSession) -> dict[str, bool]:
    out = {b: False for b in await shop_brands(s)}
    force = runtime.api_force()
    for p in await repo.storefront_products(s):
        if p.brand in out and in_stock(p) and (p.brand in MENU_BRANDS or p.external_id in force):
            out[p.brand] = True
    return out


def services_kb(avail: dict[str, bool], prefix: str = "svc") -> InlineKeyboardMarkup:
    btns = [service_button(brand, ok, f"{prefix}:{i}") for i, (brand, ok) in enumerate(avail.items())]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    if prefix == "svc":
        from handlers import tgstars
        extra = tgstars.entry_row()          # ⭐ Stars · 👑 Premium (STARSUNO_KEY sozlangan bo'lsa)
        if extra:
            rows.append(extra)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_services(message: Message, s: AsyncSession, lang: str) -> None:
    await message.answer(t(lang, "choose_sub"), reply_markup=services_kb(await availability(s)))


async def _edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:       # «message is not modified» yoki xabar o'chgan
        pass


def _brand_of(data: str, brands: list[str]) -> str | None:
    try:
        return brands[int(data.split(":")[1])]
    except (ValueError, IndexError):
        return None


# ─────────────────────────── Pastki menyu ───────────────────────────

@router.message(F.text.in_(LABELS["menu_subs"]))
async def m_subs(message: Message, state: FSMContext, session: AsyncSession, lang: str):
    await state.clear()
    await send_services(message, session, lang)


@router.message(F.text.in_(LABELS["menu_topup"]))
async def m_topup(message: Message, state: FSMContext, lang: str):
    from handlers.pay import _amounts_kb
    await state.clear()
    await message.answer(t(lang, "topup_title"), reply_markup=_amounts_kb())


@router.message(F.text.in_(LABELS["menu_orders"]))
async def m_orders(message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str):
    await state.clear()
    orders = await repo.user_orders(session, user, 5)
    if not orders:
        return await message.answer(t(lang, "orders_empty"))
    await message.answer(t(lang, "orders_title"))
    for o in reversed(orders):
        lines = [f"🧾 <b>#{o.id}</b> · {topup.to_tashkent(o.created_at)} · {money(o.total)}"]
        for it in o.items:
            mark = {"ok": "✅", "pending": "⏳", "failed": "❌"}.get(it.status or "", "⏳")
            lines.append(f"{mark} <b>{html.escape(it.product_name)}</b>")
            if it.delivered_content and it.status != "failed":
                lines.append(f"<code>{html.escape(it.delivered_content[:1500])}</code>")
            elif it.status == "failed":
                lines.append("<i>Pul hisobingizga qaytarilgan</i>")
        await message.answer("\n".join(lines))


def _lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz", style=BLUE),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru", style=BLUE),
    ]])


def _profile_text(user: User) -> str:
    return t(user.lang, "profile", id=user.tg_id, name=html.escape(user.full_name or "—"),
             balance=money(user.balance), language=LANGS.get(user.lang, user.lang))


@router.message(F.text.in_(LABELS["menu_profile"]))
async def m_profile(message: Message, state: FSMContext, user: User, lang: str):
    await state.clear()
    await message.answer(_profile_text(user), reply_markup=_lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(call: CallbackQuery, session: AsyncSession, user: User):
    code = call.data.split(":")[1]
    if code not in ("uz", "ru"):
        return await call.answer()
    await repo.set_lang(session, user, code)
    await call.answer(t(code, "lang_changed"))
    await _edit(call, _profile_text(user), _lang_kb())
    # pastki menyu yangi tilda qayta chiqadi
    await call.message.answer(t(code, "lang_changed"), reply_markup=main_menu(code, user.tg_id in settings.admins))


@router.message(F.text.in_(LABELS["menu_guide"]))
async def m_guide(message: Message, state: FSMContext, session: AsyncSession, lang: str):
    await state.clear()
    await message.answer(t(lang, "guide_choose"), reply_markup=services_kb(await availability(session), "gd"))


@router.message(F.text.in_(LABELS["menu_help"]))
async def m_help(message: Message, state: FSMContext, lang: str):
    await state.clear()
    sup = runtime.support_username()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        green_button(t(lang, "btn_write_support", support=sup), None, "💬", url=f"https://t.me/{sup}")]])
    await message.answer(t(lang, "help"), reply_markup=kb)


# ─────────────────────────── Obunalar: brend → tarif → xarid ───────────────────────────

@router.callback_query(F.data == "svc:back")
async def cb_back(call: CallbackQuery, session: AsyncSession, lang: str, state: FSMContext):
    await state.clear()
    await _edit(call, t(lang, "choose_sub"), services_kb(await availability(session)))
    await call.answer()


@router.callback_query(F.data.regexp(r"^svc:\d+$"))
async def cb_brand(call: CallbackQuery, session: AsyncSession, lang: str):
    brand = _brand_of(call.data, await shop_brands(session))
    products = await brand_products(session, brand) if brand else []
    if not products:
        return await call.answer(t(lang, "brand_empty"), show_alert=True)
    rows = []
    for p in products:
        label = f"{p.name} — {money(p.price)}"
        cid = brand_emoji.emoji_id(p.brand, canboso.plain_name(p))[0]            # brendning o'z premium logotipi (har tarif tugmasi oldida)
        if in_stock(p):
            btn = green_button(label, cid, "", callback_data=f"plan:{p.id}")
        else:
            extra = {"icon_custom_emoji_id": cid} if cid and premium_ok() else {}
            btn = InlineKeyboardButton(text=label, callback_data=f"plan:{p.id}", style=RED, **extra)
        rows.append([btn])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="svc:back")])
    head = t(lang, "choose_plan", brand=f"<b>{html.escape(brand)}</b>")
    if not any(in_stock(p) for p in products):
        head += "\n\n" + t(lang, "all_sold_out")
    await _edit(call, head, InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


async def _plan(call: CallbackQuery, session: AsyncSession) -> Product | None:
    try:
        p = await repo.get_product(session, int(call.data.split(":")[1]))
    except (ValueError, IndexError):
        return None
    return p if p and (p.is_active or sold_out_visible(p)) else None


def _plan_view(p: Product, user: User, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    desc = html.escape((p.description or "").strip()[:600])
    back = SERVICES.index(p.brand) if p.brand in SERVICES else None   # qo'shimcha brendlar: «Orqaga» → umumiy ro'yxat
    rows = [[green_button(t(lang, "btn_confirm_buy"), runtime.CART_EMOJI, "🛒", callback_data=f"buy:{p.id}")]]
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"svc:{back}" if back is not None else "svc:back")])
    if lang == "uz" and canboso.is_supplier_product(p) and "description" not in overrides.locked(p):
        # o'zbekcha, bir qarashda tushunarli karta; sarlavha oldida brendning premium logotipi
        text = cards.plan_text(p, user.balance, emoji_html("💎", brand_emoji.emoji_id(p.brand, canboso.plain_name(p))[0]))
    else:
        text = t(lang, "plan_card", name=html.escape(p.name), description=desc, price=money(p.price), balance=money(user.balance))
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def send_plan(message: Message, p: Product, user: User, lang: str) -> None:
    text, kb = _plan_view(p, user, lang)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.regexp(r"^plan:\d+$"))
async def cb_plan(call: CallbackQuery, session: AsyncSession, user: User, lang: str):
    p = await _plan(call, session)
    if not p:
        return await call.answer(t(lang, "stale_button"), show_alert=True)
    if not in_stock(p):
        return await call.answer(t(lang, "sub_unavailable"), show_alert=True)
    text, kb = _plan_view(p, user, lang)
    await _edit(call, text, kb)
    await call.answer()


def _qty(p: Product) -> int:
    return int(canboso.product_meta(p).get("fixed_qty") or 1) if canboso.is_supplier_product(p) else 1


@router.callback_query(F.data.regexp(r"^buy:\d+$"))
async def cb_buy(call: CallbackQuery, session: AsyncSession, user: User, lang: str, state: FSMContext):
    p = await _plan(call, session)
    if not p or not in_stock(p):
        return await call.answer(t(lang, "sub_unavailable"), show_alert=True)
    await call.answer()
    need = fulfillment.needs_input(p)
    if need == "email":
        await state.set_state(Buy.email)
        await state.update_data(pid=p.id)
        return await call.message.answer(t(lang, "ask_email"))
    if need == "accounts":
        await state.set_state(Buy.accounts)
        await state.update_data(pid=p.id)
        return await call.message.answer(t(lang, "ask_accounts", n=_qty(p)))
    await _checkout(call.message, session, user, lang, p, {})


@router.message(Buy.email, F.text)
async def msg_email(message: Message, session: AsyncSession, user: User, lang: str, state: FSMContext):
    await _collect(message, session, user, lang, state, email=message.text.strip(), accounts=None)


@router.message(Buy.accounts, F.text)
async def msg_accounts(message: Message, session: AsyncSession, user: User, lang: str, state: FSMContext):
    await _collect(message, session, user, lang, state, email=None, accounts=message.text.splitlines())


async def _collect(message, session, user, lang, state, *, email, accounts) -> None:
    pid = (await state.get_data()).get("pid")
    p = await repo.get_product(session, pid) if pid else None
    if not p or not p.is_active:
        await state.clear()
        return await message.answer(t(lang, "stale_button"))
    try:
        extra = fulfillment.clean_extras(p, _qty(p), email, accounts)
    except ValueError as ex:
        return await message.answer(t(lang, "bad_input", why=html.escape(str(ex))))
    await state.clear()
    await _checkout(message, session, user, lang, p, extra)


async def _checkout(message: Message, session: AsyncSession, user: User, lang: str, p: Product, extra: dict) -> None:
    """Balansdan yechish → ta'minotchidan xarid → natijani yuborish (webapp/api.py checkout bilan bir xil mantiq)."""
    bot = message.bot
    qty = _qty(p)
    wait = await message.answer(t(lang, "buying"))
    try:
        order = await repo.create_order(session, user, [(p, qty)])
    except repo.NotEnoughBalance as ex:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            green_button(t(lang, "btn_topup_now"), None, "💳", callback_data="pay:menu")]])
        return await _safe_edit(wait, t(lang, "not_enough_balance", need=money(ex.need), have=money(ex.have),
                                        diff=money(ex.need - ex.have)), kb)
    except repo.OutOfStock:
        return await _safe_edit(wait, t(lang, "sub_unavailable"))

    rep = await fulfillment.fulfill(session, user, order, {p.id: extra})
    extras = await _extras(session, [order])
    guides = {pid: e["guide"] for pid, e in extras.items() if e["guide"]}
    warranties = {pid: e["note"] for pid, e in extras.items() if e["note"]}
    if order.status.value == "cancelled":
        await fulfillment.alert_admins(bot, user, order, rep)
        return await _safe_edit(wait, order_success_text(lang, order, user.balance, guides, warranties, None))
    sup = runtime.support_username()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        green_button(t(lang, "btn_write_support", support=sup), None, "💬", url=f"https://t.me/{sup}")]]) if sup else None
    await _safe_edit(wait, order_success_text(lang, order, user.balance, guides, warranties, sup), kb)
    await _send_videos(bot, user, order, extras)
    await notify_admins_order(bot, user, order)
    await fulfillment.alert_admins(bot, user, order, rep)


async def _safe_edit(msg: Message, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await msg.answer(text, reply_markup=kb)


# ─────────────────────────── Qo'llanma ───────────────────────────

async def _send_guide(call: CallbackQuery, p: Product, lang: str) -> None:
    guide = guide_of(p)
    body = f"{t(lang, 'guide_title')}\n<b>{html.escape(p.name)}</b>\n\n{_steps(guide)}" if guide else t(lang, "guide_none")
    await call.message.answer(body)
    if has_video(p):
        await _deliver_video(call.bot, call.from_user.id, (p.guide_video or "").strip(), p.name)


@router.callback_query(F.data.regexp(r"^gd:\d+$"))
async def cb_guide_brand(call: CallbackQuery, session: AsyncSession, lang: str):
    brand = _brand_of(call.data, await shop_brands(session))
    products = await brand_products(session, brand) if brand else []
    if not products:
        return await call.answer(t(lang, "sub_unavailable"), show_alert=True)
    await call.answer()
    if len(products) == 1:
        return await _send_guide(call, products[0], lang)
    rows = [[InlineKeyboardButton(text=p.name, callback_data=f"gdp:{p.id}", style=BLUE)] for p in products[:12]]
    await call.message.answer(t(lang, "choose_plan", brand=f"<b>{html.escape(brand)}</b>"),
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.regexp(r"^gdp:\d+$"))
async def cb_guide_product(call: CallbackQuery, session: AsyncSession, lang: str):
    p = await repo.get_product(session, int(call.data.split(":")[1]))
    if not p:
        return await call.answer(t(lang, "stale_button"), show_alert=True)
    await call.answer()
    await _send_guide(call, p, lang)
