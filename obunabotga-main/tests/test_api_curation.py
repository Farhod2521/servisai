"""API mahsulotlarini saralash qoidalari va admin «API'dan qo'shish» ekrani.

Qoida (egasi qarori): menyudagi 32 ta brendning HAMMA mahsuloti chiqadi; taqiqlangan turlar va ro'yxatda yo'q brendlar chiqmaydi.
Admin API ro'yxatidan istalgan mahsulotni qo'shadi/olib tashlaydi. Ishga tushirish: python tests/test_api_curation.py (internet shart emas)
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
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", CANBOSO_API_KEY="k", USD_TO_UZS="12500")

from database.db import SessionMaker, init_db  # noqa: E402
from handlers import admin_api, shop  # noqa: E402
from services import canboso, catalog_sync, curation, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def raw(pid, name, usd=10.0, available=5):
    return {"productId": str(pid), "name": name, "price": {"amount": usd}, "availability": {"available": available},
            "productType": "account", "purchaseRequirements": {}}


def allowed(name: str) -> bool:
    return not canboso.parse_item(raw(1, name))["blocked"]


class Msg:
    def __init__(self):
        self.edits = []

    async def edit_text(self, text, reply_markup=None):
        self.edits.append((text, reply_markup))


class Call:
    def __init__(self, data):
        self.data, self.message, self.answers = data, Msg(), []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    @property
    def text(self):
        return self.message.edits[-1][0] if self.message.edits else ""

    @property
    def buttons(self):
        return [b for r in self.message.edits[-1][1].inline_keyboard for b in r] if self.message.edits else []


ADMIN = NS(tg_id=1)


async def main() -> None:
    await init_db()
    await runtime.load()

    # 1) menyudagi brendlarning hamma mahsuloti — kafolat va nominaldan qat'i nazar
    for name in ["ChatGPT Plus 1 Month 10D warranty", "ChatGPT Plus 1 Month No Warranty", "Codex API $50 30 Days Warranty",
                 "Claude API $10 1 month full warranty", "Netflix Premium 1 Month", "Windows 11 Pro Key Lifetime", "Capcut Pro 1 day"]:
        check(allowed(name), f"«{name}» → qo'yiladi")
    check(canboso.detect_brand("API Codex Astra $100")[0] == "Codex", "Codex — alohida brend")
    # 2) taqiqlangan turlar baribir chiqmaydi
    for name in ["Instagram followers 1000", "[CDK] Rent OTP Codex/GPT Number 30D", "Discord server boost 14x"]:
        check(not allowed(name), f"«{name}» → qo'yilmaydi (taqiqlangan tur)")

    # 3) sinxronlash: menyudagi brendlar do'konda; ro'yxatda yo'q brend «API'dan qo'shish» ro'yxatida sababi bilan
    feed = [raw(1, "ChatGPT Plus 1 Month 30 Days Warranty", 5), raw(2, "ChatGPT Plus 1 Month 7 days warranty", 4),
            raw(3, "Codex API $100 30 Days Warranty", 90), raw(4, "Codex API $50 30 Days Warranty", 45),
            raw(5, "Codex API $500 2 Days Warranty", 450), raw(6, "Claude Pro 1 Month", 18), raw(7, "Spotify Premium 1 Month", 3),
            raw(8, "Netflix Premium 1 Month", 6)]

    async def fetch():
        return feed
    canboso.fetch_products = fetch
    async with SessionMaker() as s:
        await catalog_sync.sync_catalog(s)
        codex = {p.name for p in await shop.brand_products(s, "Codex")}
        brands = await shop.shop_brands(s)
    check(codex == {"Codex API $100", "Codex API $50", "Codex API $500"}, f"Codex: hamma nominal do'konda {sorted(codex)}")
    check({"ChatGPT", "Codex", "Claude", "Netflix"} <= set(brands) and "Spotify" not in brands, f"menyu: {brands}")
    hidden = {v["name"]: v["reason"] for v in curation.hidden_items()}
    check("Spotify Premium · 1 oylik" in hidden and "menyusida bu brend yo'q" in hidden["Spotify Premium · 1 oylik"],
          "ro'yxatda yo'q brend (Spotify) «API'dan qo'shish» ro'yxatida, sababi bilan")

    # 4) admin ekrani: ro'yxat, brend tanlash
    async with SessionMaker() as s:
        c = Call("a:api:0:-1")
        await admin_api.api_list(c, ADMIN, s)
        check("Spotify" in c.text and any(b.callback_data.startswith("a:apiadd:") for b in c.buttons), "«API'dan qo'shish»: ro'yxat va ➕ tugmalari bor")
        none = Call("a:api:0:-1")
        await admin_api.api_list(none, NS(tg_id=999), s)
        check(not none.message.edits, "admin bo'lmaganga ko'rinmaydi")

        # 5) Spotify ni admin qo'shadi — menyuning oxiriga yangi brend chiqadi
        ext_p = next(k for k, v in curation.CATALOG.items() if v["name"] == "Spotify Premium · 1 oylik")
        await admin_api.api_add(Call(f"a:apiadd:{ext_p}"), ADMIN, s)
        brands = await shop.shop_brands(s)
        check(brands[-1] == "Spotify", "admin qo'shgan brend (Spotify) menyuning oxiriga qo'shildi")
        avail = await shop.availability(s)
        check(avail["Spotify"] is True, "Spotify tugmasi yashil")

        # 6) olib tashlash va qayta qo'shish
        lst = Call("a:apix")
        await admin_api.api_added(lst, ADMIN, s)
        check("Spotify" in lst.text, "«Qo'shilganlar» ro'yxati")
        await admin_api.api_remove(Call(f"a:apidel:{ext_p}"), ADMIN, s)
        check("Spotify" not in await shop.shop_brands(s), "olib tashlangach brend do'kondan yo'qoladi")
        await admin_api.api_add(Call(f"a:apiadd:{ext_p}"), ADMIN, s)
        check("Spotify" in await shop.shop_brands(s), "qayta qo'shsa — yana paydo bo'ladi")

        # 7) keyingi sinxronlashlarda ham saqlanadi
        await catalog_sync.sync_catalog(s)
        check("Spotify" in await shop.shop_brands(s), "admin qo'shganlari keyingi sinxronlashlarda ham saqlanadi")

        # 8) katalog yuklanmagan bo'lsa — tushunarli xabar
        saved = dict(curation.CATALOG)
        curation.CATALOG.clear()
        e = Call("a:api:0:-1")
        await admin_api.api_list(e, ADMIN, s)
        curation.CATALOG.update(saved)
        check("hali yuklanmagan" in e.text, "katalog yuklanmagan bo'lsa — tushunarli xabar")
    print("\n✅ API saralash va admin ekrani testlari o'tdi")


asyncio.run(main())
