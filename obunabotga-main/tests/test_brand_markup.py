"""Brend foizlari: admin har brendga o'z foizini qo'yadi (CapCut 40%, Claude 25%) — o'sha brend narxlari tannarx + foiz.

Ishga tushirish:  python tests/test_brand_markup.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1", EXTRA_ADMIN_IDS="1",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="k", USD_TO_UZS="12500",
                  BACKUP_DIR=f"{_tmp}/zaxira")

from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from sqlalchemy import select  # noqa: E402

from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Product  # noqa: E402
from handlers import admin_brand  # noqa: E402
from services import canboso, overrides, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def raw(pid, name, usd):
    return {"productId": str(pid), "name": name, "price": {"amount": usd}, "availability": {"available": 5},
            "productType": "account", "purchaseRequirements": {}}


class Msg:
    def __init__(self, text=""):
        self.text, self.out = text, []

    async def edit_text(self, text, reply_markup=None):
        self.out.append((text, reply_markup))

    async def answer(self, text, reply_markup=None):
        self.out.append((text, reply_markup))


class Call:
    def __init__(self, data):
        self.data, self.message = data, Msg()

    async def answer(self, *a, **k):
        pass


async def prices(brand):
    async with SessionMaker() as s:
        return {p.name: (p.price, p.supplier_price) for p in await s.scalars(select(Product).where(Product.brand == brand))}


async def main() -> None:
    await init_db()
    await runtime.load()
    async with SessionMaker() as s:
        await canboso.sync(s, items=[raw(1, "CapCut Pro 1 Month", 2.0), raw(2, "CapCut Pro Team 12 Months", 20.0),
                                     raw(3, "Claude Pro 1 Month", 18.0), raw(4, "Kling Standard 1 Month", 7.0)])
    before_kling = await prices("Kling")
    admin = NS(tg_id=1)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))

    async with SessionMaker() as s:
        c = Call("a:bm")
        await admin_brand.show(c, admin, s, state)
        text, kb = c.message.out[-1]
        labels = [b.text for r in kb.inline_keyboard for b in r]
        check("Brend foizlari" in text and any(l.startswith("CapCut · umumiy") for l in labels), "ekran: brendlar ro'yxati, hammasi «umumiy»")
        brands = await admin_brand._brands(s)
        await admin_brand.pick(Call(f"a:bm:{brands.index('CapCut')}"), admin, s, state)
        m = Msg("40")
        await admin_brand.save(m, admin, s, state)
        check("CapCut</b>: 40% qo'yildi" in m.out[-1][0], "CapCut ga 40% qo'yildi")
    cap = await prices("CapCut")
    ok = all(price == canboso.clean_uzs(cost * 1.40, cost) for price, cost in cap.values())
    check(ok, f"CapCut'ning hamma tarifi = tannarx + 40% {cap}")
    check(await prices("Kling") == before_kling, "boshqa brend (Kling) narxi o'zgarmadi (qayta hisoblashda ham bir xil)")

    async with SessionMaker() as s:
        await admin_brand.pick(Call(f"a:bm:{brands.index('Claude')}"), admin, s, state)
        await admin_brand.save(Msg("25%"), admin, s, state)
    (cl_price, cl_cost), = (await prices("Claude")).values()
    check(cl_price == canboso.clean_uzs(cl_cost * 1.25, cl_cost), "Claude = tannarx + 25% («25%» yozilsa ham tushunadi)")

    # keyingi sinxronlashda ham foiz saqlanadi
    async with SessionMaker() as s:
        await canboso.sync(s, items=[raw(1, "CapCut Pro 1 Month", 2.0), raw(2, "CapCut Pro Team 12 Months", 20.0),
                                     raw(3, "Claude Pro 1 Month", 18.0), raw(4, "Kling Standard 1 Month", 7.0)])
    check(await prices("CapCut") == cap, "katalog yangilansa ham CapCut narxi foiz bilan qoladi")

    # qo'lda qulflangan narx o'zgarmaydi
    async with SessionMaker() as s:
        p = await s.scalar(select(Product).where(Product.external_id == "cb:2"))
        p.price = 999_000
        overrides.lock(p, "price")
        await s.commit()
        await admin_brand.pick(Call(f"a:bm:{brands.index('CapCut')}"), admin, s, state)
        await admin_brand.save(Msg("60"), admin, s, state)
    cap2 = await prices("CapCut")
    check(cap2["CapCut Pro jamoa · 12 oylik"][0] == 999_000, "🔒 qo'lda qo'yilgan narx o'zgarmadi")
    p1, c1 = cap2["CapCut Pro · 1 oylik"]
    check(p1 == canboso.clean_uzs(c1 * 1.60, c1), "CapCut 60% ga o'zgardi (qolgan tarif)")

    # «-» — umumiy qoidaga qaytaradi
    async with SessionMaker() as s:
        await admin_brand.pick(Call(f"a:bm:{brands.index('CapCut')}"), admin, s, state)
        await admin_brand.save(Msg("-"), admin, s, state)
    check("CapCut" not in runtime.brand_markups(), "«-» yuborilsa — CapCut umumiy qoidaga qaytdi")
    check(await state.get_state() is None, "holat tozalandi")
    print("\nHAMMASI JOYIDA")


asyncio.run(main())
