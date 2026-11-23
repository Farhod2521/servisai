"""Ish vaqtida admin paneldan o'zgartiriladigan sozlamalar.

Qiymatlar bazadagi `settings` jadvalida saqlanadi (Render qayta ishga tushganda
yo'qolmaydi) va xotirada keshlanadi. Bazada qiymat bo'lmasa — .env dagi qiymat
ishlatiladi.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from config import settings
from database.db import SessionMaker
from database.models import Setting

_cache: dict[str, str] = {}


async def load() -> None:
    async with SessionMaker() as s:
        rows = await s.scalars(select(Setting))
        _cache.clear()
        _cache.update({r.key: r.value for r in rows})


async def set_value(key: str, value: str | None) -> None:
    """value=None — bazadan o'chiradi (keyin .env dagi qiymatga qaytadi)."""
    async with SessionMaker() as s:
        row = await s.get(Setting, key)
        if value is None:
            if row:
                await s.delete(row)
            _cache.pop(key, None)
        else:
            if row:
                row.value = value
            else:
                s.add(Setting(key=key, value=value))
            _cache[key] = value
        await s.commit()


def markup_percent() -> float:
    try:
        return float(_cache["markup"])
    except (KeyError, ValueError):
        return settings.catalog_markup_percent


def usd_rate_override() -> float:
    """0 — kurs avtomatik (Markaziy bank)."""
    try:
        return float(_cache["usd_rate"])
    except (KeyError, ValueError):
        return settings.usd_to_uzs


def usd_last() -> float:
    """Oxirgi muvaffaqiyatli olingan kurs (manbalar ochilmay qolsa ishlatiladi). 0 — hali yo'q."""
    try:
        return float(_cache["usd_last"])
    except (KeyError, ValueError):
        return 0.0


# Bot matnlarida avtomatik premium bo'ladigan tayyor emojilar (oddiy emoji → custom_emoji_id).
# Admin panelda («😀 Premium emoji») yuborgan emojilari shularning ustidan yoziladi.
DEFAULT_EMOJI: dict[str, str] = {
    # Eskilari
    "➕": "5393194986252542669",     # ko'k plyus — «Qo'shildi»
    "💵": "5413653337117571378",     # PUL: hamyon (narx, hisob, balans — hammasida shu)
    "🛍": "5235588635885054955",     # «Obunalar» bo'limining logotipi (to'rt kvadrat)
    "🛒": "5312361253610475399",     # savatcha — «Sotib olish»
    "👋": "5472354553527541051",     # qo'l — salomlashuv
    "✋": "5472354553527541051",
    # Bot egasi bergan (@TgEmojis): holat belgilari va asosiy ikonkalar
    "✅": "5413395179518310071",     # belgi (aylana ichida)
    "❌": "5260342697075416641",     # xoch (aylana ichida)
    "⏳": "5339357992103983304",     # qum soati
    "🚫": "5413775597656619974",     # taqiq
    "⚠": "5440785268296671580",     # ogohlantirish
    "💳": "5413653337117571378",     # PUL: hamyon
    "💰": "5413653337117571378",     # PUL: hamyon
    "⏱": "5416012459574048237", "🕒": "5416012459574048237",     # MUDDAT / vaqt: soat
    "🧾": "5444856076954520455",     # chek
    "📦": "5258396243666681152",     # lupa — buyurtmalar
    "🆔": "5334890573281114250",     # ID
    "🌐": "6339280615459789282",     # globus — til
    "💎": "5298988357538328017",     # olmos
    "⚡": "5219943216781995020",     # chaqmoq — tezlik
    "🛡": "5895483165182529286",     # qalqon — kafolat
    "👇": "5438525681707278534",     # pastga ko'rsatkich
    # Menyu ikonkalari bilan bir xil uslubda
    "👤": "5413353874817825806", "🙍": "5413353874817825806",     # odam — profil
    "📖": "5258328383183396223",     # ochiq kitob — qo'llanma
    "💬": "5287595522993991899",     # nutq pufagi — yordam
    # Ikkinchi to'plam (@TgEmojis)
    "📚": "5373098009640836781",     # kitoblar
    "🎧": "5307571098060078194",     # quloqchin
    "🎉": "5461136335173598840",     # konfeti
    "😔": "5240291728153397366",     # xafa ayiqcha
    "➖": "5382261056078881010",     # ko'k chiziq
    "📋": "5303365758141627496",     # yozuv daftarcha ushlagan ko'z
    "🔒": "5393302369024882368",     # qulf
    "🔕": "5470097960530375585",     # o'chirilgan qo'ng'iroq
    "🔑": "5454386656628991407",     # kalit
    "⬅": "5258236805890710909",     # orqaga
    "➡": "5260450573768990626",     # oldinga
    "⭐": "5438553238217450600",     # oltin yulduz — Telegram Stars
    "👑": "5438186851737299383",     # binafsha yulduz — Telegram Premium
    # Uchinchi to'plam (@TgEmojis)
    "✨": "5222108309795908493",     # yulduzchalar
    "📭": "5352896944496728039",     # ochiq pochta qutisi — buyurtma yo'q
    "🏠": "5465226866321268133",     # uy — bosh menyu / bosh sahifa
    "⚪": "5972210698636234017", "🔹": "5972210698636234017",     # oq doira
    "📧": "5960803037864791851", "✉": "5960803037864791851",     # Gmail — email
    "🎟": "5377599075237502153",     # chiptalar — kredit
    "🔴": "6053134711490878159",     # qizil shar — tugagan
    "❓": "5382187118216879236", "❔": "5382187118216879236",     # ko'k savol belgisi
    "✏": "6053375122285270945", "✍": "6053375122285270945",     # qalam
    "📊": "5438540301775952753", "📈": "5438540301775952753",     # diagramma
    "📄": "5258477770735885832", "📃": "5258477770735885832",     # hujjat nusxasi
    "🤔": "5832166379347776054",     # o'ylayotgan Pepe
    "🔔": "5413582169509475958",     # qo'ng'iroq
    "🆕": "5265244349976832702",     # NEW
    "🔄": "5413759431399718342", "🔃": "5413759431399718342", "♻": "5413759431399718342",     # yangilash
}
LAST_UPDATE_EMOJI = "5260687119092817530"     # «Oxirgi yangilanish» (katalog holati) belgisi
CART_EMOJI = DEFAULT_EMOJI["🛒"]
BAG_EMOJI = DEFAULT_EMOJI["🛍"]


