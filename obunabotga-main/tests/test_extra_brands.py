"""Qo'shimcha AI brendlar (Gemini, Perplexity, Grok, Higgsfield): menyuda faqat KAFOLATI bor (kamida 24 soat) mahsulot bo'lsa chiqadi.

Ishga tushirish:  python tests/test_extra_brands.py   (internet va kalit shart emas)
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="test-key", USD_TO_UZS="12500")

from database.db import SessionMaker, init_db  # noqa: E402
from handlers.shop import SERVICES, brand_products, services_kb, shop_brands  # noqa: E402
from services import canboso, curation  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def raw(pid, name, usd=5, available=3, extra=None):
    d = {"productId": str(pid), "name": name, "price": {"amount": usd}, "availability": {"available": available},
         "productType": "account", "purchaseRequirements": {}}
    d.update(extra or {})
    return d


async def main() -> None:
    await init_db()
    p = canboso.parse_item
    for n in ("Gemini Advanced 1 Month 7 Days Warranty", "Perplexity Pro 1 Year 12H Warranty", "Grok SuperGrok 1 Month",
              "Higgsfield Pro 1 Month No Warranty", "Claude Pro 1 Month"):
        check(not p(raw(1, n))["blocked"], f"«{n}» → do'konga chiqadi (egasi qarori: kafolatdan qat'i nazar)")
    it = p(raw(8, "Gemini Advanced 1 Month 30 Days Warranty", extra={"description": "Open the link and confirm. Do not change email."}))
    check(it["info"] == ["description: Open the link and confirm. Do not change email."], "ta'minotchining qo'shimcha matni (yo'riqnoma) saqlanadi")

    async with SessionMaker() as s:
        check(await shop_brands(s) == [], "mahsulot yo'q — menyuda brend yo'q (bo'sh qizil tugmalar chiqmaydi)")
    items = [raw(10, "Gemini Advanced 1 Month 30 Days Warranty"), raw(11, "Perplexity Pro 1 Month"),
             raw(12, "Higgsfield Pro 1 Month 20 Days Warranty", available=0), raw(13, "ChatGPT Plus 1 Month 30 Days Warranty"),
             raw(14, "Suno Pro 1 Month 30 Days Warranty")]
    async with SessionMaker() as s:
        res = await canboso.sync(s, items=items)
    check(res.created == 5 and res.skipped == 0, f"sinxronlash: hammasi qo'shildi ({res.created}/{res.skipped})")
    async with SessionMaker() as s:
        brands = await shop_brands(s)
        check(brands == ["ChatGPT", "Gemini", "Perplexity", "Higgsfield", "Suno"], f"menyu: mahsuloti bor brendlar, egasi tartibida ({brands})")
        check(len(await brand_products(s, "Gemini")) == 1, "Gemini ichida tarif ko'rinadi")
        kb = services_kb({b: True for b in brands})
        check(sum(len(r) for r in kb.inline_keyboard) == 5, "tugmalar: 5 ta brend")
    print("\nHAMMASI JOYIDA")



def codes_check() -> None:
    """Redeem kodlar kafolatsiz bo'lsa ham qo'yiladi; oddiy kafolatsiz obuna esa yo'q."""
    p = canboso.parse_item
    for n in ["Railway Hobby Redeem 1 year", "Cursor Pro Redeem 12 months", "Runway Pro Redeem 1 year", "redeem Notion Business 3 months",
              "Perplexity PRO Redeem 1 year", "Higgsfield Pro Redeem 12 months", "ElevenLabs Redeem 300K Credit"]:
        check(not p(raw(1, n))["blocked"], f"redeem kod «{n}» → qo'yiladi (kafolatsiz ham)")
    check(not p(raw(1, "ChatGPT Plus 1 Month No Warranty"))["blocked"], "kafolatsiz obuna ham chiqadi (egasi qarori)")


