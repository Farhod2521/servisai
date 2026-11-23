"""Fragment (fragment.com) orqali Telegram Stars va Premium — StarsUno'ga muqobil manba.

Ishlash tartibi: Fragment narxni GRAM (ex TON) da beradi, to'lov bizning TON hamyonimizdan avtomatik yuboriladi
(kutubxona: pyfragment — hamyon so'zlari faqat shu kompyuterda imzo uchun ishlatiladi, hech qayerga yuborilmaydi).
Narx so'mga: Fragment ko'rsatgan USD narx × dollar kursi; sotuv narxi = tannarx + Stars/Premium ustamasi.

Natija (services/starsuno.Result bilan bir xil):
  ok       — to'lov yuborildi (Fragment tasdiqlamagan bo'lsa ham pul ketgan: adminga tekshirish uchun xabar);
  failed   — pul YUBORILMADI (username topilmadi, hamyonda pul yo'q, cookie eskirgan…) → mijoz puli qaytadi;
  unknown  — imzolangan to'lov yuborish paytida uzildi → pul qaytarilmaydi, admin tekshiradi.
Bir hamyondan xaridlar navbat bilan (bir vaqtda bitta) bajariladi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from decimal import Decimal

from config import settings
from services.starsuno import MAX_STARS, MIN_STARS, MONTHS, Result, SupplierError

log = logging.getLogger("uzshop.fragment")

PRICE_TTL = 300
_client = None
_lock = asyncio.Lock()
_cache: dict[str, tuple[float, object]] = {}
STATE: dict = {"last_error": "", "last_ok": None, "down_until": 0.0}
DOWN_FOR = 600          # Fragment xato bersa — 10 daqiqa StarsUno orqali sotiladi, keyin Fragment qayta sinaladi


def mark_down(ex: Exception | str) -> None:
    """Fragment ishlamadi: sababini eslab qolamiz va logga yozamiz (sir — so'zlar/cookie — yozilmaydi)."""
    reason = ex if isinstance(ex, str) else _uz_error(ex)
    detail = "" if isinstance(ex, str) else f"{type(ex).__name__}: {str(ex)[:300]}"
    STATE["last_error"], STATE["down_until"] = reason, time.monotonic() + DOWN_FOR
    log.warning("Fragment ishlamayapti: %s | %s", reason, detail)


def is_down() -> bool:
    return time.monotonic() < STATE.get("down_until", 0.0)


def mark_up() -> None:
    STATE["down_until"], STATE["last_error"] = 0.0, ""


def configured() -> bool:
    return bool(settings.fragment_seed and settings.fragment_api_key and settings.fragment_cookies)


def _cookies():
    raw = (settings.fragment_cookies or "").strip()
    try:
        return json.loads(raw)
    except ValueError:
        return raw                                   # kutubxona «k=v; k2=v2» ko'rinishini ham tushunadi


def clean_seed(raw: str) -> str:
    """Hamyon so'zlarini tozalash: «1. weekend 2, lunar» → «weekend lunar» (raqam, vergul, nuqta, katta harf olib tashlanadi)."""
    words = re.findall(r"[a-zA-Z]+", raw or "")
    return " ".join(w.lower() for w in words)


def _make_client():
    """Hamyon turi: .env dagisi; so'zlar unga mos kelmasa — boshqa tur avtomatik sinaladi
    (Telegram Wallet — «TG», Tonkeeper — «V5R1»/«V4R2»)."""
    from pyfragment import FragmentClient           # faqat Fragment yoqilganda yuklanadi
    seed = clean_seed(settings.fragment_seed)
    first = (settings.fragment_wallet_version or "V5R1").strip().upper()
    order = [first] + [v for v in ("V5R1", "TG", "V4R2") if v != first]
    last_ex: Exception | None = None
    for ver in order:
        try:
            cl = FragmentClient(seed=seed, api_key=settings.fragment_api_key.strip(), cookies=_cookies(),
                                wallet_version=ver, api_provider=settings.fragment_api_provider or "tonapi")
        except Exception as ex:  # noqa: BLE001
            if type(ex).__name__ == "ConfigurationError" and "seed" in str(ex).lower():
                last_ex = ex                        # so'zlar bu turga mos emas — keyingisini sinaymiz
                continue
            raise
        STATE["wallet_version"] = ver + ("" if ver == first else " (avtomatik aniqlandi)")
        if ver != first:
            log.warning("Fragment: FRAGMENT_WALLET_VERSION=%s so'zlarga mos emas, %s ishlatildi", first, ver)
        return cl
    raise last_ex  # type: ignore[misc]


def client():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def _uz_error(ex: Exception) -> str:
    name = type(ex).__name__
    if name == "ConfigurationError":               # aniq sabab (so'zlarning o'zi xabarga qo'shilmaydi)
        msg = str(ex).lower()
        if "seed" in msg:
            n = len(clean_seed(settings.fragment_seed).split())
            return (f"FRAGMENT_SEED dagi hamyon so'zlari xato ({n} ta so'z topildi; 12 yoki 24 bo'lishi kerak) — "
                    "so'zlarni tartib bilan, orasida bittadan bo'sh joy qilib qayta yozing")
        if "missing" in msg:
            return "FRAGMENT_SEED yoki FRAGMENT_API_KEY bo'sh"
        if "provider" in msg:
            return "FRAGMENT_API_PROVIDER xato (tonapi yoki toncenter bo'lishi kerak)"
    if name in ("ModuleNotFoundError", "ImportError"):
        return "Fragment kutubxonasi o'rnatilmagan (requirements.txt dagi pyfragment)"
    return {
        "UserNotFoundError": "Bunday @username topilmadi",
        "AlreadySubscribedError": "Bu foydalanuvchida Premium allaqachon bor",
        "InsufficientBalanceError": "Fragment hamyonida (TON) pul yetarli emas",
        "SessionExpiredError": "Fragment sessiyasi eskirgan — cookie'larni yangilang",
        "CookieError": "Fragment cookie'lari noto'g'ri",
        "VerificationError": "Fragment tasdiq so'rayapti: KYC kerak yoki .env dagi hamyon Fragment'da ulangan hamyon emas",
        "ConfigurationError": "Fragment sozlamasi xato (hamyon so'zlari yoki API kalit)",
        "NetworkError": "Fragment'ga ulanib bo'lmadi",
        "ProviderError": "TON tarmog'iga ulanib bo'lmadi",
    }.get(name, f"Fragment xatosi: {name}")


# Mijozga ko'rsatiladigan sabab kodlari (handlers/tgstars.py dagi bilan mos): 006 — username topilmadi
_CODES = {"UserNotFoundError": "006", "RecipientError": "006", "InsufficientBalanceError": "003",
          "SessionExpiredError": "002", "CookieError": "002", "ConfigurationError": "001"}


async def _cached(key: str, loader):
    ts, val = _cache.get(key, (0.0, None))
    if val is not None and time.monotonic() - ts < PRICE_TTL:
        return val
    try:
        val = await loader()
    except Exception as ex:  # noqa: BLE001
        if val is not None:
            log.warning("Fragment narxi yangilanmadi, eskisi ishlatiladi: %s", type(ex).__name__)
            return val
        mark_down(ex)
        raise SupplierError(_uz_error(ex)) from ex
    _cache[key] = (time.monotonic(), val)
    mark_up()
    return val


async def check() -> str | None:
    """Admin «Holat» uchun: Fragment hozir javob beryaptimi (keshsiz). None — ishlayapti, aks holda sabab."""
    _cache.pop("stars_pk", None)
    try:
        await _stars_packages()
        return None
    except SupplierError as ex:
        return str(ex)


async def _usd_rate() -> float:
    from services import canboso
    return await canboso.usd_rate()


async def _stars_packages():
    return await _cached("stars_pk", lambda: client().get_stars_packages())


async def _premium_packages():
    return await _cached("prem_pk", lambda: client().get_premium_packages())


async def star_unit_price() -> float:
    """1 Stars tannarxi (so'm): Fragment paketlaridagi o'rtacha USD narx × kurs."""
    pk = await _stars_packages()
    usd = sum(Decimal(p.usd) for p in pk) / sum(Decimal(p.stars) for p in pk)
    return float(usd) * await _usd_rate()


async def premium_prices() -> dict[int, int]:
    rate = await _usd_rate()
    return {int(p.months): int(round(float(p.usd) * rate)) for p in await _premium_packages() if int(p.months) in MONTHS}


async def _usd_per_gram() -> float:
    pk = await _stars_packages()
    return float(sum(Decimal(p.usd) for p in pk) / sum(Decimal(p.gram) for p in pk))


async def fetch_balance() -> int | None:
    """Hamyondagi TON — so'mda (taxminiy). Olib bo'lmasa None."""
    if not configured():
        return None
    try:
        info = await client().get_wallet()
        return int(float(info.gram_balance) * await _usd_per_gram() * await _usd_rate())
    except Exception as ex:  # noqa: BLE001
        STATE["last_error"] = _uz_error(ex)
        return None


async def wallet_ton() -> float | None:
    info = await wallet_info()
    return info[0] if info else None


async def wallet_info() -> tuple[float, str] | None:
    """(TON balansi, hamyon manzili) — bot imzolaydigan hamyon. Manzil Fragment'da ulangan hamyon bilan bir xil bo'lishi shart."""
    try:
        w = await client().get_wallet()
        return float(w.gram_balance), str(getattr(w, "address", "") or "")
    except Exception as ex:  # noqa: BLE001
        STATE["last_error"] = _uz_error(ex)
        return None


async def _buy(call, what: str) -> Result:
    """call(client) — xarid. Yuborilish arafasida belgi qo'yiladi: shundan keyingi xato — «noma'lum» (pul ketgan bo'lishi mumkin)."""
    if not configured():
        return Result("failed", "Fragment sozlanmagan", "001")
    sent = {"flag": False}

    async def on_prepared(intent):  # noqa: ANN001
        sent["flag"] = True
        log.info("Fragment to'lovi yuborilmoqda: %s (tx %s)", what, intent.msg_hash)

    async with _lock:                                  # bitta hamyon — xaridlar navbat bilan
        cl = client()
        cl.on_transfer_prepared = on_prepared
        try:
            try:
                res = await call(cl)
            except Exception as ex:  # noqa: BLE001
                # Hamyon Fragment akkauntiga hali bog'lanmagan bo'lsa — bir marta bog'lab, qayta urinamiz (pul hali ketmagan)
                if sent["flag"] or type(ex).__name__ != "VerificationError" or STATE.get("linked"):
                    raise
                log.info("Fragment: hamyon akkauntga bog'lanmoqda (link_wallet) va xarid qayta urinilmoqda")
                STATE["linked"] = True
                await cl.link_wallet()
                res = await call(cl)
        except Exception as ex:  # noqa: BLE001
            if sent["flag"]:
                log.error("Fragment: to'lov yuborilgandan keyin xato (%s) — noma'lum", type(ex).__name__)
                return Result("unknown", f"To'lov yuborilgan, natija noma'lum ({type(ex).__name__})")
            log.warning("Fragment xaridi o'tmadi (pul ketmadi): %s: %s", type(ex).__name__, str(ex)[:300])
            code = next((c for n, c in _CODES.items() if any(k.__name__ == n for k in type(ex).__mro__)), "")
            if code != "006":                          # username xatosi Fragment buzilgani emas
                mark_down(ex)
            return Result("failed", _uz_error(ex), code)
        finally:
            cl.on_transfer_prepared = None
    STATE["last_ok"] = time.time()
    mark_up()
    note = "" if getattr(res, "confirmed", True) else f" (Fragment hali tasdiqlamadi, tx {getattr(res, 'transaction_id', '')})"
    return Result("ok", f"Yuborildi{note}")


async def buy_stars(username: str, amount: int) -> Result:
    if not MIN_STARS <= amount <= MAX_STARS:
        return Result("failed", "Stars miqdori 50–10000 oralig'ida bo'lishi kerak", "008")
    return await _buy(lambda c: c.purchase_stars(username, amount), f"{amount} Stars → @{username}")


async def buy_premium(username: str, month: int) -> Result:
    if month not in MONTHS:
        return Result("failed", "Premium muddati 3, 6 yoki 12 oy bo'lishi kerak", "007")
    return await _buy(lambda c: c.purchase_premium(username, month), f"Premium {month} oy → @{username}")
