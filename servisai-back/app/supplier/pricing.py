"""Aqlli narx siyosati: ta'minotchi narxidan (asl narx) kelib chiqib, sotuv narxini «insofli» va raqobatbardosh qo'yadi.

Qoidalar (USD da, keyin so'mga o'tkaziladi):
  • Foyda ulushi asl narxga qarab kamayadi: arzon mahsulotda ko'proq (1.35$ → ~3$, 1.11$ → 2.5$), qimmatda kamroq (11.64$ → 16$).
  • Kafolati kam / yo'q obunalarda foyda kamaytiriladi (narx pastroq).
  • Rasmiy narxi ma'lum obunalarda (ChatGPT Plus 20$, Claude Pro 20$ …) sotuv narxi rasmiy narxdan 3–5$ (≈15%) arzon bo'lib qoladi.
  • Narx chiroyli yaxlitlanadi: 10$ gacha 0.5$ qadam, undan yuqorida 1$.
Admin «💹 Foyda foizi» da qo'lda foiz qo'ysa — eski (bir xil foiz) rejim; «🧠 Aqlli narx» tugmasi bilan qaytariladi.
Qo'lda qo'yilgan (🔒) narxlarga tegilmaydi.
"""
from __future__ import annotations

import math
import re

# (asl narx USD, foyda ko'paytiruvchisi) — oraliqlar logarifmik interpolyatsiya qilinadi
_TIERS = [(1, 2.40), (2, 2.05), (3, 1.90), (5, 1.70), (8, 1.50), (11.64, 1.375), (20, 1.30), (50, 1.20), (100, 1.15), (300, 1.10)]
MIN_MARGIN = 1.08            # hech qachon asl narxdan 8% dan kam foyda bilan sotmaymiz
UNDERCUT = 0.15              # rasmiy narxdan ~15% arzon (20$ → 17$ dan oshmaydi)

# Rasmiy oylik narx (USD): (brend, nom regex yoki None, oyiga)
OFFICIAL: list[tuple[str, str | None, float]] = [
    ("ChatGPT", r"\bpro\b(?!\w)", 200), ("ChatGPT", r"plus", 20), ("ChatGPT", r"\bgo\b", 5),
    ("Claude", r"max.*20|20x", 200), ("Claude", r"max", 100), ("Claude", r"pro", 20),
    ("Gemini", r"ultra", 250), ("Gemini", None, 20),
    ("Grok", r"heavy", 300), ("Grok", None, 30),
    ("Perplexity", r"max", 200), ("Perplexity", None, 20),
    ("Cursor", r"ultra", 200), ("Cursor", r"pro\+", 60), ("Cursor", None, 20),
    ("Midjourney", r"pro", 60), ("Midjourney", r"standard", 30), ("Midjourney", None, 10),
    ("CapCut", None, 10), ("Canva", None, 15),
    ("ElevenLabs", r"pro", 99), ("ElevenLabs", r"creator", 22), ("ElevenLabs", None, 5),
    ("Kling", r"premier", 64), ("Kling", r"pro", 26), ("Kling", None, 7),
    ("Runway", r"pro", 28), ("Runway", None, 12),
    ("Suno", r"premier", 30), ("Suno", None, 10),
    ("HeyGen", None, 29), ("Figma", None, 15), ("Notion", None, 10), ("Grammarly", None, 12),
    ("Microsoft 365", None, 10), ("Spotify", None, 11), ("Duolingo", None, 13), ("Lovable", None, 25),
    ("Replit", None, 25), ("Zoom", None, 16),
]
_NOT_SUB = re.compile(r"\bAPI\b|kredit|credit|token|\$\d", re.I)       # kredit / API mahsulotlarda rasmiy narx chegarasi yo'q


def _interp(cost: float) -> float:
    if cost <= _TIERS[0][0]:
        return _TIERS[0][1]
    for (c0, f0), (c1, f1) in zip(_TIERS, _TIERS[1:]):
        if cost <= c1:
            t = (math.log(cost) - math.log(c0)) / (math.log(c1) - math.log(c0))
            return f0 + (f1 - f0) * t
    return _TIERS[-1][1]


def warranty_hours(w: str | None) -> float | None:
    """«12 soat kafolat» → 12; «30 kun kafolat» → 720; «kafolatsiz» → 0; noma'lum → None."""
    if not w:
        return None
    w = w.lower()
    if "kafolatsiz" in w:
        return 0.0
    m = re.search(r"(\d+(?:\s*[-~]\s*\d+)?)\s*(soat|kun|hafta|oy|yil)", w)
    if m:
        n = float(re.split(r"[-~]", m.group(1).replace(" ", ""))[-1])
        return n * {"soat": 1, "kun": 24, "hafta": 168, "oy": 720, "yil": 8640}[m.group(2)]
    return 720.0 if "to'liq" in w else None


def warranty_weight(w: str | None) -> float:
    """Foyda qancha saqlanadi: kafolat qancha qisqa bo'lsa, narx shuncha arzon (foyda kamroq)."""
    h = warranty_hours(w)
    if h is None or h >= 720:
        return 1.0
    if h >= 168:
        return 0.9
    if h >= 24:
        return 0.8
    if h >= 12:
        return 0.7
    return 0.6


def months_of(name: str) -> float | None:
    m = re.search(r"(\d+)\s*(oy|yil|kun|hafta)\b", name or "", re.I)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return n if unit == "oy" else n * 12 if unit == "yil" else n * 7 / 30 if unit == "hafta" else n / 30


def official_total(brand: str, name: str) -> float | None:
    """Obunaning rasmiy narxi (USD, butun muddat uchun) — ma'lum bo'lsa."""
    if _NOT_SUB.search(name or ""):
        return None
    months = months_of(name)
    if not months:
        return None
    for b, rx, monthly in OFFICIAL:
        if b == brand and (rx is None or re.search(rx, name or "", re.I)):
            total = monthly * months
            return total * (0.82 if months >= 12 else 1.0)       # yillik rejalar odatda ~18% arzon
    return None


def _nice(usd: float) -> float:
    """3$ gacha 0.25$, 10$ gacha 0.5$, undan yuqorida 1$ qadam."""
    return round(usd * 4) / 4 if usd < 3 else round(usd * 2) / 2 if usd < 10 else float(round(usd))


def sell_usd(cost: float, name: str = "", brand: str = "", warranty: str | None = None) -> float:
    """Sotuv narxi (USD)."""
    mult = 1 + (_interp(cost) - 1) * warranty_weight(warranty)
    price = cost * mult
    off = official_total(brand, name)
    if off:
        price = min(price, off * (1 - UNDERCUT))
    price = max(price, cost * MIN_MARGIN)
    return max(_nice(price), round(cost * MIN_MARGIN, 2), 0.25)
