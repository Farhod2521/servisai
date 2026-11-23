"""Ta'minotchi katalogini botga sinxronizatsiya qilish.

Kutilayotgan JSON formati:

    {
      "status": "success",
      "last_updated": "2026-09-30T10:00:00Z",
      "data": [
        {
          "external_id": "OD-10293",
          "title": "Simsiz quloqchinlar Pro 5",
          "price": 150000,
          "category": "Elektronika",
          "stock": 45,
          "image_url": "https://.../pro5.jpg",
          "description": "..."
        }
      ]
    }

Ishlash mantig'i:
  • external_id — asosiy kalit. Shu bo'yicha tovar topiladi yoki yaratiladi.
  • Narx: ta'minotchi narxi + CATALOG_MARKUP_PERCENT, keyin yaxlitlanadi.
  • Qo'lda kiritilgan tovarlarga (source=manual) TEGILMAYDI.
  • Feedda yo'q bo'lib qolgan tovar o'chirilmaydi, faqat is_active=False
    bo'ladi — shunda eski buyurtmalar tarixi buzilmaydi.
  • Admin narxni qo'lda o'zgartirgan bo'lsa ham keyingi sinxronizatsiya
    uni qayta hisoblaydi. Narxni qotirib qo'yish kerak bo'lsa, tovarni
    source=manual ga o'tkazing.
"""
from __future__ import annotations

import asyncio
import random
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services import overrides
from database.models import Category, DeliveryType, Product, ProductSource

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30       # soniya
MAX_RETRIES = 3
DEFAULT_EMOJI = "📦"
DEFAULT_CATEGORY = "Boshqa"


class CatalogError(Exception):
    """Katalogni olishda yoki o'qishda yuzaga kelgan xato."""


# ─────────────────────────── Autentifikatsiya ───────────────────────────
#
# Har bir API kalitni boshqa joyda kutadi. Ba'zilari header'da, ba'zilari
# URL parametrida. Aniq bilmasak, quyidagi tartibda sinab ko'ramiz.
# Har bir element: (joy, nom, prefiks)
#   joy    — "header" yoki "query"
#   nom    — header nomi yoki parametr nomi
#   prefiks— qiymat oldiga qo'shiladigan matn ("Bearer " kabi)

AUTH_ATTEMPTS: tuple[tuple[str, str, str], ...] = (
    ("header", "Authorization", "Bearer "),
    ("header", "X-API-Key", ""),
    ("header", "key", ""),
    ("header", "apikey", ""),
    ("query", "key", ""),
    ("query", "api_key", ""),
    ("query", "apikey", ""),
    ("query", "token", ""),
)

# Kalit qabul qilinmaganini bildiruvchi so'zlar (turli tillarda)
AUTH_HINTS = (
    "key", "token", "auth", "unauthor", "forbidden",
    "thieu", "thiếu", "sai", "khong hop le", "không hợp lệ",
)


def parse_auth_style(style: str) -> list[tuple[str, str, str]]:
    """Sozlamadagi uslubni sinov ro'yxatiga aylantiradi."""
    raw = (style or "auto").strip()
    key = raw.lower()

    if key in ("auto", ""):
        return list(AUTH_ATTEMPTS)
    if key == "bearer":
        return [("header", "Authorization", "Bearer ")]
    if key in ("x-api-key", "apikey", "api-key"):
        return [("header", "X-API-Key", "")]
    if key == "token":
        return [("header", "Authorization", "Token ")]
    if key.startswith("query:"):
        return [("query", raw.split(":", 1)[1].strip(), "")]
    if key.startswith("header:"):
        return [("header", raw.split(":", 1)[1].strip(), "")]
    # Oddiy header nomi deb qabul qilamiz
    return [("header", raw, "")]


def describe_attempt(attempt: tuple[str, str, str]) -> str:
    place, name, prefix = attempt
    if place == "query":
        return f"?{name}=…"
    return f"{name}: {prefix}…" if prefix else f"{name}: …"


def apply_auth(
    attempt: tuple[str, str, str], token: str
) -> tuple[dict[str, str], dict[str, str]]:
    """Header va query parametrlarini tayyorlaydi."""
    headers = {"Accept": "application/json"}
    params: dict[str, str] = {}
    if not token:
        return headers, params

    place, name, prefix = attempt
    if place == "query":
        params[name] = f"{prefix}{token}"
    else:
        headers[name] = f"{prefix}{token}"
    return headers, params


