"""Bot klaviaturalari: pastki menyu, obuna (brend) tugmalari, yashil/qizil/ko'k tugmalar."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from locales.texts import t
from services import runtime
from services.emoji import premium_ok


GREEN = "success"      # Telegram tugma rangi: yashil
BLUE = "primary"       # ko'k
RED = "danger"         # qizil


# Pastki menyu tugmalarining premium ikonkalari (bot egasi bergan, @TgEmojis ID lari).
MENU_ICON_IDS = {
    "menu_subs": "5235588635885054955",       # ▦ to'rt kvadrat
    "menu_topup": "5413653337117571378",      # hamyon
    "menu_orders": "5258396243666681152",     # lupa
    "menu_profile": "5413353874817825806",    # odam
    "menu_guide": "5258328383183396223",      # ochiq kitob
    "menu_help": "5287595522993991899",       # nutq pufagi
}

# Pastki menyu: (kalit, oddiy emoji — premium ishlamasa matn oldiga qo'shiladi, rang, avvalgi versiyalardagi emojilar).
# Joylashuv: 2 ustun × 3 qator. Avvalgi emojilar eski klaviaturadagi tugma bosilganda ham tanilishi uchun saqlanadi.
MENU_ROWS: list[list[tuple[str, str, str, tuple[str, ...]]]] = [
    [("menu_subs", "🛍", GREEN, ("💎",)), ("menu_topup", "💵", BLUE, ("💳",))],
    [("menu_orders", "🔍", BLUE, ("📦",)), ("menu_profile", "👤", BLUE, ())],
    [("menu_guide", "📖", BLUE, ("📚",)), ("menu_help", "💬", BLUE, ("🎧",))],
]


def main_menu(lang: str = "uz", is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Pastki doimiy menyu: rangli tugmalar, premium ikonkalar (rad etilsa — oddiy emoji). Adminga «Admin panel» qatori."""
    rows: list[list[KeyboardButton]] = []
    for row in MENU_ROWS:
        btns = []
        for key, char, color, _ in row:
            extra: dict = {"style": color}
            if premium_ok():
                text = t(lang, key)
                extra["icon_custom_emoji_id"] = MENU_ICON_IDS[key]
            else:
                text = f"{char} {t(lang, key)}"
            btns.append(KeyboardButton(text=text, **extra))
        rows.append(btns)
    if is_admin:
        rows.append([KeyboardButton(text=t(lang, "menu_admin"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def admin_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Eski nom: adminlar uchun to'liq menyu."""
    return main_menu(lang, True)


def menu_labels() -> dict[str, set[str]]:
    """Menyu kaliti → barcha tillardagi (emojili va emojisiz) matnlar. Tugma bosilganini aniqlash uchun."""
    from locales.texts import TEXTS
    out: dict[str, set[str]] = {}
    for key, char, _, older in (b for row in MENU_ROWS for b in row):
        out[key] = set()
        for lang in TEXTS:
            plain = t(lang, key)
            out[key] |= {plain} | {f"{c} {plain}" for c in (char, *older)}
    return out


def service_button(brand: str, available: bool, data: str) -> InlineKeyboardButton:
    """Obuna tugmasi: bor bo'lsa — yashil, tugagan bo'lsa — qizil. Brend logotipi — premium emoji."""
    from services import brand_emoji
    cid, _ = brand_emoji.emoji_id(brand)
    extra: dict = {"style": GREEN if available else RED}
    text = brand
    if cid and premium_ok():
        extra["icon_custom_emoji_id"] = cid
    return InlineKeyboardButton(text=text, callback_data=data, **extra)


def subscribe_kb(channels, lang: str) -> InlineKeyboardMarkup:
    """Majburiy obuna: har bir kanal uchun tugma + «Tekshirish»."""
    kb = InlineKeyboardBuilder()
    for ch in channels:
        if ch.url:
            kb.button(text=f"📢 {ch.title}", url=ch.url)
    kb.button(text=t(lang, "btn_check_sub"), callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


def app_url(start_param: str | None = None) -> str:
    """Mini App o'chirilgan: do'kon butunlay botning o'zida. Bo'sh qaytadi (tugmalar botga olib boradi)."""
    return ""




def green_button(text: str, icon_id: str | None = None, fallback: str = "", **kw) -> InlineKeyboardButton:
    """Yashil fonli tugma. `icon_id` — matn oldidagi premium emoji; premium bo'lmasa `fallback` oddiy emoji matnga qo'shiladi."""
    extra = {"style": GREEN}
    if icon_id and premium_ok():
        extra["icon_custom_emoji_id"] = icon_id
    elif fallback:
        text = f"{fallback} {text}"
    return InlineKeyboardButton(text=text, **kw, **extra)


def open_app_kb(lang: str, product_id: int | None = None) -> InlineKeyboardMarkup | None:
    """Mini App'ni ochuvchi yashil tugma (🛍 premium ikonka bilan). initData faqat inline tugma orqali keladi."""
    url = app_url(str(product_id) if product_id else None)
    if not url:
        return None
    btn = green_button(t(lang, "btn_open_app"), runtime.BAG_EMOJI, "🛍", web_app=WebAppInfo(url=url))
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


def buy_kb(lang: str, product_id: int | None = None, bot_username: str | None = None) -> InlineKeyboardMarkup | None:
    """Yashil «Sotib olish» tugmasi (🛒 premium ikonka): Mini App'da shu mahsulot sahifasini ochadi."""
    url = app_url(str(product_id) if product_id else None)
    text = t(lang, "btn_buy_now")
    if url:
        btn = green_button(text, runtime.CART_EMOJI, "🛒", web_app=WebAppInfo(url=url))
    elif bot_username:
        btn = green_button(text, runtime.CART_EMOJI, "🛒", url=f"https://t.me/{bot_username}?start=p{product_id or ''}")
    else:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


def channel_kb(bot_username: str, product_id: int | None = None, lang: str = "uz") -> InlineKeyboardMarkup:
    """Kanal xabari tagidagi yashil «Sotib olish» tugmasi (🛒 premium ikonka, botdagi bilan bir xil).
    Kanalda web_app tugmasi ishlamaydi — tugma botdagi mahsulotga olib boradi."""
    url = f"https://t.me/{bot_username}?start=p{product_id or ''}"
    return InlineKeyboardMarkup(inline_keyboard=[[green_button(t(lang, "btn_buy_now"), runtime.CART_EMOJI, "🛒", url=url)]])


def announce_kb(bot_username: str, product_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(lang, "btn_open_bot"),
        url=f"https://t.me/{bot_username}?start=p{product_id}",
    )
    return kb.as_markup()
