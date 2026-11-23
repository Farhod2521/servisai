"""Do'kondagi nomlar ta'minotchi so'zlarisiz (VIP, Astra, Slot, Renewal...) va qo'llanmalar shunga qaramay to'g'ri ishlaydi.

Ishga tushirish:  python tests/test_naming.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="test-key", USD_TO_UZS="12500")

from sqlalchemy import select  # noqa: E402

from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Product  # noqa: E402
from services import canboso, cards, guides, naming  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def raw(pid, name, ptype="account", usd=5):
    return {"productId": str(pid), "name": name, "price": {"amount": usd}, "availability": {"available": 3},
            "productType": ptype, "purchaseRequirements": {}}


async def main() -> None:
    await init_db()
    feed = [raw(1, "GPT Plus VIP 1 month full warranty"),
            raw(2, "Slot Chatgpt Business Renewal for 1 month full warranty", "slot"),
            raw(3, "API Codex Astra $100 1 month full warranty"),
            raw(4, "Notion Business Redeem 1 year"),
            raw(5, "Claude x5 officially owned, 1 month warranty, 7 days", "upgrade_account"),
            raw(6, "Slot Gemini Pro Official Owner +GG 5TB 1 YEAR 1 year full warranty", "slot"),
            raw(7, "ChatGPT Business account shared for 1 month with full warranty")]
    async with SessionMaker() as s:
        await canboso.sync(s, items=feed)
        prods = {p.external_id: p for p in await s.scalars(select(Product))}
    names = {k: p.name for k, p in prods.items()}
    check(names["cb:1"] == "ChatGPT Plus · 1 oylik", f"«GPT Plus VIP» → «{names['cb:1']}»")
    check(names["cb:2"] == "ChatGPT Business · 1 oylik · email taklif orqali", f"«Slot … Renewal» → «{names['cb:2']}»")
    check(names["cb:3"] == "API Codex $100 · 1 oylik", f"«API Codex Astra» → «{names['cb:3']}»")
    check(names["cb:4"] == "Notion Business · 1 yillik · kod", f"«Redeem» → «{names['cb:4']}»")
    check(names["cb:6"].endswith("email taklif orqali") and "GG" not in names["cb:6"], f"Gemini slot → «{names['cb:6']}»")
    check(not any(re.search(r"\b(VIP|Astra|Renewal|Slot|officially|owned|Extended)\b", n, re.I) for n in names.values()),
          "hech bir nomda ta'minotchi so'zlari qolmagan")

    # nom o'zgargan bo'lsa ham qo'llanma va karta to'g'ri ishlaydi (asl nom meta'da)
    g = guides.default_guide(prods["cb:2"])
    check("2 soat" in g and "taklif" in g, "ChatGPT Business (taklif): qo'llanma to'g'ri")
    check("vibi.top" in guides.default_guide(prods["cb:3"]) and "faollashtirish kodi" in cards.plan_text(prods["cb:3"], 0), "Codex API: vibi.top qo'llanmasi va «faollashtirish kodi» kartasi")
    check("2fa.page" in guides.default_guide(prods["cb:1"]), "ChatGPT Plus (nomida «ChatGPT» yo'q edi): qo'llanma to'g'ri")
    check("Codex ishlamaydi" in guides.default_guide(prods["cb:7"]), "ChatGPT Business umumiy akkaunt: qo'llanma to'g'ri")
    check("kafolat yo'q" in cards.plan_text(prods["cb:4"], 0).lower() or "Kafolat" in cards.plan_text(prods["cb:4"], 0), "kod kartasida kafolat satri bor")
    # eski (boshqa botlardagi) uslubdagi «1 oy» ko'rinishi yo'q; muddat/kredit kartada to'g'ri chiqadi
    check(not any(re.search(r"\d+ (oy|kun|yil)\b", n) for n in names.values()), "nomlarda «1 oy» emas, «1 oylik» uslubi")
    check("⏱ <b>Muddati:</b> 1 oy" in cards.plan_text(prods["cb:1"], 0), "mahsulot kartasida muddat to'g'ri («1 oy»)")
    # ruscha nomlar: inglizchaga o'giriladi, kafolat taniladi, do'kon nomida ruscha so'z qolmaydi
    for ru, title, warr in [("ChatGPT Plus 1 месяц гарантия 30 дней", "ChatGPT Plus · 1 oylik", "30 kun kafolat"),
                            ("ChatGPT Plus 1 мес полная гарантия", "ChatGPT Plus · 1 oylik", "to'liq kafolat"),
                            ("Kling 3000 кредитов 1 месяц гарантия 9 дней", "Kling 3 000 kredit · 1 oylik", "9 kun kafolat")]:
        it = canboso.parse_item(raw(50, ru))
        check(it["title"] == title and it["warranty"] == warr, f"ruscha «{ru}» → «{it['title']}» · {it['warranty']}")
    check(canboso.parse_item(raw(51, "Claude Pro 1 месяц без гарантии"))["warranty"] == "kafolatsiz", "«без гарантии» → kafolatsiz")
    check(not re.search(r"[А-Яа-яЁё]", canboso.parse_item(raw(52, "Аккаунт CapCut Pro 30 дней, гарантия 30 дней"))["title"]), "nomda kirill harfi qolmaydi")
    print("\nHAMMASI JOYIDA")


asyncio.run(main())