def user_emoji_map() -> dict[str, str]:
    """Admin paneldan saqlangan emojilar."""
    try:
        data = json.loads(_cache.get("emoji_map", "{}"))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def emoji_map() -> dict[str, str]:
    """Oddiy emoji → premium (custom) emoji ID: tayyor ro'yxat + admin saqlaganlari."""
    return {**DEFAULT_EMOJI, **user_emoji_map()}


# ─── Avtomatik to'lov: karta ma'lumotlari (admin paneldan o'zgaradi) va avto-tasdiq ───

def card_number() -> str:
    return (_cache.get("pay_card") or settings.payment_card_number or "").strip()


def card_owner() -> str:
    return (_cache.get("pay_owner") or settings.payment_card_owner or "").strip()


def tg_session() -> str:
    """Telethon StringSession: botda /sessiya orqali olingan (bazada) yoki Render'dagi TG_SESSION."""
    return (_cache.get("tg_session") or "").strip() or settings.tg_session


def autoconfirm_enabled() -> bool:
    return _cache.get("pay_auto", "1") != "0"


DEFAULT_SUPPORT = "fen1xmedia"


def support_username() -> str:
    """Yordam markazi: admin paneldan o'zgartirilgan, bo'lmasa .env dagi (@siz, kichik harfsiz o'zgartirilmaydi)."""
    return (_cache.get("support") or settings.support_username or DEFAULT_SUPPORT).strip().lstrip("@")


def pricing_mode() -> str:
    """«smart» (SUKUT: aqlli narx — Servis AI botning o'z narx siyosati, uz shop botdagi jadvaldan farqli)
    | «flat» (bir xil foiz) | «tiers» (tannarxga qarab qat'iy ustama jadvali)."""
    m = _cache.get("pricing", "smart")
    return m if m in ("flat", "tiers") else "smart"


async def apply_migrations() -> None:
    """Bir martalik sozlama o'zgarishlari (bot yonganda). Bajarilgani bazada belgilanadi — qayta ishlamaydi."""
    if _cache.get("mig_pricing_smart_v2") != "1":
        # Servis AI bot uz shop botdan farqli narxlansin: zaxiradan kelgan «ustama jadvali» o'rniga o'zining aqlli narxi
        await set_value("pricing", "smart")
        await set_value("mig_pricing_smart_v2", "1")


