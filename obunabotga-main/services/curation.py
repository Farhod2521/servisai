"""Do'konga ta'minotchi (API) mahsulotlaridan qaysilari qo'yilishi.

Loyiha egasining qarori (2026-11-07): menyudagi brendlar — quyidagi ro'yxat, ularning HAMMA mahsulotlari do'konga chiqadi
(kafolat muddati, API nominali bo'yicha cheklov yo'q). Faqat taqiqlangan turdagilar (soxta obunachi, SMS-raqam ijarasi va h.k.,
services/canboso.py: is_blocked) chiqmaydi. Ro'yxatda yo'q brendni admin «API'dan qo'shish» orqali qo'lda qo'sha oladi.
"""
from __future__ import annotations

import re

# Do'kon menyusidagi asosiy brendlar (tartib shu). Admin qo'shgan boshqa brendlar ularning ostiga qo'shiladi.
BASE_BRANDS = [
    "ChatGPT", "Codex", "Claude", "Gemini", "Grok", "Perplexity", "DeepSeek", "Qwen", "Cursor", "n8n",
    "Kling", "Higgsfield", "Runway", "Seedance", "Google VEO", "OpenArt", "Freepik", "ElevenLabs", "Suno",
    "CapCut", "Canva", "Adobe", "Figma", "Gamma", "Notion", "Microsoft 365", "Windows", "Zoom", "Duolingo",
    "Kaspersky", "Netflix", "Autodesk",
]

# Qo'shimcha AI obunalar: menyuda faqat shu brendning qoidaga to'g'ri keladigan (KAFOLATI yozilgan va kamida 24 soat)
# mahsuloti bo'lsa chiqadi; bo'lmasa menyuda ko'rinmaydi (tugmalar bo'sh turmasin).
EXTRA_BRANDS: list[str] = []       # hammasi asosiy ro'yxatda

API_AMOUNTS = {100, 500}            # API paketlar (hamma brendda): faqat shu nominallar ($)
CODEX_AMOUNTS = API_AMOUNTS         # eski nom
SUB_MIN_WARRANTY_DAYS = 20          # OBUNALAR (hamma brend): kamida shuncha kunlik kafolat
CHATGPT_MIN_WARRANTY_DAYS = SUB_MIN_WARRANTY_DAYS     # eski nom
API_MIN_WARRANTY_DAYS = 1           # API: kamida 24 soat kafolat
CODEX_MIN_WARRANTY_DAYS = API_MIN_WARRANTY_DAYS
MIN_WARRANTY_DAYS_ALL = 1           # kafolati yozilgan bo'lsa, 24 soatdan kam bo'lmasin

_API = re.compile(r"\bcodex\b|\bapi\b", re.I)
_AMOUNT = re.compile(r"\$\s*(\d{1,5})(?![\d.])|(?<![\d.])(\d{1,5})\s*\$|(?<![\d.])(\d{1,5})\s*(?:usd|dollars?)\b", re.I)
_DUR = re.compile(r"(\d+(?:[.,]\d+)?)\s*(soat|kun|hafta|oy|yil)", re.I)
_MULT = {"soat": 1 / 24, "kun": 1, "hafta": 7, "oy": 30, "yil": 365}


def is_codex_api(name_en: str) -> bool:
    return bool(_API.search(name_en or ""))


_CODE = re.compile(r"\bredeem\b|\bcdk\b|activation (?:link|code|key)|key activation|\bcode\b", re.I)


def is_code(name_en: str) -> bool:
    """Rasmiy kod / aktivatsiya havolasi mahsuloti (Redeem, CDK, Activation link)."""
    return bool(_CODE.search(name_en or ""))


def is_api(brand: str, name_en: str) -> bool:
    """API paketmi: nomida «API»; ChatGPT uchun «Codex» ham. Boshqa brendlarda «codex» so'zi API degani emas."""
    return bool(re.search(r"\bapi\b", name_en or "", re.I)) or (brand == "ChatGPT" and is_codex_api(name_en))


def api_amount(name_en: str) -> int | None:
    """Nomdagi dollar nominali: «$100», «100$», «100 USD» → 100."""
    m = _AMOUNT.search(name_en or "")
    return int(next(g for g in m.groups() if g)) if m else None


def warranty_days(warranty: str) -> float | None:
    """Kafolat matnidan kunlar: «30 kun kafolat» → 30, «24 soat kafolat» → 1, «kafolatsiz» → 0, «to'liq kafolat» → cheksiz, noma'lum → None."""
    if not warranty:
        return None
    low = warranty.lower()
    if "kafolatsiz" in low:
        return 0.0
    m = _DUR.search(low)
    if m:
        return float(m.group(1).replace(",", ".")) * _MULT[m.group(2)]
    if "to'liq" in low:
        return float("inf")
    return None


def _fmt_days(days: float | None) -> str:
    if days is None:
        return "ko'rsatilmagan"
    if days == 0:
        return "yo'q"
    if days == float("inf"):
        return "to'liq"
    return f"{days:g} kun" if days >= 1 else f"{days * 24:g} soat"


def reject_reason(brand: str, name_en: str, warranty: str, duration_days: float | None = None) -> str | None:
    """Mahsulot do'konga chiqmasligi sababi yoki None. Egasi qarori: menyudagi brendlarning hamma mahsuloti chiqadi —
    kafolat va nominal bo'yicha cheklov yo'q (taqiqlangan turlar canboso.is_blocked da alohida to'xtatiladi)."""
    return None


# Oxirgi sinxronlashdagi API ro'yxati (admin «API'dan qo'shish» ekrani uchun). Xotirada: bot qayta yonganda sinxronlash to'ldiradi.
# {external_id: {"name", "raw", "usd", "price", "brand", "warranty", "available", "shown", "reason"}}
CATALOG: dict[str, dict] = {}


def hidden_items() -> list[dict]:
    """Do'konda ko'rinmaydigan API mahsulotlari (admin qo'shishi mumkin): brend, nom bo'yicha tartiblangan."""
    rows = [dict(v, id=k) for k, v in CATALOG.items() if not v["shown"]]
    return sorted(rows, key=lambda r: (r["brand"] or "~", r["name"], r["usd"]))
