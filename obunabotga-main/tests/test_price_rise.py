"""Ta'minotchi narxi oshganda bizning narx sakramasligi.   Ishga tushirish:  python tests/test_price_rise.py"""
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

from sqlalchemy import select  # noqa: E402

from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Product  # noqa: E402
from services import canboso, overrides, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def item(usd: float, name: str = "DeepSeek Pro 1 Month 30 Days Warranty") -> list[dict]:
    return [{"productId": "1", "name": name, "price": {"amount": usd}, "availability": {"available": 5}, "productType": "account"}]


async def price() -> tuple[int, int]:
    async with SessionMaker() as s:
        p = await s.scalar(select(Product))
        return p.price, p.supplier_price


async def sync(raw):
    async with SessionMaker() as s:
        return await canboso.sync(s, raw, auto=False)


async def main() -> None:
    c = canboso.cap_rise
    # birlik: foyda eng ko'pi bilan 5 000 so'm o'sadi
    check(c(30_000, 13_000, 26_000, 90_000) == 48_000, "ta'minotchi narxi ikki barobar: foyda +5 000 dan oshmaydi (30 000 → 48 000, 90 000 emas)")
    check(c(30_000, 13_000, 26_000, 40_000) == 40_000, "hisoblangan narx cheklovdan past bo'lsa — o'sha olinadi")
    check(c(30_000, 13_000, 9_000, 25_000) == 25_000, "ta'minotchi narxi tushsa — cheklov yo'q")
    check(c(30_000, 13_000, 13_000, 33_000) == 33_000, "ta'minotchi narxi o'zgarmasa — cheklov yo'q")
    check(c(0, 0, 26_000, 90_000) == 90_000, "yangi mahsulot (eski narx yo'q) — cheklov yo'q")

    # sinxron: 1$ → 2$ (aqlli narx rejimida: cheklov shu rejimda ishlaydi)
    await init_db()
    await runtime.load()
    await runtime.set_value("pricing", "smart")
    await sync(item(1.0))
    p0, c0 = await price()
    await sync(item(2.0))
    p1, c1 = await price()
    profit0, profit1 = p0 - c0, p1 - c1
    free = canboso.sell_price_uzs(2.0, 12000, "DeepSeek Pro 1 oy", "DeepSeek", "")[1]
    check(c1 > c0 and p1 > p0, f"ta'minotchi 1$ → 2$: bizning narx ham oshdi ({p0} → {p1})")
    check(profit1 - profit0 <= 5_500, f"foyda {profit0} → {profit1}: o'sish 5 000 dan oshmadi")
    check(p1 < free, f"cheklovsiz narx {free} bo'lardi, endi {p1}")

    # keyingi sinxronda (narx o'zgarmagan) cheklangan narx USHLAB turiladi — qayta sakramaydi
    for _ in range(3):
        r = await sync(item(2.0))
    check((await price())[0] == p1 and r.price_changes == [], "narx o'zgarmaguncha cheklangan narx ushlab turiladi (har sinxronda 5 000 dan qo'shilmaydi)")

    # narx tushsa — hisoblangan narxga qaytadi (cheklov yo'q)
    await sync(item(1.0))
    p2, _ = await price()
    check(p2 == p0, "ta'minotchi narxi tushsa — narx avvalgisiga qaytadi")

    # reprice_all (kurs o'zgarishi) ham cheklanadi
    runtime.usd_rate_override = lambda: 24000.0          # kurs ikki barobar
    async with SessionMaker() as s:
        await canboso.reprice_all(s)
    p3, c3 = await price()
    check(c3 > c0 and (p3 - c3) - (p0 - c0) <= 5_500, f"kurs ikki barobar oshsa ham foyda 5 000 dan ko'p o'smaydi ({p3 - c3 - (p0 - c0)})")

    # qo'lda qo'yilgan narxga tegilmaydi
    async with SessionMaker() as s:
        p = await s.scalar(select(Product))
        p.price = 99_999
        overrides.lock(p, "price")
        await s.commit()
    await sync(item(5.0))
    check((await price())[0] == 99_999, "🔒 qo'lda qo'yilgan narx o'zgarmaydi")
    print("\n✅ Narx o'sishi cheklovi testlari o'tdi")


asyncio.run(main())
