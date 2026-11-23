"""Premium (custom) emoji yordamchisi.

Telegram qoidasi: bot custom emojini bot EGASIDA (BotFather'da botni yaratgan akkaunt)
Telegram Premium bo'lsa yubora oladi — Fragment'dagi qo'shimcha username shart emas.
Premium emoji admin paneldagi xarita to'lishi bilan avtomatik yoqiladi (.env shart emas).
Telegram baribir rad etsa, middlewares/emoji_fallback.py xatolikni ushlab,
oddiy emoji bilan qayta yuboradi.
"""
from __future__ import annotations

import re
import time

from services import runtime

_TAG = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', re.DOTALL)


def e(fallback: str, custom_emoji_id: str | None = None) -> str:
    """HTML parse_mode uchun emoji qaytaradi."""
    if custom_emoji_id and time.monotonic() > _blocked_until:
        return f'<tg-emoji emoji-id="{custom_emoji_id}">{fallback}</tg-emoji>'
    return fallback


def strip_custom(text: str | None) -> str | None:
    """<tg-emoji> teglarini olib tashlab, ichidagi oddiy emojini qoldiradi."""
    if not text:
        return text
    return _TAG.sub(r"\1", text)


def extract_custom_id(entities) -> str | None:
    """Admin yuborgan xabardan custom_emoji_id ni ajratib oladi."""
    for ent in entities or []:
        if ent.type == "custom_emoji" and ent.custom_emoji_id:
            return ent.custom_emoji_id
    return None

# ─────────────────────────── Avtomatik premium emoji ───────────────────────────
#
# Admin paneldan «premium emoji xaritasi» yig'iladi: oddiy emoji → custom_emoji_id.
# Bot yuboradigan har bir matndagi shu oddiy emojilar premium bilan almashtiriladi.
# Tugma matnlarida (inline/reply) Telegram custom emojiga ruxsat bermaydi — ular oddiy qoladi.

_VS16 = "\ufe0f"
_SPLIT = re.compile(r'(<tg-emoji emoji-id="\d+">.*?</tg-emoji>|<[^>]+>)', re.DOTALL)
_blocked_until = 0.0     # Telegram rad etsa, shu vaqtgacha premium yuborilmaydi


def mark_blocked(seconds: int = 600) -> None:
    global _blocked_until
    _blocked_until = time.monotonic() + seconds


def premium_ok() -> bool:
    """Telegram premium emojini hozir rad etmayaptimi (tugma ikonkalari uchun)."""
    return time.monotonic() > _blocked_until


def premium_active() -> bool:
    return time.monotonic() > _blocked_until and bool(runtime.emoji_map())


def premiumize(text: str | None, mapping: dict[str, str] | None = None) -> str | None:
    """HTML matndagi xaritadagi emojilarni <tg-emoji> bilan almashtiradi (teglar ichiga tegmaydi)."""
    mapping = mapping if mapping is not None else runtime.emoji_map()
    if not text or not mapping:
        return text
    norm = {k.replace(_VS16, ""): v for k, v in mapping.items() if k.replace(_VS16, "")}
    if not norm:
        return text
    rx = re.compile("(?:" + "|".join(re.escape(k) for k in sorted(norm, key=len, reverse=True)) + f"){_VS16}?")
    parts = _SPLIT.split(text)
    for i in range(0, len(parts), 2):          # juft indekslar — oddiy matn, toq — teglar
        parts[i] = rx.sub(
            lambda m: f'<tg-emoji emoji-id="{norm[m.group(0).replace(_VS16, "")]}">{m.group(0)}</tg-emoji>',
            parts[i],
        )
    return "".join(parts)


