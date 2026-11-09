"""Do'kondagi mahsulot nomlari: ta'minotchining o'ziga xos so'zlari olib tashlanadi, nom bir xil, toza ko'rinishga keladi.

Maqsad — nomga qarab mahsulot qaysi ta'minotchidan ekanini bilib bo'lmasin (VIP, Astra, «Renewal», «officially owned» kabi
ta'minotchi so'zlari yo'qoladi). Asl (inglizcha) nom mahsulot ma'lumotida («raw») saqlanadi: qo'llanma va qoidalar shunga qarab ishlaydi.
Admin istalgan mahsulot nomini qo'lda o'zgartira oladi (u ustun).
"""
from __future__ import annotations

import re

# (regex, almashtirish): ta'minotchi marketing so'zlari va belgilari
_RULES: list[tuple[str, str]] = [
    (r"\bVIP\b", ""), (r"\bAstra\b", ""), (r"\bSol\b|\bTerra\b", ""),
    (r"\bofficially\s+owned\b|\bofficial(?:ly)?\b|\bowned\b", ""),
    (r"\bUS\b(?=\s+\d)", ""),
    (r"\+\s*GG\b", "+ Google One"),
    (r"\bBiznes\b", "Business"),
    (r"\bStand\b", "Standard"),
    (r"\buzaytirish\b|\buzaytirilgan\b", ""),
    (r"\bPremium\s+Slot\b|\bSlot\b", ""),
    (r"\bRedeem-kod\b", ""),
    (r"\boyiga\b", "1 oy"),
    (r"(?<=\w),\s+(?=\d)", " "),                  # «Claude x5, 7 kun» → «Claude x5 7 kun»
]
_COMPILED = [(re.compile(p, re.I), r) for p, r in _RULES]


def own_name(brand: str, name: str, ptype: str = "account") -> str:
    """Ta'minotchi nomini (o'zbekcha tozalangan) do'konning o'z nomiga aylantiradi.
    Oxirida mahsulot turi: taklif (slot) → «(taklif)», kod/redeem → «(kod)»."""
    original = name or ""
    s = original
    was_code = bool(re.search(r"Redeem-kod|\(kod\)", s, re.I))
    was_slot = ptype == "slot" or bool(re.search(r"\bSlot\b", s, re.I))
    for rx, rep in _COMPILED:
        s = rx.sub(rep, s)
    s = re.sub(r"\(\s*kod\s*\)", "", s, flags=re.I)
    s = re.sub(r"\(\s*\)|\[\s*\]", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -,:|")
    if brand == "ChatGPT" and re.match(r"(?i)gpt\b", s):
        s = "Chat" + s                       # «GPT Plus 1 oy» → «ChatGPT Plus 1 oy»
    if len(s) < 3 or brand and brand.lower() not in s.lower() and brand.lower() in original.lower():
        s = original                         # ortiqcha qirqib yuborilgan bo'lsa — eski nom
    if was_code:
        s += " (kod)"
    elif was_slot and "(taklif)" not in s:
        s += " (taklif)"
    s = re.sub(r"\s{2,}", " ", s).strip()
    if re.match(r"(?i)n8n\b", s):
        return ("n8n" + s[3:])[:200]          # brend nomi kichik harf bilan yoziladi
    return (s[:1].upper() + s[1:])[:200] if s else original


# ─────────────────────────── Ko'rinish uslubi ───────────────────────────
# Do'kon nomlarining o'z uslubi: «Brend Tarif · muddat · tur». Qisqa «1 oy» o'rniga «1 oylik», kreditlar probel bilan («8 000 kredit»).
# Boshqa botlardagi («Brend Tarif 1 oy») nomlardan ko'rinishidanoq farq qiladi.

_SUFFIX = {"soat": "soatlik", "kun": "kunlik", "hafta": "haftalik", "oy": "oylik", "yil": "yillik"}
_TAGS = {"taklif": "email taklif orqali", "kod": "kod"}
_DUR_RX = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?)\s*(soat|kun|hafta|oy|yil)\b", re.I)
_CRED_RX = re.compile(r"(?<![\w.])(\d{4,7})(?=\s+kredit)", re.I)


def restyle(name: str) -> str:
    """«ChatGPT Plus 1 oy (taklif)» → «ChatGPT Plus · 1 oylik · email taklif orqali»."""
    s = (name or "").strip()
    if not s:
        return s
    tag = ""
    m = re.search(r"\s*\((taklif|kod)\)\s*$", s, re.I)
    if m:
        tag = _TAGS[m.group(1).lower()]
        s = s[:m.start()]
    dur = ""
    found = list(_DUR_RX.finditer(s))
    if found:
        m = found[-1]
        num = re.sub(r"\s+", "", m.group(1))
        dur = f"{num} {_SUFFIX[m.group(2).lower()]}"
        s = s[:m.start()] + " " + s[m.end():]
    s = _CRED_RX.sub(lambda m: f"{int(m.group(1)):,}".replace(",", " "), s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -,:|")
    return " · ".join(x for x in (s, dur, tag) if x) or name
