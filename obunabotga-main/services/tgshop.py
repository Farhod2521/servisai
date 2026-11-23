"""Telegram Stars / Premium — faqat Fragment (fragment.com) orqali. StarsUno olib tashlangan.

Narx ustamasi: ⚙️ Admin panel → ⭐ Stars / Premium → 💹 Ustama foizi (starsuno.markup_percent — umumiy hisob-kitob).
"""
from __future__ import annotations

from services import fragment_tg
from services.starsuno import (  # noqa: F401 — umumiy narsalar (natija turi, chegaralar, ustama)
    ADMIN_CODES, MAX_STARS, MIN_STARS, MONTHS, Result, SupplierError, low_balance, markup_percent, sell_price, valid_username,
)

NAMES = {"fragment": "Fragment"}


def provider_key() -> str:
    return "fragment"


def preferred_key() -> str:
    return "fragment"


def configured() -> bool:
    return fragment_tg.configured()


async def star_unit_price() -> float:
    return await fragment_tg.star_unit_price()


async def premium_prices() -> dict[int, int]:
    return await fragment_tg.premium_prices()


async def stars_price(amount: int) -> int:
    return sell_price(await star_unit_price() * amount)


async def premium_price(month: int) -> int:
    prices = await premium_prices()
    if month not in prices:
        raise SupplierError("Bu muddat mavjud emas")
    return sell_price(prices[month])


async def buy_stars(username: str, amount: int) -> Result:
    return await fragment_tg.buy_stars(username, amount)


async def buy_premium(username: str, month: int) -> Result:
    return await fragment_tg.buy_premium(username, month)


async def fetch_balance() -> int | None:
    return await fragment_tg.fetch_balance()