def looks_like_auth_error(payload, body: str) -> bool:
    """Javob 'kalit yo'q/noto'g'ri' deganini aytyaptimi?"""
    message = ""
    if isinstance(payload, dict):
        if payload.get("success") is True or str(payload.get("status", "")).lower() in ("success", "ok"):
            return False
        for field in ("message", "error", "msg", "detail"):
            value = payload.get(field)
            if isinstance(value, str):
                message = value
                break
    text = (message or body or "").lower()
    return any(hint in text for hint in AUTH_HINTS)


def clean_url(raw: str) -> str:
    """Manzildan ortiqcha belgilarni tozalaydi.

    Odamlar ko'pincha markdown havola yoki qo'shtirnoq bilan nusxalaydi:
        [https://a.uz/api](https://a.uz/api)  → https://a.uz/api
        "https://a.uz/api"                    → https://a.uz/api
    """
    text = (raw or "").strip()
    match = re.search(r'https?://[^\s\)\]>"\'<]+', text)
    return match.group(0) if match else text.strip('"\'<>[]() ')


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    note: str = ""
    # Mijozlarga xabar beriladigan hodisalar: {"id", "kind": "new"|"restock", "added", "stock"} — fon sinxronlashida to'ldiriladi
    events: list[dict] = field(default_factory=list)
    # Narxi o'zgargan obunalar: {"id", "name", "old", "new"} — admin «Narx o'zgarishlari» va ogohlantirish uchun
    price_changes: list[dict] = field(default_factory=list)

    @property
    def total_seen(self) -> int:
        return self.created + self.updated + self.unchanged

    def report(self) -> str:
        lines = [
            "🔄 <b>Katalog yangilandi</b>",
            "",
            f"🆕 Yangi qo'shildi: <b>{self.created}</b>",
            f"♻️ Yangilandi: <b>{self.updated}</b>",
            f"➖ O'zgarmadi: <b>{self.unchanged}</b>",
            f"🚫 O'chirib qo'yildi: <b>{self.deactivated}</b>",
        ]
        if self.skipped:
            lines.append(f"⚠️ Tashlab ketildi: <b>{self.skipped}</b>")
        if self.note:
            lines.append(self.note)
        if self.errors:
            lines.append("")
            lines.append("❗️ <b>Xatolar:</b>")
            for err in self.errors[:5]:
                lines.append(f"• {err}")
            if len(self.errors) > 5:
                lines.append(f"• …va yana {len(self.errors) - 5} ta")
        return "\n".join(lines)


# ─────────────────────────── Tarmoq ───────────────────────────