def guides_check() -> None:
    """Ta'minotchi PDF ma'lumotidagi mahsulotlar uchun qo'llanmalar: ta'minotchi tavsifidan, oddiy o'zbekchada."""
    import json
    from database.models import Product, ProductSource
    from services import guides

    def g(raw_name: str, ptype: str = "account") -> str:
        it = canboso.parse_item(raw(1, raw_name))
        p = Product(name=it["name"], brand=it["brand"], source=ProductSource.API, external_id="cb:1", price=1000,
                    supplier_data=json.dumps({"type": ptype, "warranty": it["warranty"]}))
        return guides.default_guide(p)

    t = g("GPT Plus VIP 1 month full warranty")
    check("2fa.page" in t and "openai.com/policies" in t and "Email bilan kirish" in t, "ChatGPT Plus (email|parol|2FA) qo'llanmasi")
    t = g("Chatgpt Pro $500 1 month, 3-day warranty")
    check("2FA ni o'zgartiring" in t and "buyurtma bo'yicha" in t, "ChatGPT Pro $500 (3 kun): darhol 2FA o'zgartirish ogohlantirishi")
    t = g("Chatgpt Pro $500 1 month full warranty")
    check("2FA ni o'zgartiring" not in t, "ChatGPT Pro $500 (30 kun to'liq): shu ogohlantirish yo'q")
    check("30 daqiqadan 1 soatgacha" in g("CHATGPT PRO X100 1 MONTH (7D warranty)"), "ChatGPT Pro X100: buyurtma vaqti")
    t = g("Slot Chatgpt Business Renewal for 1 month full warranty", "slot")
    check("2 soat" in t and "taklif" in t, "ChatGPT Business slot: email, taklif, 2 soatlik tuzatish")
    check("Codex ishlamaydi" in g("ChatGPT Business account shared for 1 month with full warranty"), "ChatGPT Business umumiy akkaunt")
    t = g("API Codex Astra $100 1 month full warranty")
    check("vibi.top" in t and "Wallet" in t and "Codex (GPT)" in t, "Codex API: vibi.top → Wallet → kod → API Keys")
    t2 = g("Claude API $100 1 month full warranty")
    check("Claude (Opus, Sonnet, Haiku)" in t2 and "Wallet" in t2, "Claude API: xuddi shu qo'llanma, nomi Claude")
    t = g("GEMINI API $100 1 month full warranty")
    check("SHART EMAS" in t and "usage" in t and "Wallet" not in t, "Gemini API: tayyor kalit, faollashtirish shart emas")
    check("SHART EMAS" in g("Grok API $100 1 month full warranty"), "Grok API: tayyor kalit")
    t = g("Gemini Pro Slot +5TB Google One 1 month full warranty", "slot")
    check("Google Family" in t and "5 TB" in t, "Gemini slot: Family taklifi, 5 TB")
    t = g("Perplexity Pro officially owned, 30 days full warranty", "upgrade_account")
    check("login|parol|2fa" in t, "Perplexity (akkauntni yangilash): bir qatorda login|parol|2fa")
    check("30 daqiqa" in g("Perplexity Pro 30-day full warranty"), "Perplexity tayyor akkaunt: 30 daqiqa")
    check("Cursor va Grok Super" in g("GROK SUPER 15X 1 MONTH (7D warranty)", "upgrade_account"), "Grok Super: akkaunt ma'lumoti va Google bilan kirish")
    t = g("Higgsfield Genjutsu 30-day limit, 24-hour warranty")
    check("OTP" in t and "720p" in t and "20 daqiqa" in t, "Higgsfield Genjutsu: akkaunt, OTP, 20 daqiqa")
    t = g("Slot Notion Business has an official AI with a full 3-month warranty", "slot")
    check("SAQLAMANG" in t and "coding" in t, "Notion Business slot")
    check("parolni o'zgartiring" in g("Notion Plus 1 year full warranty"), "Notion Plus (Education): parolni o'zgartirish")
    t = g("Capcut Pro 14-20 Days full warranty")
    check("QR" in t and "2 ta qurilma" in t, "CapCut: QR bilan kompyuterga kirish, 1–2 qurilma")
    check("Vibi.pro" in g("ElevenLabs Redeem 300K Credit"), "ElevenLabs kredit kodi: Vibi.pro")
    check("7 kun" in g("ElevenLabs Redeem Creator 12 months"), "ElevenLabs Creator kodi: 7 kun ichida")
    check("QR" not in g("RUNWAY PRO 1 MONTH (15-day warranty)", "upgrade_account") and "1–2 soatda" in g("RUNWAY PRO 1 MONTH (15-day warranty)", "upgrade_account"), "Runway: akkauntni yangilash")
    t = g("Dreamina US 8k6 credit 7-day warranty 3D")
    check(canboso.detect_brand("Dreamina US 8k6 credit 7-day warranty 3D")[0] == "Seedance" and "34 ta Seedance" in t, "Dreamina → Seedance brendi va qo'llanma")
    check("faqat EMAIL" in g("Kling 3000 credit 1 month warranty 9D"), "Kling: faqat email orqali kirish")
    check("YANGI Railway" in g("Railway Hobby Redeem 1 year"), "Railway: faollashtirish havolasi")
    check("OCHMANG" in g("Cursor Pro Redeem 12 months"), "Cursor kodi: havolani tekshirish uchun ochmang")
    check("300 Notion Credits" in g("redeem Notion Business 3 months") and "Cursor" not in g("redeem Notion Business 3 months"), "Notion redeem: kod/havola qo'llanmasi")
    check("4000 kredit" in g("Perplexity PRO Redeem 1 year"), "Perplexity redeem")
    check("600 ball" in g("Higgsfield Pro Redeem 12 months"), "Higgsfield redeem")
    check("2250 kredit" in g("Runway Pro Redeem 1 year"), "Runway redeem")
    check("Access Grok Bot" in g("Cursor Pro Plus bonus Grok Bot redeem 1 month"), "Cursor Pro+ Grok Bot redeem")
    print("qo'llanmalar: hammasi joyida")


codes_check()
guides_check()
asyncio.run(main())
