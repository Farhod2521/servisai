"""Fragment orqali Stars/Premium: narx (USD × kurs + ustama), xarid natijalari (pul ketdi / ketmadi / noma'lum), manba tanlash.
Soxta Fragment mijozi bilan (internet, hamyon va pyfragment kutubxonasi shart emas).

Ishga tushirish:  python tests/test_fragment.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", USD_TO_UZS="12500", BACKUP_DIR=f"{_tmp}/z",
                  STARSUNO_KEY="su-test", FRAGMENT_SEED="soz " * 24, FRAGMENT_API_KEY="tonapi-test",
                  FRAGMENT_COOKIES='{"stel_ssid": "x", "stel_token": "y"}')

from database.db import init_db  # noqa: E402
from services import fragment_tg, runtime, starsuno, tgshop  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


class UserNotFoundError(Exception): ...
class InsufficientBalanceError(Exception): ...
class ProviderError(Exception): ...
class VerificationError(Exception): ...
class ConfigurationError(Exception): ...


class FakeFragment:
    def __init__(self):
        self.on_transfer_prepared = None
        self.calls, self.mode, self.linked = [], "ok", False

    async def get_stars_packages(self):
        if self.mode == "broken":
            raise ConfigurationError("bad seed")
        return [NS(stars=50, gram=Decimal("0.25"), usd=Decimal("0.75")), NS(stars=100, gram=Decimal("0.5"), usd=Decimal("1.5"))]

    async def get_premium_packages(self):
        return [NS(months=3, gram=Decimal("4"), usd=Decimal("12")), NS(months=6, gram=Decimal("5.3"), usd=Decimal("16")),
                NS(months=12, gram=Decimal("9.7"), usd=Decimal("29"))]

    async def get_wallet(self):
        return NS(gram_balance=Decimal("10"), address="UQA4-test-address")

    async def link_wallet(self):
        self.linked = True

    async def _pay(self, what):
        self.calls.append(what)
        if self.mode == "notfound":
            raise UserNotFoundError("no user")
        if self.mode == "nomoney":
            raise InsufficientBalanceError("low")
        if self.mode == "unlinked" and not self.linked:
            raise VerificationError("wallet not linked")
        await self.on_transfer_prepared(NS(msg_hash="abc123"))
        if self.mode == "after_send":
            raise ProviderError("dropped while sending")
        return NS(transaction_id="abc123", confirmed=self.mode != "unconfirmed")

    async def purchase_stars(self, username, amount):
        return await self._pay(("stars", username, amount))

    async def purchase_premium(self, username, months):
        return await self._pay(("premium", username, months))


async def main() -> None:
    await init_db()
    await runtime.load()
    fake = FakeFragment()
    fragment_tg._client = fake

    check(fragment_tg.configured() and tgshop.configured() and tgshop.provider_key() == "fragment",
          "Stars/Premium faqat Fragment orqali")
    check(fragment_tg.clean_seed("1. Weekend 2. lunar,  3) cherry") == "weekend lunar cherry",
          "hamyon so'zlari tozalanadi: raqam, nuqta, vergul, katta harf olib tashlanadi")
    unit = await tgshop.star_unit_price()
    check(abs(unit - 0.015 * 12500) < 0.01, f"1 Stars tannarxi = 0.015$ × 12 500 = {unit:.1f} so'm")
    check(await tgshop.stars_price(100) == starsuno.sell_price(unit * 100), "100 Stars sotuv narxi = tannarx + ustama")
    prem = await tgshop.premium_prices()
    check(prem == {3: 150000, 6: 200000, 12: 362500}, f"Premium tannarxlari (USD × kurs): {prem}")
    check(await tgshop.fetch_balance() == int(10 * 3.0 * 12500), "hamyon: 10 TON ≈ so'mda")

    check(await fragment_tg.wallet_info() == (10.0, "UQA4-test-address"), "admin panel: hamyon balansi va manzili")

    fake.mode = "unlinked"
    r = await tgshop.buy_stars("monk", 50)
    check(r.kind == "ok" and fake.linked and len(fake.calls) == 2,
          "hamyon Fragment akkauntiga bog'lanmagan → bot o'zi bog'laydi va xaridni qayta qiladi")
    fake.mode = "ok"
    r = await tgshop.buy_stars("monk", 100)
    check(r.kind == "ok" and fake.calls[-1] == ("stars", "monk", 100), "Stars xaridi: to'lov yuborildi → «ok»")
    fake.mode = "unconfirmed"
    r = await tgshop.buy_premium("monk", 3)
    check(r.kind == "ok" and "tasdiqlamadi" in r.message, "Fragment tasdiqlamasa ham pul ketgan → «ok», izohda tx")
    fake.mode = "notfound"
    r = await tgshop.buy_stars("yoq_user", 50)
    check(r.kind == "failed" and r.code == "006", "username topilmadi → pul ketmadi, mijozga qaytadi (006)")
    fake.mode = "nomoney"
    r = await tgshop.buy_stars("monk", 50)
    check(r.kind == "failed" and r.code == "003" and "TON" in r.message, "hamyonda TON yetmaydi → pul ketmadi, mijozga qaytadi (003)")

    fake.mode = "broken"
    fragment_tg._cache.clear()
    try:
        await tgshop.star_unit_price()
        ok = False
    except starsuno.SupplierError as ex:
        ok = "sozlama" in str(ex) or "so'z" in str(ex)
    check(ok, "Fragment narx bermasa — xato (StarsUno yo'q, boshqa joydan sotilmaydi)")
    check(await fragment_tg.check() is not None, "admin «Holat»: Fragment ishlamayotgani va sababi ko'rinadi")
    fake.mode = "ok"
    check(await fragment_tg.check() is None, "Fragment tuzalgach — yana ishlaydi")
    ConfigurationError.__name__ = "ConfigurationError"
    msg = fragment_tg._uz_error(ConfigurationError("Invalid seed phrase: bad checksum"))
    check("24" in msg and "soz" not in msg, f"so'zlar xato bo'lsa aniq sabab (so'zlarning o'zi ko'rsatilmaydi): {msg[:60]}…")
    fake.mode = "after_send"
    r = await tgshop.buy_stars("monk", 50)
    check(r.kind == "unknown", "to'lov yuborilayotganda uzildi → «noma'lum» (pul qaytarilmaydi, admin tekshiradi)")
    n = len(fake.calls)
    r = await tgshop.buy_stars("monk", 49)
    check(r.kind == "failed" and len(fake.calls) == n, "49 Stars — Fragment'ga so'rov yuborilmaydi")

    # Hamyon turini avtomatik aniqlash: Telegram Wallet so'zlari V5R1 ga mos kelmasa — «TG» bilan ulanadi
    import types
    tried = []

    class FakeClient:
        def __init__(self, seed, api_key, cookies, wallet_version, api_provider):
            tried.append(wallet_version)
            if wallet_version != "TG":
                raise ConfigurationError("Invalid seed phrase: invalid mnemonic")
            self.seed = seed

    sys.modules["pyfragment"] = types.SimpleNamespace(FragmentClient=FakeClient)
    fragment_tg._client = None
    cl = fragment_tg.client()
    check(isinstance(cl, FakeClient) and tried == ["V5R1", "TG"] and fragment_tg.STATE["wallet_version"].startswith("TG"),
          "12 so'zli Telegram Wallet — hamyon turi avtomatik «TG» aniqlanadi")
    print("\nHAMMASI JOYIDA")


asyncio.run(main())