def button_icons(markup, mapping: dict[str, str] | None = None):
    """Inline tugmalar: matn boshidagi emoji (masalan «⭐ Stars») premium ikonkaga aylanadi (matndan olinadi,
    `icon_custom_emoji_id` qo'yiladi; rang — style — saqlanadi). Allaqachon ikonkasi bor tugmalarga tegmaydi. O'zgarmasa None."""
    rows = getattr(markup, "inline_keyboard", None)
    mapping = mapping if mapping is not None else runtime.emoji_map()
    if not rows or not mapping:
        return None
    norm = {k.replace(_VS16, ""): v for k, v in mapping.items() if k.replace(_VS16, "")}
    keys = sorted(norm, key=len, reverse=True)
    changed, new_rows = False, []
    for row in rows:
        new_row = []
        for btn in row:
            text = getattr(btn, "text", "") or ""
            if not (getattr(btn, "model_extra", None) or {}).get("icon_custom_emoji_id"):
                plain = text.replace(_VS16, "")
                for k in keys:
                    if plain.startswith(k):
                        rest = plain[len(k):].strip()
                        if rest:                    # faqat emojidan iborat tugmaga tegmaymiz
                            data = btn.model_dump(exclude_none=True)
                            data["text"], data["icon_custom_emoji_id"] = rest, norm[k]
                            btn, changed = type(btn)(**data), True
                        break
            new_row.append(btn)
        new_rows.append(new_row)
    return type(markup)(inline_keyboard=new_rows) if changed else None


_PAIR = re.compile(r"(?P<ch>[^\w\s=:\-–—,;|]{1,12}?)\s*[=:\-–—]?\s*\[?(?P<id>\d{15,20})\]?")


def parse_emoji_pairs(text: str | None) -> dict[str, str]:
    """«📦 5312361253610475399» (emoji + ID, har qatorda bittadan yoki vergul bilan) → {"📦": "5312…"}."""
    out: dict[str, str] = {}
    for m in _PAIR.finditer(text or ""):
        ch = m.group("ch").replace(_VS16, "").strip()
        if ch and not ch.isascii():
            out[ch] = m.group("id")
    return out


# ─── Emoji paketidan avtomatik olish ───
# Bot matnlari va menyusida ishlatiladigan emojilar: paketda shular bo'lsa ID lari o'zi olinadi.
WANTED = (
    # Mijoz har kuni ko'radigan asosiy emojilar
    "💎", "✅", "❌", "⏳", "⚠", "🚫", "💳", "💰", "💵", "🧾", "📦", "👤", "👋", "👇", "⚡", "🛡", "🎉", "😔",
    "⬅", "➡", "➖", "🔻", "📋", "🔒", "🔔", "🔕", "🆔", "🙍", "🌐", "🔑", "📧", "📖", "📚", "🎧", "💬", "🛍", "🛒", "➕",
    # Kamroq uchraydiganlari (to'lov, xabarnoma, kanal e'lonlari)
    "❓", "ℹ", "🔎", "🔍", "🔄", "✏", "🕒", "⌛", "⏰", "🏦", "📄", "📊", "📈", "🆕", "📢", "♾", "🔺",
)
_PACK = re.compile(r"(?:https?://)?(?:t|telegram)\.me/add(?:emoji|stickers)/([A-Za-z0-9_]{3,64})", re.I)


def pack_names(text: str | None) -> list[str]:
    """Matndagi emoji-paket havolalaridan (t.me/addemoji/Nom) paket nomlari. Takrorlanmaydi."""
    return list(dict.fromkeys(_PACK.findall(text or "")))


def pick_from_pack(stickers) -> dict[str, str]:
    """Paketdagi stikerlardan botga kerak emojilar: {oddiy emoji: custom_emoji_id}. Har emoji uchun birinchisi."""
    wanted = {w.replace(_VS16, "") for w in WANTED}
    out: dict[str, str] = {}
    for st in stickers or []:
        cid = getattr(st, "custom_emoji_id", None)
        for ch in (getattr(st, "emoji", None) or "").replace(_VS16, ""):   # stikerga bir nechta emoji biriktirilgan bo'lishi mumkin
            if cid and ch in wanted and ch not in out:
                out[ch] = cid
    return out
