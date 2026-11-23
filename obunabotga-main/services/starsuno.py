"""Ta'minotchi: StarsUno (Telegram Stars va Premium). https://starsuno.uz/api

Hamma amal oddiy GET so'rov, javob JSON:  {"ok": true, ...}  yoki  {"ok": false, "code": "003", "error": "..."}.
  /stars/price      — 1 dona Stars narxi (so'm)
  /premium/price    — Premium narxlari: {"3": ..., "6": ..., "12": ...} (so'm)
  /balance          — bizning StarsUno hisobidagi qoldiq (so'm)
  /stars/buy        — username, amount (50–10000): Stars yuboradi
  /premium/buy      — username, month (3 / 6 / 12): Premium taqdim etadi

Kalit faqat Render muhitida (STARSUNO_KEY), kodga yoki GitHub'ga yozilmaydi; URL dagi kalit loglarda yashiriladi.

Buyurtma natijasi uch xil (services/fulfillment.py dagi qoida bilan bir xil):
  ok       — yuborildi;
  failed   — API aniq rad etdi (username topilmadi, hisob yetmaydi...) → mijoz puli qaytariladi;
  unknown  — javob kelmadi / tushunarsiz / «yuborishda xatolik» (004, 005) → pul QAYTARILMAYDI (yuborilgan bo'lishi mumkin),
             admin qo'lda tekshiradi. Bu API'da Idempotency-Key yo'q, shuning uchun qayta urinish HECH QACHON qilinmaydi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass

import aiohttp

from config import settings
from services import runtime

log = logging.getLogger("uzshop.starsuno")

BASE_URL = "https://starsuno.uz"
TIMEOUT = aiohttp.ClientTimeout(total=60)
PRICE_TTL = 300
MIN_STARS, MAX_STARS = 50, 10000
MONTHS = (3, 6, 12)
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

# Rad etish kodlari: so'rov bajarilmagani aniq (tekshiruv bosqichida to'xtagan) → pul qaytariladi
DEFINITE = {"001", "002", "003", "006", "007", "008", "009", "010"}
# Biz tomondagi/hisobdagi muammo: adminga xabar beriladi (kalit, balans)
ADMIN_CODES = {"001", "002", "003"}
CODE_TEXT = {
    "001": "API kalit yuborilmagan", "002": "API kalit noto'g'ri yoki topilmadi",
    "003": "StarsUno hisobida mablag' yetarli emas", "004": "Stars yuborishda xatolik",
    "005": "Premium yuborishda xatolik", "006": "Username topilmadi",
    "007": "Premium muddati 3, 6 yoki 12 oy bo'lishi kerak", "008": "Stars miqdori 50–10000 oralig'ida bo'lishi kerak",
    "009": "Gift topilmadi", "010": "Izoh juda uzun", "011": "Gift yuborishda xatolik",
}


class SupplierError(Exception):
    pass


@dataclass
class Result:
    kind: str                 # "ok" | "failed" | "unknown"
    message: str = ""
    code: str = ""
    balance: int | None = None


def configured() -> bool:
    return bool(settings.starsuno_key)


def _mask(text: str) -> str:
    key = settings.starsuno_key
    return text.replace(key, "***") if key else text


def valid_username(raw: str) -> str | None:
    """«@monk» / «monk» / «https://t.me/monk» → «monk»; yaroqsiz bo'lsa None."""
    s = (raw or "").strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):].split("/")[0].split("?")[0]
    s = s.lstrip("@")
    return s if USERNAME_RE.match(s) else None


async def _get(path: str, **params) -> dict:
    """GET so'rov → JSON (dict). Ulanish/format xatosi — SupplierError (so'rov yuborilgan bo'lishi mumkin: qayta urinmaymiz)."""
    if not settings.starsuno_key:
        raise SupplierError("STARSUNO_KEY sozlanmagan")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as http:
            async with http.get(f"{BASE_URL}/{path}", params={"key": settings.starsuno_key, **params}) as resp:
                body = await resp.text()
    except aiohttp.ClientConnectorError as ex:          # hech qachon ulanmagan → so'rov yuborilmagan
        raise ConnectionRefusedError(_mask(str(ex))) from ex
    except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
        raise SupplierError(f"Javob olinmadi: {_mask(type(ex).__name__ + ' ' + str(ex))}") from ex
    try:
        data = json.loads(body)
    except ValueError as ex:
        raise SupplierError(f"Tushunarsiz javob (HTTP {resp.status})") from ex
    if not isinstance(data, dict):
        raise SupplierError("Tushunarsiz javob")
    return data