async def fetch_catalog(url: str | None = None, token: str | None = None) -> list[dict]:
    """API dan tovarlar ro'yxatini oladi. Xato bo'lsa CatalogError."""
    url = clean_url(url or settings.catalog_api_url)
    token = (token if token is not None else settings.catalog_api_token).strip()

    if not url:
        raise CatalogError("CATALOG_API_URL sozlanmagan")

    if not url.lower().startswith(("http://", "https://")):
        hint = url if len(url) <= 24 else url[:24] + "…"
        raise CatalogError(
            "CATALOG_API_URL to'liq manzil bo'lishi kerak.\n\n"
            f"Hozir u yerda: <code>{hint}</code>\n\n"
            "To'g'ri ko'rinishi:\n"
            "<code>CATALOG_API_URL=https://example.uz/api/products</code>\n"
            "<code>CATALOG_API_TOKEN=tokeningiz</code>\n\n"
            "Token alohida o'zgaruvchiga yoziladi, manzil qatoriga emas."
        )

    attempts = parse_auth_style(settings.catalog_auth_style)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    last_network_error: Exception | None = None
    auth_bodies: list[str] = []

    for attempt in attempts:
        headers, params = apply_auth(attempt, token)

        for retry in range(1, MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as http:
                    async with http.get(url, headers=headers, params=params) as resp:
                        body = await resp.text()
                        status = resp.status
            except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
                last_network_error = ex
                if retry < MAX_RETRIES:
                    await asyncio.sleep(2 ** retry)   # 2s, 4s
                    continue
                break   # keyingi uslubga o'tmaymiz — bu tarmoq muammosi
            else:
                last_network_error = None

            try:
                payload = json.loads(body)
            except ValueError:
                payload = None

            # Kalit qabul qilinmadi — keyingi uslubni sinaymiz
            if status in (400, 401, 403) or (
                payload is not None and looks_like_auth_error(payload, body)
            ):
                if looks_like_auth_error(payload, body) or status in (401, 403):
                    auth_bodies.append(f"{describe_attempt(attempt)} → {body[:120]}")
                    break
                raise CatalogError(
                    f"API {status} qaytardi — so'rov noto'g'ri.\n"
                    f"Server javobi: <code>{body[:250]}</code>"
                )

            if status == 404:
                raise CatalogError(
                    "API 404 qaytardi — bunday manzil yo'q.\n"
                    "CATALOG_API_URL ni hamkoringizdan qayta aniqlang."
                )
            if status != 200:
                raise CatalogError(
                    f"API {status} qaytardi.\n"
                    f"Javob: <code>{body[:250]}</code>"
                )
            if payload is None:
                raise CatalogError(
                    "Javob JSON emas.\n"
                    f"Boshlanishi: <code>{body[:150]}</code>"
                )

            if attempt != attempts[0]:
                log.info("Katalog: kalit '%s' ko'rinishida qabul qilindi",
                         describe_attempt(attempt))
            return _extract_items(payload)

        if last_network_error:
            break

    if last_network_error:
        raise CatalogError(f"API ga ulanib bo'lmadi: {last_network_error}")

    tried = "\n".join(f"• {line}" for line in auth_bodies[:6])
    raise CatalogError(
        "API kalitni qabul qilmadi.\n\n"
        "Sinab ko'rilgan usullar va server javobi:\n"
        f"{tried}\n\n"
        "Hamkoringizdan aniqlang: kalit qaysi nom bilan va qayerda "
        "yuborilishi kerak — header'dami yoki URL parametridami.\n\n"
        "Keyin <code>CATALOG_AUTH_STYLE</code> ga yozing, masalan:\n"
        "<code>query:key</code> — URL parametri\n"
        "<code>header:X-Shop-Key</code> — header\n"
        "<code>bearer</code> — Authorization: Bearer"
    )


def _extract_items(payload) -> list[dict]:
    """Javobdan tovarlar ro'yxatini ajratadi."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise CatalogError("Kutilmagan JSON formati")

    if payload.get("success") is False:
        raise CatalogError(f"API xato qaytardi: {payload.get('message') or payload}")

    if "status" in payload:
        status = str(payload.get("status")).lower()
        if status not in ("success", "ok", "200", "true"):
            raise CatalogError(f"API status: {payload.get('status')}")

    for field in ("data", "products", "items", "results"):
        data = payload.get(field)
        if isinstance(data, list):
            return data
        # Ba'zi CRM lar {"data": {"items": [...]}} shaklida beradi
        if isinstance(data, dict):
            for inner in ("data", "products", "items", "results"):
                nested = data.get(inner)
                if isinstance(nested, list):
                    return nested

    raise CatalogError(
        "Javobda tovarlar ro'yxati topilmadi.\n"
        f"Mavjud maydonlar: <code>{', '.join(list(payload.keys())[:10])}</code>"
    )


# ─────────────────────────── Narx ───────────────────────────

def sell_price(supplier_price: int) -> int:
    """Ta'minotchi narxidan sotuv narxini hisoblaydi."""
    price = supplier_price * (1 + settings.catalog_markup_percent / 100)
    step = settings.catalog_round_to
    if step > 1:
        price = round(price / step) * step
    price = int(price)
    # Marja manfiy bo'lib qolmasin
    return max(price, supplier_price)


# ─────────────────────────── Tahlil ───────────────────────────

def _parse_item(raw: dict) -> dict:
    """Bitta tovarni tekshiradi va normallashtiradi. Xato bo'lsa ValueError."""
    if not isinstance(raw, dict):
        raise ValueError("tovar obyekt emas")

    ext_id = str(raw.get("external_id") or raw.get("id") or "").strip()
    if not ext_id:
        raise ValueError("external_id yo'q")

    title = str(raw.get("title") or raw.get("name") or "").strip()
    if not title:
        raise ValueError(f"{ext_id}: nomi yo'q")

    try:
        price = int(float(raw.get("price")))
    except (TypeError, ValueError):
        raise ValueError(f"{ext_id}: narx noto'g'ri") from None
    if price <= 0:
        raise ValueError(f"{ext_id}: narx noldan katta bo'lishi kerak")

    try:
        stock = int(raw.get("stock", 0) or 0)
    except (TypeError, ValueError):
        stock = 0

    image = str(raw.get("image_url") or "").strip() or None
    if image and not image.startswith(("http://", "https://")):
        image = None

    return {
        "external_id": ext_id[:128],
        "title": title[:255],
        "price": price,
        "stock": max(stock, 0),
        "category": str(raw.get("category") or DEFAULT_CATEGORY).strip()[:128],
        "image_url": image[:1024] if image else None,
        "description": str(raw.get("description") or "").strip(),
    }


# ─────────────────────────── Kategoriya ───────────────────────────

async def _get_or_create_category(
    s: AsyncSession, name: str, cache: dict[str, Category]
) -> Category:
    key = name.casefold()
    if key in cache:
        return cache[key]

    cat = await s.scalar(select(Category).where(Category.name_uz.ilike(name)))
    if not cat:
        cat = Category(emoji=DEFAULT_EMOJI, name_uz=name, sort_order=200)
        s.add(cat)
        await s.flush()
        log.info("Yangi kategoriya: %s", name)
    cache[key] = cat
    return cat


# ─────────────────────────── Asosiy ───────────────────────────

_sync_lock = asyncio.Lock()    # qo'lda /sync va avtomatik sinxronlash bir vaqtda ishlamasin


async def sync_catalog(s: AsyncSession, items: list[dict] | None = None, auto: bool = False) -> SyncResult:
    """Katalogni tortib olib, bazaga yozadi. CANBOSO_API_KEY bo'lsa — canboso'dan.

    auto=True — fon sinxronlashi: mahsulot ro'yxatdan bir marta tushib qolsa darhol yashirilmaydi
    (mijozlar «yo'qolib, qaytib chiqqan» mahsulotni ko'rmasin).
    """
    async with _sync_lock:
        STATUS["last_try"] = datetime.utcnow()
        try:
            res = await _sync_catalog(s, items, auto)
        except Exception as ex:  # noqa: BLE001 — holat yoziladi, xato chaqiruvchiga qaytadi
            STATUS["last_error"] = str(ex)[:300] or type(ex).__name__
            raise
        STATUS["last_ok"] = datetime.utcnow()
        STATUS["last_error"] = "; ".join(res.errors[:2])[:300] if not res.total_seen and res.errors else ""
        STATUS["seen"] = res.total_seen
        return res


# Admin bosh sahifasi uchun: katalog oxirgi marta qachon yangilandi va xato bo'ldimi
STATUS: dict = {"last_try": None, "last_ok": None, "last_error": "", "seen": 0}


async def _sync_catalog(s: AsyncSession, items: list[dict] | None, auto: bool) -> SyncResult:
    if settings.canboso_api_key and items is None:
        from services import canboso
        try:
            result = await canboso.sync(s, auto=auto)
        except canboso.SupplierError as ex:
            raise CatalogError(str(ex)) from ex
        bal = await canboso.fetch_balance()
        if bal is not None:
            result.note = f"💳 Ta'minotchi hamyoni: <b>${bal:,.2f}</b>"
        return result
    result = SyncResult()

    if items is None:
        items = await fetch_catalog()

    if not items:
        result.errors.append("API bo'sh ro'yxat qaytardi — hech narsa o'zgartirilmadi")
        return result

    # Mavjud API tovarlari
    existing: dict[str, Product] = {
        p.external_id: p
        for p in await s.scalars(
            select(Product).where(Product.source == ProductSource.API)
        )
        if p.external_id
    }

    cat_cache: dict[str, Category] = {}
    seen: set[str] = set()
    now = datetime.utcnow()

    for raw in items:
        try:
            item = _parse_item(raw)
        except ValueError as ex:
            result.skipped += 1
            result.errors.append(str(ex))
            continue

        ext_id = item["external_id"]
        if ext_id in seen:
            result.skipped += 1
            result.errors.append(f"{ext_id}: feedda takrorlangan")
            continue
        seen.add(ext_id)

        category = await _get_or_create_category(s, item["category"], cat_cache)
        price = sell_price(item["price"])
        product = existing.get(ext_id)

        if product is None:
            s.add(Product(
                category_id=category.id,
                emoji=DEFAULT_EMOJI,
                name=item["title"],
                description=item["description"],
                price=price,
                supplier_price=item["price"],
                stock_qty=item["stock"],
                image_url=item["image_url"],
                delivery_type=DeliveryType.MANUAL,
                unlimited=False,
                source=ProductSource.API,
                external_id=ext_id,
                is_active=item["stock"] > 0,
                synced_at=now,
            ))
            result.created += 1
            continue

        changed = False
        locked_fields = overrides.locked(product)
        for attr, value in (
            ("name", item["title"]),
            ("description", item["description"]),
            ("price", price),
            ("supplier_price", item["price"]),
            ("stock_qty", item["stock"]),
            ("image_url", item["image_url"]),
            ("category_id", category.id),
            ("is_active", item["stock"] > 0),
        ):
            if attr == "image_url" and "image" in locked_fields:
                continue                     # admin o'zi rasm yuklagan — ta'minotchi rasmi bilan almashtirilmaydi
            if getattr(product, attr) != value:
                setattr(product, attr, value)
                changed = True

        product.synced_at = now
        if changed:
            result.updated += 1
        else:
            result.unchanged += 1

    # Feedda yo'q bo'lib qolganlar
    if settings.catalog_deactivate_missing:
        for ext_id, product in existing.items():
            if ext_id not in seen and product.is_active:
                product.is_active = False
                product.stock_qty = 0
                result.deactivated += 1

    await s.commit()
    log.info(
        "Katalog: +%d ~%d =%d -%d (tashlandi %d)",
        result.created, result.updated, result.unchanged,
        result.deactivated, result.skipped,
    )
    return result


DEFAULT_SYNC_MINUTES = 3        # canboso: narx va zaxira tez o'zgaradi
ALERT_AFTER_FAILS = 5           # ketma-ket shuncha xatodan keyin adminga bir marta xabar (mijozga emas)
MAX_BACKOFF_SECONDS = 15 * 60


def sync_interval_seconds() -> int:
    """Avtomatik sinxronlash oralig'i (soniya). 0 — o'chiq."""
    m = settings.catalog_sync_minutes
    if m == 0 or not settings.catalog_enabled:
        return 0
    if m < 0:
        m = DEFAULT_SYNC_MINUTES if settings.canboso_api_key else 60
    return max(m, 1) * 60


async def _notify_admins(bot, text: str) -> None:
    if bot is None:
        return
    for admin_id in settings.admins:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001 — admin botni bloklagan bo'lishi mumkin
            pass


async def periodic_sync(bot=None) -> None:
    """Fonda ishlaydigan avtomatik sinxronizatsiya.

    Mijozlarga hech narsa ko'rinmaydi: xabar yo'q, ro'yxat miltillamaydi. Xato bo'lsa kutish
    vaqti oshadi (ta'minotchini bezovta qilmaymiz), ketma-ket xatolarda faqat ADMINGA xabar boradi.
    """
    from database.db import SessionMaker

    interval = sync_interval_seconds()
    if not interval:
        return

    log.info("Katalog avtomatik yangilanadi: har %d soniyada", interval)
    await asyncio.sleep(20)   # ishga tushgach bir marta darrov — do'kon bo'sh turmasin
    fails, alerted = 0, False
    while True:
        delay = interval
        try:
            async with SessionMaker() as session:
                res = await sync_catalog(session, auto=True)
            if alerted:
                await _notify_admins(bot, "✅ Katalog yangilanishi qayta tiklandi.")
            fails, alerted = 0, False
            if res.created or res.deactivated:
                log.info("Katalog: +%d yangi, -%d yashirildi", res.created, res.deactivated)
            if res.price_changes and bot is not None:
                from services.announce import alert_price_changes
                asyncio.create_task(alert_price_changes(bot, res.price_changes))
            if res.events and bot is not None:
                # xabar yuborish sinxronlashni kutdirmasin va uning xatosi sinxronlashni buzmasin
                from services.announce import announce_events
                asyncio.create_task(announce_events(bot, res.events))
        except Exception as ex:  # noqa: BLE001
            fails += 1
            if isinstance(ex, CatalogError):
                log.warning("Katalog yangilanmadi (%d): %s", fails, ex)
            else:
                log.exception("Katalog sinxronizatsiyasida kutilmagan xato (%d)", fails)
            delay = min(interval * 2 ** min(fails, 4), MAX_BACKOFF_SECONDS)   # 3 → 6 → 12 → 15 daqiqa
            if fails >= ALERT_AFTER_FAILS and not alerted:
                alerted = True
                await _notify_admins(
                    bot,
                    f"⚠️ Katalog {fails} marta ketma-ket yangilanmadi: {ex}\n"
                    "Mijozlar vaqtincha eski narx va zaxirani ko'radi. Muammo bartaraf bo'lganda xabar beraman.",
                )
        await asyncio.sleep(delay + random.uniform(0, 10))
