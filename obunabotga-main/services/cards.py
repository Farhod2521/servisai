"""Mahsulot kartasi: o'zbek mijozga bir qarashda tushunarli matn.

Ta'minotchi ma'lumotidan (tur, kafolat, nom) ko'rinadigan, sodda satrlar yasaydi:
  📦 Nima olasiz · ⏱ Muddati · 🎟 Kredit (nima ekani tushuntiriladi) · 🛡 Kafolat (nima ekani tushuntiriladi) · 💵 Narxi.
Admin mahsulot tavsifini qo'lda yozgan bo'lsa — o'sha ishlatiladi (handlers/shop.py).
"""
from __future__ import annotations

import html
import re

from database.models import Product
from locales.texts import money
from services import canboso, guides

_DURATION = re.compile(r"(?<![\w.])(\d+)\s*(soat|kun|hafta|oy|yil)\b", re.I)
_CREDITS = re.compile(r"(?<![\w.])(\d[\d\s]*(?:\s*-\s*\d[\d\s]*)?)\s*(mln\s+)?kredit\b", re.I)
_CODE = re.compile(r"\bkod\b|\bkalit\b|redeem", re.I)
_API = re.compile(r"\bapi\b", re.I)


def duration_of(name: str) -> str:
    """Nomdagi obuna muddati («1 oy», «7 kun»); bo'lmasa ''."""
    m = _DURATION.search(name or "")
    return f"{m.group(1)} {m.group(2).lower()}" if m else ""


def credits_of(name: str) -> str:
    """Nomdagi kredit soni («660 kredit», «5 mln kredit»); bo'lmasa ''."""
    m = _CREDITS.search(name or "")
    if not m:
        return ""
    num = re.sub(r"\s+", " ", m.group(1)).strip()
    return f"{num}{' mln' if m.group(2) else ''} kredit"


def delivery_of(p: Product, meta: dict) -> str:
    """«Nima olasiz» — oddiy gap bilan."""
    need, ptype = meta.get("need"), meta.get("type") or "account"
    if need == "email":
        return "obuna sizning <b>emailingizga</b> ulanadi (xaridda email so'raladi)"
    if need == "accounts":
        return "obuna sizning <b>akkauntingizga</b> ulanadi (xaridda login so'raladi)"
    if ptype == "upgrade_account":
        return "<b>mavjud akkauntingiz</b> yangilanadi"
    if ptype == "slot":
        return "<b>taklif (invite)</b>: emailingizga yuboriladi, buyurtma qo'lda bajariladi"
    if _API.search(canboso.search_name(p)):
        if p.brand in guides.ai_guides.API_PACKAGE_BRANDS:
            return "<b>faollashtirish kodi</b>: xariddan so'ng darhol shu chatga yuboriladi; uni vibi.top saytida API kalitga aylantirasiz"
        return "<b>API kalit</b>: xariddan so'ng darhol shu chatga yuboriladi"
    if _CODE.search(canboso.search_name(p)):
        return "<b>kod (kalit)</b>: xariddan so'ng shu chatga yuboriladi"
    if ptype == "account":
        return "<b>tayyor akkaunt</b>: login va parol xariddan so'ng darhol shu chatga yuboriladi"
    return "buyurtma qo'lda bajariladi, holatini «Buyurtmalarim» da ko'rasiz"


def warranty_line(p: Product, meta: dict) -> str:
    """«Kafolat» satri: muddat va u nimani anglatishi; kafolatsiz bo'lsa ochiq aytiladi; ma'lumot yo'q bo'lsa ''."""
    w = (meta.get("warranty") or "").strip()
    if w == "kafolatsiz":
        return "🛡 <b>Kafolat:</b> yo'q"
    public = guides.warranty_public(p)
    if not public:
        if re.search(r"redeem|\(kod\)", canboso.search_name(p), re.I):
            return "🛡 <b>Kafolat:</b> yo'q: rasmiy kod faollashtirilgach qaytarilmaydi — xariddan keyin darhol ishlating"
        return ""
    if public.lower().startswith("to'liq"):
        return "🛡 <b>Kafolat:</b> to'liq: obuna muddati davomida muammo chiqsa, «Yordam»ga yozing, akkauntni almashtirib beramiz"
    dur = re.sub(r"\s*kafolat$", "", public).strip()
    return (f"🛡 <b>Kafolat:</b> {html.escape(dur)}: shu vaqt ichida muammo chiqsa, «Yordam»ga yozing, "
            "akkauntni almashtirib beramiz")


def plan_text(p: Product, balance: int, icon: str = "💎") -> str:
    """O'zbekcha mahsulot kartasi (ta'minotchi mahsulotlari uchun). `icon` — sarlavha oldidagi belgi (brend premium emojisi)."""
    meta = canboso.product_meta(p)
    lines = [f"{icon} <b>{html.escape(p.name)}</b>", "", f"📦 <b>Nima olasiz:</b> {delivery_of(p, meta)}"]
    dur = duration_of(canboso.plain_name(p))
    if dur:
        lines.append(f"⏱ <b>Muddati:</b> {dur}")
    credits = credits_of(canboso.plain_name(p))
    if credits:
        lines.append(f"🎟 <b>Kredit:</b> {credits}: xizmat ichidagi hisob (rasm, video va boshqalarni yaratish uchun sarflanadi)")
    wl = warranty_line(p, meta)
    if wl:
        lines.append(wl)
    lines += ["", f"💵 <b>Narxi:</b> {money(p.price)}", f"💳 <b>Hisobingiz:</b> {money(balance)}"]
    return "\n".join(lines)
