"""Ustama jadvali (tannarx + qat'iy ustama) va do'kon kanali formati.   Ishga tushirish:  python tests/test_feed_tiers.py"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1", EXTRA_ADMIN_IDS="",
                  DATABASE_URL=f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/t.db", CANBOSO_API_KEY="k", USD_TO_UZS="12000")

from config import settings  # noqa: E402
from database.db import SessionMaker, init_db  # noqa: E402
from database.models import User  # noqa: E402
from services import canboso, feed, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


class Bot:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def send_message(self, chat_id, text, **kw):
        if self.fail:
            raise RuntimeError("Forbidden")
        self.sent.append((chat_id, text))


async def main() -> None:
    await init_db()
    # ── Ustama jadvali ──
    check([runtime.tier_markup(u) for u in (0.5, 5, 10, 20, 45, 80, 150, 400)] == [35_000, 35_000, 35_000, 50_000, 80_000, 130_000, 250_000, 250_000],
          "jadval: 1–10$ → 35k, 10–30$ → 50k, 30–60$ → 80k, 60–100$ → 130k, 100$+ → 250k")
    await runtime.set_value("pricing", "tiers")
    check(runtime.pricing_mode() == "tiers" and not runtime.pricing_smart(), "rejim: ustama jadvali (aqlli narx o'chadi)")
    for usd, extra in ((5, 35_000), (20, 50_000), (45, 80_000), (80, 130_000), (150, 250_000)):
        cost, price = canboso.sell_price_uzs(usd, 12_000, "X 1 oy", "X", "")
        check(price == canboso.clean_uzs(usd * 12_000 + extra, cost), f"{usd}$ mahsulot: tannarx + {extra:,} so'm → {price:,}".replace(",", " "))
    check(canboso.sell_price_uzs(1.11, 12_000, "Gemini AI Pro 18 oy", "Gemini", "")[1] == 48_500, "Gemini 1.11$ → 13 320 + 35 000 ≈ 48 500")
    # narx oshsa cheklov yo'q (qat'iy ustama)
    price, hold = canboso.decide_price(30_000, 13_000, {"usd": 1.0, "pol": "x", "hold": True}, 2.0, 26_000, 61_000, canboso.pricing_policy())
    check(price == 61_000 and hold is False, "ustama jadvalida narx tannarx bilan birga to'liq o'zgaradi (+5 000 cheklovi qo'llanmaydi)")
    # jadvalni o'zgartirish
    rows = runtime.parse_tiers("10 40000\n30 60000\n+ 300000")
    check(rows == [(10.0, 40_000), (30.0, 60_000), (None, 300_000)], "admin matnidan jadval o'qiladi")
    check(runtime.parse_tiers("10 40000\n5 60000\n+ 300000") is None and runtime.parse_tiers("10 40000") is None
          and runtime.parse_tiers("abc") is None and runtime.parse_tiers("10 40000\n20 50000") is None, "noto'g'ri jadval rad etiladi")
    import json
    await runtime.set_value("markup_tiers", json.dumps(rows))
    check(runtime.tier_markup(5) == 40_000 and runtime.tier_markup(500) == 300_000, "saqlangan jadval ishlaydi")
    await runtime.set_value("markup_tiers", None)
    await runtime.set_value("pricing", None)
    check(runtime.pricing_mode() == "smart", "sukut: aqlli narx (uz shop botdagi jadvaldan farqli)")
    check(runtime.tier_markup(5) == 35_000 and runtime.tier_markup(25) == 50_000 and runtime.tier_markup(500) == 250_000,
          "sukut jadval: 10$ gacha +35 000, 30$ gacha +50 000, 100$ dan yuqori +250 000")
    await runtime.set_value("pricing", "smart")
    check(runtime.pricing_mode() == "smart", "aqlli narxga qaytish mumkin")

    # ── Do'kon kanali ──
    when = datetime(2026, 10, 7, 9, 35)          # UTC → Toshkent 14:35
    user = NS(full_name="Azizbek", username="azizbek", tg_id=123456789)
    order = NS(id=1024, created_at=when, items=[NS(product_name="GPT Go 1 oy", price=49_000, qty=1, status="ok")])
    t = feed.sale_text(user, order)
    check(all(x in t for x in ("🎉 <b>OBUNA SOTIB OLINDI</b>", "Azizbek | @azizbek", "123456789", "GPT Go 1 oy", "49 000 so'm",
                                "Bot balansi", "07.10.2026 → 07.11.2026", "#ORD-1024", "07.10.2026, 14:35")), "sotuv xabari mijoz formatida")
    check("Foyda:" not in t and "tannarx" not in t.lower(), "kanalga foyda va tannarx chiqmaydi")
    check(feed.expiry(datetime(2026, 1, 31, 5, 0), "X 1 oy") == "31.01.2026 → 28.02.2026", "oy oxirida muddat to'g'ri (31.01 → 28.02)")
    check(feed.expiry(when, "CapCut 7 kun") == "07.10.2026 → 14.10.2026" and feed.expiry(when, "ChatGPT Plus") == "", "kunlik muddat; muddatsiz mahsulotda bo'sh")
    tt = feed.topup_text("Azizbek", "azizbek", 123456789, 500_000, "TOP-7", when)
    check("💵 <b>BALANS TO'LDIRILDI</b>" in tt and "500 000 so'm" in tt and "#TOP-7" in tt and "07.10.2026, 14:35" in tt, "to'ldirish xabari mijoz formatida")
    check("Yangi" not in tt and "yangi mijoz" not in t.lower(), "yangi mijoz xabari yo'q")

    bot = Bot()
    check(await feed.sale(bot, user, order) is False and not bot.sent, "FEED_CHAT_ID yo'q — hech narsa yuborilmaydi")
    settings.feed_chat_id = "-1001234567890"
    check(await feed.sale(bot, user, order) and bot.sent[0][0] == -1001234567890, "FEED_CHAT_ID bilan kanalga yuboriladi")
    async with SessionMaker() as s:
        s.add(User(tg_id=555, full_name="Dilshod", username=None))
        await s.commit()
    bot = Bot()
    await feed.topup(bot, 555, 100_000, "TOP-9")
    check("Dilshod" in bot.sent[0][1] and "100 000" in bot.sent[0][1], "to'ldirishda ism bazadan olinadi")
    check(await feed.sale(Bot(fail=True), user, order) is False, "kanal xatosi savdoni to'xtatmaydi")
    settings.feed_chat_id = ""
    print("\n✅ Ustama jadvali va do'kon kanali testlari o'tdi")


asyncio.run(main())
