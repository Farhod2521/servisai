"""Ta’minotchi (canboso.com) API: katalog, hamyon, xarid; USD kursi va sotuv narxi.

ServesAI botidagi services/canboso.py mantig‘i (narx — botning «aqlli narx» rejimi, services/pricing.py).
API kalit faqat .env da (CANBOSO_API_KEY) — kodga yoki GitHub’ga yozilmaydi.
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass

import httpx

from ..config import settings
from . import pricing
from .catalog import PREFIX, format_delivery

log = logging.getLogger("servisai.supplier")

TIMEOUT = httpx.Timeout(30)
RATE_TTL = 6 * 3600

# Do‘konda ko‘rinadigan brendlar va ularning tartibi (botdagi services/curation.py: BASE_BRANDS)
BASE_BRANDS = [
    "ChatGPT", "Codex", "Claude", "Gemini", "Grok", "Perplexity", "DeepSeek", "Qwen", "Cursor", "n8n",
    "Kling", "Higgsfield", "Runway", "Seedance", "Google VEO", "OpenArt", "Freepik", "ElevenLabs", "Suno",
    "CapCut", "Canva", "Adobe", "Figma", "Gamma", "Notion", "Microsoft 365", "Windows", "Zoom", "Duolingo",
    "Kaspersky", "Netflix", "Autodesk",
]


class SupplierError(Exception):
    """Ta’minotchi bilan ishlashda xato (xabar adminga ko‘rsatilishi mumkin)."""


def enabled() -> bool:
    return bool(settings.canboso_api_key)


def _mask(text: str) -> str:
    key = settings.canboso_api_key
    return text.replace(key, "***") if key else text


async def _request(method: str, path: str, *, params=None, json_body=None, headers=None):
    if not settings.canboso_api_key:
        raise SupplierError("CANBOSO_API_KEY sozlanmagan")
    url = f"{settings.canboso_api_url.rstrip('/')}/{path}"
    hdrs = {"Accept": "application/json", "Accept-Language": "en-US,en;q=0.9", **(headers or {})}  # nomlar inglizcha kelsin
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.request(method, url, params=params, json=json_body, headers=hdrs)
    try:
        data = resp.json()
    except ValueError:
        data = None
    return resp.status_code, data, resp.headers


async def fetch_products() -> list[dict]:
    try:
        status, data, headers = await _request("GET", "products", params={"key": settings.canboso_api_key})
    except httpx.HTTPError as ex:
        raise SupplierError(f"Ta’minotchiga ulanib bo‘lmadi: {_mask(str(ex)) or type(ex).__name__}") from ex
    if status == 429:
        raise SupplierError(f"Ta’minotchi so‘rovlarni chekladi. {headers.get('Retry-After', '?')} soniyadan keyin urinib ko‘ring.")
    if not isinstance(data, dict) or not data.get("success"):
        msg = data.get("message") if isinstance(data, dict) else None
        raise SupplierError(f"Ta’minotchi katalogni bermadi ({status}): {msg or 'javob noto‘g‘ri'}")
    items = data.get("products")
    if not isinstance(items, list):
        raise SupplierError("Ta’minotchi javobida mahsulotlar ro‘yxati yo‘q")
    if data.get("walletCurrency") and str(data.get("walletCurrency")).upper() != "USD":
        # Narxni so‘mga aylantirish USD ga asoslangan — boshqa valyutada xato narx chiqmasin
        raise SupplierError(f"Kutilmagan valyuta: {data.get('walletCurrency')} (USD kutilgan)")
    return items


async def fetch_balance() -> float | None:
    """Ta’minotchidagi hamyon qoldig‘i (USD). Olib bo‘lmasa None."""
    try:
        status, data, _ = await _request("GET", "balance", params={"key": settings.canboso_api_key})
    except (httpx.HTTPError, SupplierError):
        return None
    if status == 200 and isinstance(data, dict) and data.get("success"):
        try:
            return float(data.get("balance"))
        except (TypeError, ValueError):
            return None
    return None


# ---------- USD kursi ----------

_rate_cache: tuple[float, float] = (0.0, 0.0)  # (vaqt, kurs)
_RATE_SOURCES = [
    ("CBU", "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/", lambda d: d[0]["Rate"]),
    ("open.er-api.com", "https://open.er-api.com/v6/latest/USD", lambda d: d["rates"]["UZS"]),
    ("exchangerate-api.com", "https://api.exchangerate-api.com/v4/latest/USD", lambda d: d["rates"]["UZS"]),
]


async def usd_rate() -> float:
    """1 USD necha so‘m. .env dagi USD_TO_UZS ustun; aks holda Markaziy bank (yoki zaxira manbalar), 6 soat keshlanadi."""
    global _rate_cache
    if settings.usd_to_uzs > 0:
        return settings.usd_to_uzs
    ts, cached = _rate_cache
    if cached and time.monotonic() - ts < RATE_TTL:
        return cached
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; servisai.uz)"}) as http:
        for name, url, pick in _RATE_SOURCES:
            try:
                rate = float(pick((await http.get(url)).json()))
                if not 1000 <= rate <= 100000:
                    raise ValueError(f"g‘alati kurs: {rate}")
            except Exception as ex:  # noqa: BLE001 — keyingi manbani sinaymiz
                errors.append(f"{name}: {type(ex).__name__}")
                continue
            _rate_cache = (time.monotonic(), rate)
            return rate
    if cached:
        log.warning("USD kursi yangilanmadi (%s), eskisi ishlatiladi: %s", "; ".join(errors), cached)
        return cached
    raise SupplierError(f"USD kursini olib bo‘lmadi ({'; '.join(errors)}). .env ga USD_TO_UZS=12100 kabi yozing.")


# ---------- Narx ----------


def clean_uzs(price: float, cost: float = 0) -> int:
    """So‘m narxini «yumaloq» qiladi: 48 120 emas 48 000. Ta’minotchi narxidan 5% dan kam foyda qolsa — yuqoriga."""
    step = 100 if price < 10_000 else 500 if price < 50_000 else 1_000 if price < 200_000 else 5_000 if price < 1_000_000 else 10_000
    out = int(round(price / step) * step)
    if cost and out < cost * 1.05:
        out = int(math.ceil(cost * 1.05 / step) * step)
    return max(out, step)


def sell_price_uzs(usd: float, rate: float, name: str, brand: str, warranty: str | None) -> tuple[int, int]:
    """(ta’minotchi narxi so‘mda, sotuv narxi so‘mda) — botdagi «aqlli narx» bilan bir xil."""
    base = usd * rate
    return int(round(base)), clean_uzs(pricing.sell_usd(usd, name, brand, warranty) * rate, base)


# ---------- Xarid ----------


@dataclass
class PurchaseResult:
    kind: str  # "ok" | "failed" | "unknown"
    content: str = ""
    message: str = ""
    completed: bool = False  # ta’minotchi buyurtmani tugatdimi (slot/upgrade’lar keyinroq bajariladi)
    order_code: str = ""


async def purchase(
    external_id: str, quantity: int, idempotency_key: str, *, email: str | None = None, accounts: list[str] | None = None
) -> PurchaseResult:
    """Ta’minotchidan xarid.

    "failed"  — xarid O‘TMAGAN, pulni qaytarish xavfsiz.
    "unknown" — natija noma’lum (tarmoq uzildi / jarayonda): pul qaytarilmaydi, admin tekshiradi.
    Bir xil Idempotency-Key bilan qayta yuborish ikki marta sotib olmaydi.
    """
    body: dict = {
        "key": settings.canboso_api_key,
        "product_id": external_id.removeprefix(PREFIX),
        "quantity": quantity,
    }
    if email:
        body["customer_email"] = email
    if accounts:
        body["customer_accounts"] = accounts

    last_err = ""
    for attempt in range(3):
        try:
            status, data, _ = await _request("POST", "purchase", json_body=body, headers={"Idempotency-Key": idempotency_key})
        except httpx.HTTPError as ex:
            last_err = _mask(str(ex)) or type(ex).__name__
            await asyncio.sleep(2 * (attempt + 1))
            continue

        msg = (data or {}).get("message", "") if isinstance(data, dict) else ""
        if status == 200 and isinstance(data, dict) and data.get("success"):
            order = data.get("order") or {}
            content = format_delivery(data.get("delivery"))
            return PurchaseResult(
                "ok",
                content=content,
                completed=str(order.get("status")) == "completed" and bool(content),
                order_code=str(order.get("orderCode") or ""),
            )
        if status == 409 and "progress" in msg.lower():
            last_err = msg
            await asyncio.sleep(2 * (attempt + 1))
            continue
        if status in (400, 401, 404, 409, 429, 503):
            return PurchaseResult("failed", message=msg or f"Ta’minotchi xatosi ({status})")
        last_err = f"HTTP {status} {msg}".strip()
        await asyncio.sleep(2 * (attempt + 1))

    return PurchaseResult("unknown", message=last_err or "javob kelmadi")
