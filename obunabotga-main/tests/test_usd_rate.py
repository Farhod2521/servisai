"""USD kursi: manbalar ketma-ket sinaladi, oxirgi muvaffaqiyatli kurs saqlanadi, hech narsa bo'lmasa — aniq xabar.
Ishga tushirish:  python tests/test_usd_rate.py   (internet shart emas)
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
os.environ.update(
    BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="k",
)
os.environ.pop("USD_TO_UZS", None)

from database.db import init_db  # noqa: E402
from services import canboso, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def src(name, value):
    async def fetch(_http):
        if isinstance(value, Exception):
            raise value
        return value
    return name, fetch


async def main() -> None:
    await init_db()
    await runtime.load()

    # 1) birinchi manba ochilmasa — keyingisi ishlaydi va kurs saqlanadi
    canboso.RATE_SOURCES = [src("CBU", ConnectionError("blok")), src("NBU", ValueError("bo'sh")), src("ER", 12150.5)]
    canboso._rate_cache = (0.0, 0.0)
    check(await canboso.usd_rate() == 12150.5, "CBU va NBU ochilmasa ham — keyingi manbadan kurs olinadi")
    check(runtime.usd_last() == 12150.5, "oxirgi muvaffaqiyatli kurs bazaga saqlandi")

    # 2) hamma manba ochilmasa — saqlangan oxirgi kurs ishlatiladi (katalog to'xtab qolmaydi)
    canboso.RATE_SOURCES = [src("A", ConnectionError("x")), src("B", TimeoutError())]
    canboso._rate_cache = (0.0, 0.0)
    check(await canboso.usd_rate() == 12150.5, "hamma manba ochilmasa — saqlangan oxirgi kurs ishlatiladi")

    # 3) g'alati kurs (masalan 0 yoki 5) rad etiladi
    canboso.RATE_SOURCES = [src("BAD", 5.0), src("OK", 12200.0)]
    canboso._rate_cache = (0.0, 0.0)
    check(await canboso.usd_rate() == 12200.0, "g'alati kurs (5 so'm) rad etilib, keyingi manbaga o'tiladi")

    # 4) hech qachon kurs olinmagan va hamma manba ochilmasa — aniq, admin paneliga yo'naltiruvchi xabar
    await runtime.set_value("usd_last", None)
    canboso.RATE_SOURCES = [src("A", ConnectionError("x")), src("B", TimeoutError())]
    canboso._rate_cache = (0.0, 0.0)
    try:
        await canboso.usd_rate()
        ok, msg = False, ""
    except canboso.SupplierError as ex:
        ok, msg = True, str(ex)
    check(ok and "USD kursi" in msg and "Admin panel" in msg and "12100" in msg and "A: ConnectionError" in msg,
          "kurs umuman olinmasa — xabar admin paneldagi «USD kursi» ga yo'naltiradi va qaysi manba nima bo'lganini aytadi")

    # 5) qo'lda berilgan kurs hamma narsadan ustun (internetga umuman chiqmaydi)
    await runtime.set_value("usd_rate", "12345")
    canboso.RATE_SOURCES = [src("A", RuntimeError("chaqirilmasligi kerak"))]
    canboso._rate_cache = (0.0, 0.0)
    check(await canboso.usd_rate() == 12345.0, "qo'lda yozilgan kurs ustun — manbalar so'ralmaydi")

    # 6) manbalar ro'yxatida Markaziy bank birinchi, kamida 3 ta zaxira bor
    import importlib
    importlib.reload(canboso)
    check([n for n, _ in canboso.RATE_SOURCES][0] == "CBU" and len(canboso.RATE_SOURCES) >= 4, "Markaziy bank birinchi; kamida 3 ta zaxira manba bor")
    print("\n✅ USD kursi testlari o'tdi")


asyncio.run(main())
