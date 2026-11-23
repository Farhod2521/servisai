"""Premium emoji yuborilmasa — oddiy emoji bilan qayta yuborish.

Bot egasida Telegram Premium bo'lmasa (yoki Telegram boshqa sabab bilan rad etsa), custom emojili
xabar rad etiladi. Bu middleware shu xatoni ushlab, teglarni olib
tashlaydi va xabarni qayta yuboradi — natijada bot to'xtab qolmaydi.
"""
from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest

from services import runtime
from services.emoji import button_icons, mark_blocked, strip_custom, premium_active, premiumize

log = logging.getLogger(__name__)

_MARKERS = ("custom emoji", "custom_emoji", "CUSTOM_EMOJI", "icon", "ICON")


def _reverse_map() -> dict[str, str]:
    """premium ID → oddiy emoji (ikonka olib tashlanganda tugma matniga qaytariladi)."""
    out: dict[str, str] = {}
    for ch, cid in runtime.emoji_map().items():
        out.setdefault(cid, ch)
    return out


def _strip_button_icons(markup):
    """Tugmalardagi premium ikonkani olib tashlaydi (rang — style — qoladi). O'zgarmasa None."""
    rows = getattr(markup, "inline_keyboard", None)
    if not rows:
        return None
    changed, new_rows = False, []
    for row in rows:
        new_row = []
        for btn in row:
            if (getattr(btn, "model_extra", None) or {}).get("icon_custom_emoji_id"):
                data = btn.model_dump(exclude_none=True)
                cid = data.pop("icon_custom_emoji_id", None)
                plain = _reverse_map().get(cid)
                if plain and not data.get("text", "").startswith(plain):
                    data["text"] = f"{plain} {data.get('text', '')}".strip()      # ikonka ketsa ham emoji tugmada qolsin
                btn = type(btn)(**data)
                changed = True
            new_row.append(btn)
        new_rows.append(new_row)
    return type(markup)(inline_keyboard=new_rows) if changed else None


async def custom_emoji_fallback(make_request, bot, method):
    try:
        return await make_request(bot, method)
    except TelegramBadRequest as ex:
        msg = str(ex)
        if not any(m in msg for m in _MARKERS):
            raise

        updates: dict[str, str] = {}
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            cleaned = strip_custom(value)
            if cleaned is not None and cleaned != value:
                updates[field] = cleaned

        stripped = _strip_button_icons(getattr(method, "reply_markup", None))
        if stripped is not None:
            updates["reply_markup"] = stripped
        if not updates:
            raise

        mark_blocked()   # Telegram ruxsat bermadi — har xabarda qayta urinmaymiz (10 daqiqa)
        log.warning(
            "Premium emoji yuborilmadi (%s) — oddiy emoji bilan qayta yuborilmoqda", msg
        )
        return await make_request(bot, method.model_copy(update=updates))

async def premium_emoji(make_request, bot, method):
    """Chiquvchi matnlardagi oddiy emojilarni premium bilan almashtiradi.

    Ro'yxatga custom_emoji_fallback'DAN OLDIN qo'shiladi (tashqi qatlam), shunda
    Telegram rad etsa, fallback teglarni olib tashlab qayta yuboradi.
    """
    # faqat HTML qabul qiladigan so'rovlar (parse_mode maydoni bor): xabar, tahrir, rasm/video sarlavhasi.
    # AnswerCallbackQuery (alert) kabilarda matn oddiy — teg qo'yilsa, mijozga kod ko'rinib qoladi
    if premium_active():
        markup = button_icons(getattr(method, "reply_markup", None))       # tugma matni boshidagi emoji → premium ikonka
        if markup is not None:
            method = method.model_copy(update={"reply_markup": markup})
    if premium_active() and hasattr(method, "parse_mode") and method.parse_mode is not None:
        updates = {}
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            new = premiumize(value)
            if new is not None and new != value:
                updates[field] = new
        if updates:
            method = method.model_copy(update=updates)
    return await make_request(bot, method)
