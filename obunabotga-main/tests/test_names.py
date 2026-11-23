"""Nomlar o'zbekchasi, yumaloq so'm narx, CapCut 7 kun va qo'llanmalar.   Ishga tushirish:  python tests/test_names.py"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="k", USD_TO_UZS="12000")

from database.models import Product, ProductSource  # noqa: E402
from services import canboso, guides  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def item(name: str, usd: float = 3.0, ptype: str = "account") -> dict:
    return {"productId": "1", "name": name, "price": {"amount": usd}, "availability": {"available": 5}, "productType": ptype}


def prod(name: str, brand: str, ptype: str = "account", logo: str = "") -> Product:
    import json
    return Product(name=name, brand=brand, logo=logo, source=ProductSource.API, external_id="cb:1", price=1000,
                   supplier_data=json.dumps({"type": ptype, "warranty": ""}))


def main() -> None:
    # 1) yumaloq so'm narx
    c = canboso.clean_uzs
    check(c(48_120) == 48_000 and c(4_187) == 4_200 and c(3_000) == 3_000, "48 120 → 48 000, 4 187 → 4 200")
    check(c(191_880) == 192_000 and c(2_087_000) == 2_090_000, "yirik narxlar ham yumaloq")
    check(c(1_010, cost=1_000) >= 1_050, "asl narxdan 5% dan kam foyda qolmaydi")
    for usd in (0.4, 1.11, 1.35, 2, 5.5, 11.64, 33, 120):
        _, p = canboso.sell_price_uzs(usd, 12_100, "ChatGPT Plus 1 oy", "ChatGPT", "")
        check(p % 100 == 0 and p >= usd * 12_100 * 1.05, f"{usd}$ → {p} so'm yumaloq va foydali")

    # 2) nomlar to'liq o'zbekcha
    cases = {
        "Leonardo AI 8500 credits 1 month": "Leonardo AI 8500 kredit 1 oy",
        "Leonardo AI 8500 cre / 1 month": "Leonardo AI 8500 kredit 1 oy",
        "Capcut Pro 1000 7 days": "CapCut Pro 1000 7 kun",
        "ChatGPT Plus 1 Month - Warranty 30 days": "ChatGPT Plus 1 oy",
        "CapCut Pro 2 weeks": "CapCut Pro 2 hafta",
        "Gemini AI Pro Lifetime": "Gemini AI Pro umrbod",
        "Midjourney Basic Yearly subscription": "Midjourney Basic yillik obuna",
    }
    for raw, want in cases.items():
        got = canboso.parse_item(item(raw))["name"]
        check(got == want, f"{raw!r} → {got!r}")
    english = re.compile(r"\b(credits?|month|months|days?|weeks?|with|for|warranty|account|subscription|lifetime|yearly)\b", re.I)
    for raw in cases:
        check(not english.search(canboso.parse_item(item(raw))["name"]), f"inglizcha so'z qolmagan: {raw}")

    # 3) CapCut: egasi qarori — muddat va kafolat bo'yicha cheklov yo'q
    for nm in ("CapCut Pro 1 day", "CapCut Pro 7 days", "Capcut Pro 1000 7d no warranty"):
        check(not canboso.parse_item(item(nm))["blocked"], f"CapCut «{nm}» ham do'konga chiqadi")
    check(not canboso.parse_item(item("CapCut Pro 1 month 30 days warranty"))["blocked"], "CapCut 1 oylik, 30 kun kafolatli qoladi")
    check(canboso.parse_item(item("CapCut Pro 1000 30 days warranty"))["reason"] == "", "muddati yo'q, lekin 30 kun kafolatli CapCut qoladi")
    check("CapCut" not in canboso.parse_item(item("Claude Pro 1 day 30 days warranty"))["reason"], "CapCut'ga xos qoida boshqa brendga tegmaydi")

    # kafolat: nomda bo'lmasa, API'ning boshqa matn maydonlaridan olinadi
    r = item("Gemini AI Pro 18 months", 1.11)
    r["description"] = "Includes 30 days warranty. Login by Google."
    check(canboso.parse_item(r)["warranty"] == "30 kun kafolat", "kafolat tavsif maydonidan olinadi")
    check(canboso.parse_item(item("Gemini AI Pro 18 months", 1.11))["warranty"] == "", "kafolat yo'q bo'lsa — bo'sh (o'ylab topilmaydi)")

    # 4) qo'llanmalar
    g = guides.default_guide(prod("ChatGPT Plus 1 oy", "ChatGPT", "upgrade_account"))
    check("chatgpt.com" in g and "Plus" in g and len(g.splitlines()) == 4, "ChatGPT (akkaunt yangilash) qo'llanmasi")
    g = guides.default_guide(prod("Leonardo AI 8500 kredit 1 oy", "Leonardo AI", "account"))
    check("app.leonardo.ai" in g and "Canva" in g and "8500 kredit" in g, "Leonardo 8500 kredit qo'llanmasi (Canva orqali kirish, taxminiy sarf)")
    g = guides.default_guide(prod("Gemini AI Pro 12 oy", "Gemini", "slot"))
    check("taklif" in g and "Spam" in g and "gemini.google.com" in g, "Gemini (taklif) qo'llanmasi")
    g = guides.default_guide(prod("API Codex $10 1 oy", "ChatGPT", "account"))
    check("vibi.top" in g and "Wallet" in g and "API Keys" in g and "ChatGPT (GPT va Codex)" in g, "ChatGPT/Codex API: vibi.top → Wallet → kod → API Keys qo'llanmasi")
    g2 = guides.default_guide(prod("API Claude Opus 1 oy", "Claude", "account"))
    check("vibi.top" in g2 and "Claude (Opus, Sonnet, Haiku)" in g2 and g2.replace("Claude (Opus, Sonnet, Haiku)", "").replace("Claude", "") != "", "Claude API: xuddi shu qo'llanma, faqat nomi o'zining")
    g = guides.default_guide(prod("API Perplexity 1 oy", "Yangi", "account"))
    check("API kalit" in g and "ko'rsatmang" in g, "boshqa brendlarning API qo'llanmasi (umumiy)")
    g = guides.default_guide(prod("ChatGPT Plus 1 oy 30 kun kafolat", "ChatGPT", "account"))
    check("2fa.page" in g and "openai.com/policies" in g and "Email bilan kirish" in g and "o'zgartirmang" in g and "Codex" in g, "ChatGPT akkaunt: oddiy tilda to'liq qo'llanma")
    g = guides.default_guide(prod("Notion Business 3 oy", "Notion", "slot"))
    check("Workspace" in g and "taklif" in g and "SAQLAMANG" in g and "coding" in g, "Notion Business (slot): taklif, umumiy Workspace ogohlantirishi")
    g = guides.default_guide(prod("Noma'lum xizmat 1 oy", "Yangi", "account", logo="yangi.com"))
    check("yangi.com" in g, "noma'lum brend: logotip domenidan sayt olinadi")
    check(guides.default_guide(Product(name="x", source=ProductSource.MANUAL if hasattr(ProductSource, "MANUAL") else None)) == "",
          "ta'minotchiga tegishli bo'lmagan mahsulotda tayyor qo'llanma yo'q")
    # Haqiqiy ta'minotchi nomlari: nom, kafolat, brend
    real = {
        "LINK GEMINI AI PRO 18 Months warranty 24H": ("Gemini AI Pro 18 oy", "24 soat kafolat"),
        "ChatGPT Plus VIP 1 month full warranty": ("ChatGPT Plus VIP 1 oy", "to'liq kafolat"),
        "ChatGPT Go 1 Month (20-Day Warranty)": ("ChatGPT Go 1 oy", "20 kun kafolat"),
        "Capcut Pro 7 D full warranty": ("CapCut Pro 7 kun", "to'liq kafolat"),
        "LEONARDO AI Essential 8500 Credit 1 month - 12H warranty": ("Leonardo AI 8500 kredit 1 oy", "12 soat kafolat"),
        "ELEVENLABS CREATOR 1 MONTH - [5D warranty]": ("ElevenLabs Creator 1 oy", "5 kun kafolat"),
        "Link Gift ElevenReader Ultra 1 year warranty 1 day": ("Sovg'a ElevenReader Ultra 1 yil", "1 kun kafolat"),
        "CDK SUPER GROK 1 month warranty not included": ("Super Grok 1 oy (kod)", "kafolatsiz"),
        "Seedance 700~1k credit 1 Day - 1H warranty": ("Seedance 700-1000 kredit 1 kun", "1 soat kafolat"),
        "Higgsfield 80cre 1 month warranty 5 days": ("Higgsfield 80 kredit 1 oy", "5 kun kafolat"),
    }
    for raw, (nm, wr) in real.items():
        it = canboso.parse_item(item(raw, 3))
        check(it["name"] == nm and it["warranty"] == wr, f"{raw[:40]!r} → {it['name']!r} · {it['warranty']}")
    # ChatGPT Plus (Apple Pay): nomda «Apple Pay» yozilmaydi, ostida «to'liq kafolat»
    for raw in ("ChatGPT Plus Apple Pay 1 month full warranty", "ChatGPT Plus (Apple Pay) 1 Month Full Warranty",
                "ChatGPT Plus 1 Month Apple Pay - Full Warranty", "ChatGPT Plus ApplePay 1 month warranty full",
                "ChatGPT Plus Apple Pay 1 month Full BH", "ChatGPT Plus via Apple Pay 1 month full time warranty"):
        it = canboso.parse_item(item(raw, 14))
        check(it["name"] == "ChatGPT Plus 1 oy" and it["warranty"] == "to'liq kafolat", f"{raw!r} → {it['name']!r} · {it['warranty']}")
    check(canboso.parse_item(item("( So Beautiful) ChatGPT Plus 1 month full warranty", 14))["name"] == "ChatGPT Plus 1 oy", "«( So Beautiful)» reklama so'zi nomdan olib tashlanadi")

    def pr(name, brand, ptype="account"):
        return prod(name, brand, ptype)
    g = guides.default_guide(pr("Gemini AI Pro 18 oy", "Gemini"))
    check("havola" in g and "Gmail" in g and "Karta ulash shart emas" in g, "Gemini 18 oy: havola orqali faollashtirish")
    g = guides.default_guide(pr("ChatGPT Plus VIP 1 oy", "ChatGPT"))
    check("2fa.page" in g and "chatgpt.com" in g, "ChatGPT akkaunt: 2fa.page orqali kod")
    g = guides.default_guide(pr("ChatGPT Plus K12 Edu 2 yil", "ChatGPT"))
    check("Workspace" in g and "2fa.page" in g, "ChatGPT K12: Workspace ga qo'shilish")
    g = guides.default_guide(pr("CapCut Pro 1 oy", "CapCut"))
    check("2 ta qurilma" in g and "Space" in g, "CapCut: 2 qurilma va Space qoidasi")
    g = guides.default_guide(pr("Super Grok 1 oy (kod)", "Grok"))
    check("sso-rw" in g and "BEPUL" in g, "Grok kod: bepul tarif va cookie yo'riqnomasi")
    g = guides.default_guide(pr("Seedance 700-1000 kredit 1 kun", "Seedance"))
    check("capcut.com/login" in g, "Seedance: CapCut orqali kirish")
    g = guides.default_guide(pr("ElevenLabs Redeem-kod Creator 12 oy", "ElevenLabs"))
    check("7 kun" in g, "ElevenLabs redeem: 7 kun ichida ishlatish")
    import json
    gem = prod("Gemini AI Pro 18 oy", "Gemini")
    gem.supplier_data = json.dumps({"type": "account", "warranty": "24 soat kafolat"})
    wn = guides.warranty_note(gem)
    check("12 soat ichida" in wn and "18 oy" in wn and "faollashtirib" in wn and "login" not in wn,
          "Gemini (xariddan KEYIN): havolaga 12 soat, faollashgach 18 oy kafolat")
    wp = guides.warranty_public(gem)
    check("12 soat" in wp and "18 oy" in wp, f"Gemini (xariddan OLDIN): «{wp}»")
    chat = prod("ChatGPT Plus VIP 1 oy", "ChatGPT")
    chat.supplier_data = json.dumps({"type": "account", "warranty": "12 soat kafolat"})
    check(guides.warranty_public(chat) == "12 soat kafolat", "ChatGPT: kafolat muddati mahsulotda ko'rinadi")
    cn = guides.warranty_note(chat)
    check("12 soat ichida" in cn and "almashtirib beramiz" in cn and "almashtirib olasiz" not in cn and "2FA ni o'zgartirmang" in cn,
          "ChatGPT (xariddan keyin): muammo chiqsa almashtirib BERAMIZ, parol/2FA ni o'zgartirmang")
    leo = prod("Leonardo AI 8500 kredit 1 oy", "Leonardo AI")
    leo.supplier_data = json.dumps({"type": "account", "warranty": "12 soat kafolat"})
    check(guides.warranty_public(leo) == "" and "10 daqiqa" in guides.warranty_note(leo),
          "Leonardo: tavsifi nomdan farq qiladi — mahsulotda yo'q, xariddan keyin «10 daqiqa» matni")
    capk = prod("CapCut Pro 1000 7 kun", "CapCut")
    capk.supplier_data = json.dumps({"type": "account", "warranty": "kafolatsiz"})
    check(guides.warranty_public(capk) == "" and guides.warranty_note(capk) == "", "«Kafolatsiz» yozuvi mahsulotda ko'rsatilmaydi")
    check(guides.warranty_hours(chat) == 12 and abs(guides.warranty_hours(leo) - 10 / 60) < 1e-9, "kafolat soatlari: ChatGPT 12, Leonardo 10 daqiqa")
    check(guides.warranty_hours(gem) == 12, "Gemini havolasi: 24 soatdan 12 soatga cheklangan")
    full = prod("ChatGPT Plus VIP 1 oy", "ChatGPT")
    full.supplier_data = json.dumps({"type": "account", "warranty": "to'liq kafolat"})
    check(guides.warranty_hours(full) is None, "«to'liq kafolat» (muddatsiz) — hisoblagich yo'q")
    kod = prod("Super Grok 1 oy (kod)", "Grok")
    kod.supplier_data = json.dumps({"type": "account", "warranty": "24 soat kafolat"})
    check("24 soat" in guides.warranty_public(kod), "kod mahsuloti: qisqa kafolat xariddan oldin ko'rinadi")
    print("\n✅ Barcha nom/narx/qo'llanma testlari o'tdi")


if __name__ == "__main__":
    main()
