"""Katalogni har 3 daqiqada jim yangilash mantig'ini tekshiradi (internet va token shart emas).

Ishga tushirish:  python tests/test_catalog_sync.py
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
    BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678",
    ADMIN_IDS="1",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db",
    CANBOSO_API_KEY="test-key",
    USD_TO_UZS="12000",
    CATALOG_MARKUP_PERCENT="25",
)

from sqlalchemy import select  # noqa: E402

from config import settings  # noqa: E402
from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Product  # noqa: E402
from services import canboso, catalog_sync  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def items(n: int, skip: set[int] = frozenset(), avail: int = 5) -> list[dict]:
    return [
        {"productId": str(i), "name": f"CapCut Pro {i} Month 30 Days Warranty", "price": {"amount": 3.5},
         "availability": {"available": avail}, "productType": "account"}
        for i in range(1, n + 1) if i not in skip
    ]


async def active_ids() -> set[str]:
    async with SessionMaker() as s:
        rows = await s.scalars(select(Product).where(Product.is_active.is_(True)))
        return {p.external_id for p in rows}


async def run_sync(raw: list[dict], auto: bool):
    async with SessionMaker() as s:
        return await canboso.sync(s, raw, auto=auto)


async def main() -> None:
    await init_db()

    # ── 1. Birinchi sinxronlash ──
    r = await run_sync(items(12), auto=True)
    check(r.created == 12 and len(await active_ids()) == 12, "12 ta mahsulot qo'shildi")

    # ── 2. O'zgarmagan qatorga tegilmaydi ──
    async with SessionMaker() as s:
        before = {p.external_id: p.synced_at for p in await s.scalars(select(Product))}
    r = await run_sync(items(12), auto=True)
    async with SessionMaker() as s:
        after = {p.external_id: p.synced_at for p in await s.scalars(select(Product))}
    check(r.updated == 0 and r.unchanged == 12 and before == after,
          "o'zgarmagan mahsulotlar qayta yozilmaydi (har 3 daqiqada bazani bezovta qilmaymiz)")

    # ── 3. Bir marta tushib qolgan mahsulot darhol yashirilmaydi ──
    r = await run_sync(items(12, skip={5}), auto=True)
    check(r.deactivated == 0 and "cb:5" in await active_ids(), "mahsulot ro'yxatdan bir marta tushsa — hali ko'rinib turadi")
    r = await run_sync(items(12), auto=True)
    check("cb:5" in await active_ids() and canboso._missing.get("cb:5") is None,
          "qaytib kelsa — hisoblagich nolga tushadi")
    await run_sync(items(12, skip={5}), auto=True)
    r = await run_sync(items(12, skip={5}), auto=True)
    check(r.deactivated == 1 and "cb:5" not in await active_ids(), "ketma-ket 2 marta tushsa — yashiriladi")

    # ── 4. Qaytib kelgan mahsulot yana ko'rinadi ──
    await run_sync(items(12), auto=True)
    check("cb:5" in await active_ids(), "qaytib kelgan mahsulot yana sotuvda")

    # ── 5. Gumonli (juda qisqa) ro'yxat qabul qilinmaydi ──
    r = await run_sync(items(3), auto=True)
    check(r.deactivated == 0 and len(await active_ids()) == 12 and r.errors,
          "ta'minotchi 3 ta mahsulot qaytarsa (12 dan) — hech narsa yashirilmaydi")

    # ── 6. Qo'lda /sync — darhol, ehtiyotkorlik rejimisiz ──
    r = await run_sync(items(3), auto=False)
    check(r.deactivated == 9 and len(await active_ids()) == 3, "qo'lda /sync darhol qo'llanadi")
    await run_sync(items(12), auto=False)

    # ── 7. Qulf: ikkita sinxronlash bir vaqtda ishlamaydi ──
    state = {"now": 0, "max": 0}

    async def slow_sync(s, auto=False):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        await asyncio.sleep(0.05)
        state["now"] -= 1
        return catalog_sync.SyncResult()

    async def no_balance():
        return None

    orig_sync, orig_bal = canboso.sync, canboso.fetch_balance
    canboso.sync, canboso.fetch_balance = slow_sync, no_balance
    try:
        async def one():
            async with SessionMaker() as s:
                await catalog_sync.sync_catalog(s, auto=True)
        await asyncio.gather(one(), one(), one())
    finally:
        canboso.sync, canboso.fetch_balance = orig_sync, orig_bal
    check(state["max"] == 1, "bir vaqtda faqat bitta sinxronlash ishlaydi (qulf)")

    # ── 8. Oraliq sozlamasi ──
    settings.catalog_sync_minutes = -1
    check(catalog_sync.sync_interval_seconds() == 180, "sukut bo'yicha har 3 daqiqada (canboso kaliti bor)")
    settings.catalog_sync_minutes = 10
    check(catalog_sync.sync_interval_seconds() == 600, "CATALOG_SYNC_MINUTES=10 hurmat qilinadi")
    settings.catalog_sync_minutes = 0
    check(catalog_sync.sync_interval_seconds() == 0, "CATALOG_SYNC_MINUTES=0 — o'chiq")
    settings.catalog_sync_minutes = -1

    # ── 9. Xatolarda: kutish oshadi, adminga BIR marta xabar, tiklanganda yana bir marta ──
    delays: list[float] = []
    sent: list[tuple[int, str]] = []
    calls = {"n": 0}

    class FakeBot:
        async def send_message(self, chat_id, text):
            sent.append((chat_id, text))

    async def flaky_sync(s, items=None, auto=False):
        calls["n"] += 1
        if calls["n"] <= 6:
            raise catalog_sync.CatalogError("ta'minotchi javob bermadi")
        return catalog_sync.SyncResult()

    async def fake_sleep(sec):
        delays.append(sec)
        if len(delays) >= 9:
            raise asyncio.CancelledError

    orig = (catalog_sync.sync_catalog, catalog_sync.asyncio.sleep, catalog_sync.random.uniform)
    catalog_sync.sync_catalog = flaky_sync
    catalog_sync.asyncio.sleep = fake_sleep
    catalog_sync.random.uniform = lambda a, b: 0
    try:
        try:
            await catalog_sync.periodic_sync(FakeBot())
        except asyncio.CancelledError:
            pass
    finally:
        catalog_sync.sync_catalog, catalog_sync.asyncio.sleep, catalog_sync.random.uniform = orig

    waits = delays[1:]   # birinchisi — ishga tushgandan keyingi 20 soniya
    check(waits[:6] == [360, 720, 900, 900, 900, 900], f"xatolarda kutish oshadi va 15 daqiqada to'xtaydi: {waits[:6]}")
    check(waits[6] == 180, "tiklangach yana har 3 daqiqada")
    alerts = [t for cid, t in sent if "ketma-ket" in t and cid == 1]         # har adminga (ikkinchi admin ham oladi) bir martadan
    check(len(alerts) == 1, "5 ta ketma-ket xatodan keyin adminga BIR marta ogohlantirish (har safar emas)")
    check(any("qayta tiklandi" in t for _, t in sent), "tiklanganda adminga xabar")
    check(all(cid in settings.admins for cid, _ in sent), "xabarlar faqat adminlarga boradi, mijozlarga emas")

    print("\nHammasi joyida.")


asyncio.run(main())