# ─────────────────────────── Narxlar ───────────────────────────

_cache: dict[str, tuple[float, object]] = {}


async def _cached(key: str, loader):
    ts, val = _cache.get(key, (0.0, None))
    if val is not None and time.monotonic() - ts < PRICE_TTL:
        return val
    try:
        val = await loader()
    except (SupplierError, ConnectionRefusedError) as ex:
        if _cache.get(key, (0, None))[1] is not None:
            log.warning("StarsUno narxi yangilanmadi, eskisi ishlatiladi: %s", ex)
            return _cache[key][1]
        raise SupplierError("StarsUno bilan bog'lanib bo'lmadi") from ex
    _cache[key] = (time.monotonic(), val)
    return val


async def _load_star_price() -> float:
    d = await _get("stars/price")
    if not d.get("ok") or float(d.get("price") or 0) <= 0:
        raise SupplierError("Stars narxi olinmadi")
    return float(d["price"])


async def _load_premium_prices() -> dict[int, int]:
    d = await _get("premium/price")
    prices = d.get("prices")
    if not d.get("ok") or not isinstance(prices, dict):
        raise SupplierError("Premium narxlari olinmadi")
    out = {int(k): int(v) for k, v in prices.items() if str(k).isdigit() and int(k) in MONTHS and float(v) > 0}
    if not out:
        raise SupplierError("Premium narxlari bo'sh")
    return out


async def star_unit_price() -> float:
    return await _cached("stars", _load_star_price)


async def premium_prices() -> dict[int, int]:
    return await _cached("premium", _load_premium_prices)


def sell_price(cost: float) -> int:
    """Sotuv narxi (so'm): tannarx + ustama foizi, yuqoriga 100 so'mgacha yaxlitlanadi."""
    return int(math.ceil(round(cost * (100 + markup_percent()) / 10000, 6)) * 100)   # round: float xatosi (275.00000001) ortiqcha 100 so'm qo'shmasin


def markup_percent() -> float:
    try:
        return max(0.0, float(runtime._cache["tg_markup"]))
    except (KeyError, ValueError):
        return 10.0


async def stars_price(amount: int) -> int:
    return sell_price(await star_unit_price() * amount)


async def premium_price(month: int) -> int:
    prices = await premium_prices()
    if month not in prices:
        raise SupplierError("Bu muddat mavjud emas")
    return sell_price(prices[month])


# ─────────────────────────── Balans ───────────────────────────

async def fetch_balance() -> int | None:
    """StarsUno hisobidagi qoldiq (so'm). Olib bo'lmasa None."""
    try:
        d = await _get("balance")
    except (SupplierError, ConnectionRefusedError):
        return None
    try:
        return int(float(d["balance"])) if d.get("ok") else None
    except (KeyError, TypeError, ValueError):
        return None


def low_balance() -> int:
    try:
        return int(float(runtime._cache["tg_low"]))
    except (KeyError, ValueError):
        return 100_000


# ─────────────────────────── Xarid ───────────────────────────

def _parse(data: dict) -> Result:
    bal = data.get("balance")
    bal = int(bal) if isinstance(bal, (int, float)) else None
    if data.get("ok") is True:
        return Result("ok", str(data.get("message") or ""), balance=bal)
    code = str(data.get("code") or "")
    msg = str(data.get("error") or CODE_TEXT.get(code) or "Noma'lum xato")
    return Result("failed" if code in DEFINITE else "unknown", msg, code)


async def _buy(path: str, **params) -> Result:
    try:
        data = await _get(path, **params)
    except ConnectionRefusedError as ex:
        return Result("failed", "StarsUno ochilmadi (so'rov yuborilmadi)")
    except SupplierError as ex:
        log.error("StarsUno %s natijasi noma'lum: %s", path, ex)
        return Result("unknown", str(ex))
    res = _parse(data)
    if res.kind != "ok":
        log.warning("StarsUno %s: kod=%s %s", path, res.code, res.message)
    return res


async def buy_stars(username: str, amount: int) -> Result:
    if not MIN_STARS <= amount <= MAX_STARS:
        return Result("failed", CODE_TEXT["008"], "008")
    return await _buy("stars/buy", username=username, amount=amount)


async def buy_premium(username: str, month: int) -> Result:
    if month not in MONTHS:
        return Result("failed", CODE_TEXT["007"], "007")
    return await _buy("premium/buy", username=username, month=month)
