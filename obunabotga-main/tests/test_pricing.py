"""Aqlli narx siyosati testlari.   Ishga tushirish:  python tests/test_pricing.py"""
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
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="k", USD_TO_UZS="12000")

from services import canboso, pricing, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def main() -> None:
    s = pricing.sell_usd
    check(s(11.64, "ChatGPT Plus 1 oy", "ChatGPT", "30 kun kafolat") == 16.0, "ChatGPT Plus: asl 11.64$ → 16$ (rasmiy 20$ dan 4$ arzon)")
    check(s(1.35, "API Codex Astra $10 1 oy", "ChatGPT", "") == 3.0, "GPT Astra API $10: asl 1.35$ → 3$")
    check(2.5 <= s(1.11, "Google AI Pro 18 oy", "Gemini", "") <= 3.0, "Gemini AI Pro 18 oy: asl 1.11$ → 2.5–3$")
    check(s(8, "Claude Pro 1 oy", "Claude", "30 kun kafolat") < 20 * 0.85 + 0.01, "rasmiy narxdan (20$) kamida ~15% arzon")
    full = s(5, "Midjourney Basic 1 oy", "Midjourney", "to'liq kafolat")
    short = s(5, "Midjourney Basic 1 oy", "Midjourney", "12 soat kafolat")
    none = s(5, "Midjourney Basic 1 oy", "Midjourney", "kafolatsiz")
    check(full > short > none, "kafolat qisqa bo'lgan obunalar arzonroq (to'liq > 12 soat > kafolatsiz)")
    check(all(s(c, "X 1 oy", "X", "") >= c * 1.08 for c in (0.3, 1, 4, 20, 90)), "hech qachon asl narxdan 8% dan kam foyda bilan sotilmaydi")
    check(pricing.official_total("ChatGPT", "ChatGPT Plus 1 oy") == 20 and pricing.official_total("ChatGPT", "API Codex $10 1 oy") is None,
          "rasmiy narx: obunada bor, API/kreditda yo'q")
    check(pricing.warranty_hours("12 soat kafolat") == 12 and pricing.warranty_hours("kafolatsiz") == 0, "kafolat muddati tahlili")

    # so'mga o'tkazish: aqlli rejim va qo'lda foiz
    sup, price = canboso.sell_price_uzs(11.64, 12000, "ChatGPT Plus 1 oy", "ChatGPT", "30 kun kafolat")
    check(sup == round(11.64 * 12000) and price == 192000, "so'mda: 16$ × 12 000 = 192 000 so'm (taminotchi 139 680)")
    asyncio.run(runtime.set_value("pricing", "flat"))
    asyncio.run(runtime.set_value("markup", "25"))
    sup, price = canboso.sell_price_uzs(11.64, 12000, "ChatGPT Plus 1 oy", "ChatGPT", "30 kun kafolat")
    check(price == 175000, "qo'lda 25% foiz qo'yilsa — eski bir xil foiz rejimi")
    asyncio.run(runtime.set_value("pricing", "smart"))
    check(runtime.pricing_smart(), "«🧠 Aqlli narx» tugmasi rejimni qaytaradi")

    for brand in ("Telegram", "YouTube", "Discord"):
        check(brand in canboso.UNPOPULAR_BRANDS, f"O'zbekiston uchun begona xizmat sotuvdan olib tashlangan: {brand}")
    check(canboso.parse_item({"productId": "1", "name": "Telegram Premium 1 Month", "price": {"amount": 3},
                              "availability": {"available": 5}})["blocked"], "Telegram Premium sotuvga qo'shilmaydi")
    print("\nHammasi joyida ✅")


from database.db import init_db  # noqa: E402

asyncio.run(init_db())
asyncio.run(runtime.load())
asyncio.run(runtime.set_value("pricing", "smart"))     # bu test aqlli narx mantiqini tekshiradi
main()
