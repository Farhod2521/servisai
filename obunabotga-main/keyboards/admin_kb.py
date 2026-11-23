"""Admin klaviaturalari."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Category, Product
from services import overrides


def admin_main(c: dict | None = None) -> InlineKeyboardMarkup:
    """Bosh sahifa. Birinchi qatorda eng kerakli 3 amal: to'lovlarni tasdiqlash, ID bilan hisob to'ldirish, majburiy obuna.
    `c` — sonlar (bajarilmagan buyurtma, kutilayotgan to'lov)."""
    from keyboards.user_kb import BLUE, GREEN, RED
    c = c or {}
    pending, topups = c.get("pending", 0), c.get("topups", 0)

    def btn(text: str, data: str, style: str = BLUE) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=text, callback_data=data, style=style)

    confirm = btn(f"✅ To'lovlarni tasdiqlash ({topups})" if topups else "✅ To'lovlarni tasdiqlash", "pay:adm_list", GREEN if topups else BLUE)
    orders = btn(f"🧾 Buyurtmalar ({pending})" if pending else "🧾 Buyurtmalar", "a:orders", RED if pending else BLUE)
    return InlineKeyboardMarkup(inline_keyboard=[
        [confirm],
        [btn("💰 ID bilan hisob to'ldirish", "a:fastbal", GREEN), btn("📢 Majburiy obuna", "a:fsub")],
        [orders, btn("👥 Mijozlar", "a:users")],
        [btn("🛍 Obunalar", "a:s:shop"), btn("💰 Narx va foyda", "a:s:price")],
        [btn("📣 Xabarlar", "a:s:msg"), btn("📊 Hisobotlar", "a:s:report")],
        [btn("⚙️ Sozlamalar", "a:s:settings"), btn("💳 To'lov sozlamalari", "a:s:pay")],
        [btn("⭐ Stars / Premium", "a:s:tg"), btn("📖 Qo'llanma", "a:help:0")],
        [btn("🔄 Katalogni yangilash", "a:sync", GREEN), btn("🔃 Yangilash", "a:home")],
    ])


def section_kb(key: str) -> InlineKeyboardMarkup:
    """Bo'lim ichidagi tugmalar (2 tadan) va doim ko'rinadigan «Bosh sahifa»."""
    from keyboards.user_kb import BLUE, GREEN
    from services.panel import SECTIONS
    btns = [InlineKeyboardButton(text=t, callback_data=d, style=BLUE) for t, d in SECTIONS[key][2]]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="a:home", style=GREEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_cats(cats: list[Category]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in cats:
        flag = "✅" if c.is_active else "🚫"
        kb.button(text=f"{flag} {c.emoji} {c.name_uz}", callback_data=f"a:cat:{c.id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:home"))
    return kb.as_markup()


def admin_cat_actions(cat: Category) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Nomini o'zgartirish", callback_data=f"a:cat_rename:{cat.id}")
    kb.button(text="😀 Emoji o'zgartirish", callback_data=f"a:cat_emoji:{cat.id}")
    kb.button(
        text="🚫 O'chirib qo'yish" if cat.is_active else "✅ Yoqish",
        callback_data=f"a:cat_toggle:{cat.id}",
    )
    kb.button(text="🗑 Butunlay o'chirish", callback_data=f"a:cat_del:{cat.id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:cats"))
    return kb.as_markup()


def admin_prod_list(products: list[Product], cat_id: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in products:
        flag = "✅" if p.is_active else "🚫"
        kb.button(text=f"{flag} {p.emoji} {p.name}", callback_data=f"a:prod:{p.id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="a:prods" if cat_id else "a:home"))
    return kb.as_markup()


def admin_prod_actions(p: Product) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Nom", callback_data=f"a:p_name:{p.id}")
    kb.button(text="💵 Narx", callback_data=f"a:p_price:{p.id}")
    kb.button(text="📝 Tavsif", callback_data=f"a:p_desc:{p.id}")
    kb.button(text="📖 Qo'llanma ✅" if p.guide else "📖 Qo'llanma", callback_data=f"a:p_guide:{p.id}")
    kb.button(text="🎬 Video ✅" if p.guide_video else "🎬 Video qo'llanma", callback_data=f"a:p_video:{p.id}")
    kb.button(text="🛡 Kafolat matni ✅" if p.warranty_note else "🛡 Kafolat matni", callback_data=f"a:p_warr:{p.id}")
    kb.button(text="😀 Emoji", callback_data=f"a:p_emoji:{p.id}")
    kb.button(text="📥 Zaxira qo'shish", callback_data=f"a:p_stock:{p.id}")
    kb.button(text="📢 E'lon qilish", callback_data=f"a:p_announce:{p.id}")
    kb.button(
        text="🚫 O'chirib qo'yish" if p.is_active else "✅ Yoqish",
        callback_data=f"a:p_toggle:{p.id}",
    )
    kb.button(text="🗑 Butunlay o'chirish", callback_data=f"a:p_del:{p.id}")
    if overrides.locked(p):
        kb.button(text="↩️ Avtomatik rejimga qaytarish", callback_data=f"a:p_auto:{p.id}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"a:cat_prods:{p.category_id}"))
    return kb.as_markup()


def confirm_kb(action: str, obj_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, o'chirilsin", callback_data=f"a:confirm:{action}:{obj_id}")
    kb.button(text="❌ Yo'q", callback_data="a:home")
    kb.adjust(1)
    return kb.as_markup()