def brand_markups() -> dict[str, float]:
    """Brend bo'yicha foyda foizi: {"CapCut": 40.0, "Claude": 25.0}. Foiz qo'yilgan brend narxi = tannarx + shu foiz."""
    try:
        data = json.loads(_cache.get("brand_markup", "{}"))
        return {str(k): float(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


async def set_brand_markup(brand: str, percent: float | None) -> None:
    """Brendga foiz qo'yadi; None — olib tashlaydi (umumiy narx qoidasiga qaytadi)."""
    data = brand_markups()
    if percent is None:
        data.pop(brand, None)
    else:
        data[brand] = float(percent)
    await set_value("brand_markup", json.dumps(data, ensure_ascii=False) if data else None)


def pricing_smart() -> bool:
    """Aqlli narx rejimi (sukut). Admin «Foyda foizi» ga qo'lda foiz qo'ysa — «flat», ustama jadvali yoqilsa — «tiers»."""
    return pricing_mode() == "smart"


# Tannarx (USD) bo'yicha QAT'IY ustama (so'm): (shu qiymatgacha, ustama). Oxirgisi — undan yuqorisi.
DEFAULT_TIERS: list[tuple[float | None, int]] = [(10, 35_000), (30, 50_000), (60, 80_000), (100, 130_000), (None, 250_000)]


def markup_tiers() -> list[tuple[float | None, int]]:
    try:
        raw = json.loads(_cache.get("markup_tiers", ""))
        tiers = [(None if t[0] is None else float(t[0]), int(t[1])) for t in raw]
        return tiers if tiers and tiers[-1][0] is None else DEFAULT_TIERS
    except (ValueError, TypeError, IndexError, KeyError):
        return DEFAULT_TIERS


def tier_markup(usd: float) -> int:
    """Mahsulot tannarxi (USD) ga mos qat'iy ustama (so'm)."""
    for upto, markup in markup_tiers():
        if upto is None or usd <= upto:
            return markup
    return markup_tiers()[-1][1]


def parse_tiers(text: str) -> list[tuple[float | None, int]] | None:
    """Admin matni → jadval. Har qatorda: «10 35000» (10$ gacha 35 000 so'm); oxirgi qator «+ 250000» (undan yuqori). Xato bo'lsa None."""
    rows: list[tuple[float | None, int]] = []
    for line in (text or "").replace(",", " ").splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 2:
            return None
        try:
            upto = None if parts[0] in ("+", "inf", "∞") else float(parts[0])
            markup = int(float(parts[1]))
        except ValueError:
            return None
        if markup <= 0 or (upto is not None and upto <= 0):
            return None
        rows.append((upto, markup))
    if len(rows) < 2 or rows[-1][0] is not None or any(r[0] is None for r in rows[:-1]):
        return None
    bounds = [r[0] for r in rows[:-1]]
    return rows if bounds == sorted(bounds) and len(set(bounds)) == len(bounds) else None


def welcome_html() -> str:
    """Admin yozgan /start salomlashuvi (HTML, premium emoji bilan). Bo'sh — standart matn."""
    return _cache.get("welcome_html", "").strip()


def price_alert_enabled() -> bool:
    """Narxi o'zgargan obunalar haqida adminga xabar yuborish."""
    return _cache.get("price_alert", "1") != "0"


def brand_emoji() -> dict[str, dict]:
    """Brend → {"id": custom_emoji_id, "char": oddiy emoji}. Xabarnomada mahsulot belgisi sifatida chiqadi."""
    try:
        data = json.loads(_cache.get("brand_emoji", "{}"))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


# ─── Xabarnoma (yangi mahsulot / zaxira to'ldirilishi) ───
NOTIFY_MIN_DEFAULT = 5


def notify_enabled() -> bool:
    """Yangi mahsulot / zaxira haqida mijozlarga xabar. Sukut: O'CHIQ (mahsulotlar jimgina qo'shiladi); admin paneldan yoqiladi."""
    return _cache.get("notify_on", "0") == "1"


def notify_min() -> int:
    """Zaxira shuncha dona oshganda xabar beriladi (0 dan N ga qaytganda va yangi mahsulotda — har doim)."""
    try:
        return max(1, int(_cache["notify_min"]))
    except (KeyError, ValueError):
        return NOTIFY_MIN_DEFAULT


# ─── Majburiy obuna kanallari (admin panelda boshqariladi; bo'lmasa .env dagi FORCE_SUB_CHANNEL) ───

def force_sub_channels() -> list[str]:
    raw = _cache.get("force_sub")
    if raw is None:
        return settings.force_sub_channels
    try:
        data = json.loads(raw)
    except ValueError:
        return settings.force_sub_channels
    return [x for x in data if isinstance(x, str) and x] if isinstance(data, list) else settings.force_sub_channels


async def set_force_sub(channels: list[str]) -> None:
    await set_value("force_sub", json.dumps(channels, ensure_ascii=False))


# ─── Admin API ro'yxatidan qo'lda qo'shgan mahsulotlar (qoidalarga qaramasdan do'konda ko'rinadi) ───

def api_force() -> set[str]:
    try:
        data = json.loads(_cache.get("api_force", "[]"))
    except ValueError:
        return set()
    return {x for x in data if isinstance(x, str)} if isinstance(data, list) else set()


async def set_api_force(ids: set[str]) -> None:
    await set_value("api_force", json.dumps(sorted(ids)))
