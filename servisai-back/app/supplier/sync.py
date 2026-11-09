"""Ta’minotchi katalogini saytga yozish (har SUPPLIER_SYNC_SECONDS da fonda).

Taqiqlanmagan HAMMA mahsulotlar qo‘shiladi: avval botdagi asosiy brendlar (client.BASE_BRANDS), keyin qolganlari. Har sinxronlashda nom, tavsif,
narx (Markaziy bank kursi + botdagi «aqlli narx») va soni yangilanadi. Admin o‘zgartirgan faollik (yashirish),
tartib, belgi va yuklagan logo saqlanib qoladi. Ro‘yxatdan chiqib ketgan mahsulot o‘chirilmaydi — yashiriladi.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import SessionLocal
from ..logos import media_dir
from ..models import Product
from . import client
from .catalog import is_api, parse_item

log = logging.getLogger("servisai.supplier")

# Bot kategoriyasi → sayt katalogi filtri
CATEGORY = {"ai": "chat", "ai_dev": "code", "media_ai": "design", "voice_ai": "design", "design": "design", "office": "office"}
# Ro‘yxat oldingi faol mahsulotlarning shu ulushidan kam bo‘lsa — javob gumonli, hech narsa yashirilmaydi
SUSPICIOUS_RATIO = 0.5
_DURATION = re.compile(r"(\d+)\s*(soat|kun|hafta|oy|yil)", re.I)


last_result: "SyncResult | None" = None
last_sync_at: datetime | None = None


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    hidden: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def duration_of(name: str) -> tuple[int, str]:
    """«ChatGPT Plus 1 oy» → (1, "month"); «… 7 kun» → (7, "day"); muddatsiz (kredit, kalit) → (1, "item")."""
    m = _DURATION.search(name or "")
    if not m:
        return 1, "item"
    n, unit = int(m.group(1)), m.group(2).lower()
    return {
        "oy": (n, "month"),
        "yil": (n * 12, "month"),
        "kun": (n, "day"),
        "hafta": (n * 7, "day"),
        "soat": (max(1, round(n / 24)), "day"),
    }[unit]


def brand_order(brand: str) -> int:
    """Botdagi asosiy brendlar oldinda (o‘sha tartibda), qolganlari ulardan keyin; o‘zimizning mahsulotlar (0…) eng oldinda."""
    if brand in client.BASE_BRANDS:
        return 1000 + client.BASE_BRANDS.index(brand) * 10
    return 2000


def product_id(external_id: str) -> str:
    """"cb:Ab_12" → "cb-ab-12" (sahifa manzili uchun)."""
    return "cb-" + re.sub(r"[^a-z0-9]+", "-", external_id.removeprefix("cb:").lower()).strip("-")[:56]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "brand"


async def brand_logo(brand: str, domain: str) -> str | None:
    """Brend logotipi (sayt ikonkasi) bir marta yuklab olinib media/logos da saqlanadi."""
    if not domain:
        return None
    name = f"brand-{_slug(brand)}.png"
    path = media_dir("logos") / name
    if not path.exists():
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as http:
                resp = await http.get("https://www.google.com/s2/favicons", params={"domain": domain, "sz": 128})
            if resp.status_code != 200 or not resp.content.startswith(b"\x89PNG"):
                return None
            path.write_bytes(resp.content)
        except httpx.HTTPError:
            return None
    return f"/api/media/logos/{name}"


async def sync(session: AsyncSession) -> SyncResult:
    result = SyncResult()
    items = await client.fetch_products()
    if not items:
        result.errors.append("Ta’minotchi bo‘sh ro‘yxat qaytardi — hech narsa o‘zgartirilmadi")
        return result
    rate = await client.usd_rate()

    existing = {p.external_id: p for p in await session.scalars(select(Product).where(Product.source == "canboso"))}
    logos: dict[str, str | None] = {}
    seen: set[str] = set()

    for raw in items:
        try:
            it = parse_item(raw)
        except ValueError as ex:
            result.skipped += 1
            result.errors.append(str(ex))
            continue
        if it["blocked"] or it["external_id"] in seen:
            result.skipped += 1
            continue
        seen.add(it["external_id"])

        cost, price = client.sell_price_uzs(it["usd"], rate, it["name"], it["brand"], it["warranty"])
        n, unit = duration_of(it["clean"])
        if it["brand"] not in logos:
            logos[it["brand"]] = await brand_logo(it["brand"], it["logo"])
        ready = it["type"] == "account" and not it["need"]
        fields = {
            "name": it["title"][:255],
            "description": it["description"].split("\n")[0],
            "features": [line for line in it["description"].split("\n") if line],
            "price": price,
            "supplier_price": cost,
            "stock": it["available"],
            "brand": it["brand"],
            "category": CATEGORY.get(it["category"], "other"),
            "durations": [n],
            "duration_unit": unit,
            "delivery_time": "Darhol, avtomatik" if ready else "10 daqiqa – 24 soat",
            "supplier_meta": {
                "need": it["need"], "fixed_qty": it["fixed_qty"], "usd": it["usd"], "warranty": it["warranty"],
                "type": it["type"], "raw": it["name_en"],
            },
        }
        product = existing.get(it["external_id"])
        if product is None:
            session.add(
                Product(
                    id=product_id(it["external_id"]),
                    external_id=it["external_id"],
                    source="canboso",
                    delivery_mode="supplier",
                    is_active=True,
                    badge="api" if is_api(it["brand"], it["name_en"]) else None,
                    # Brendlar tartibi botdagidek; o‘zimiz qo‘shgan mahsulotlar (0…) oldinda turadi
                    sort_order=brand_order(it["brand"]),
                    logo_url=logos[it["brand"]],
                    old_price=None,
                    sold_base=0,
                    notes="",
                    **fields,
                )
            )
            result.created += 1
            continue
        if product.supplier_meta.get("gone"):
            product.is_active = True  # ro‘yxatga qaytdi
        if not product.logo_url:
            product.logo_url = logos[it["brand"]]
        changed = False
        for attr, value in fields.items():
            if getattr(product, attr) != value:
                setattr(product, attr, value)
                changed = True
        result.updated += changed

    # Ro‘yxatdan chiqqanlar yashiriladi (buyurtmalar tarixi saqlanishi uchun o‘chirilmaydi)
    active = [p for p in existing.values() if p.is_active]
    gone = [p for p in active if p.external_id not in seen]
    if len(active) >= 10 and len(seen) < SUSPICIOUS_RATIO * len(active):
        result.errors.append(f"Ta’minotchi ro‘yxati gumonli darajada qisqa ({len(seen)} / {len(active)}) — hech narsa yashirilmadi")
        gone = []
    for p in gone:
        p.is_active = False
        p.stock = 0
        p.supplier_meta = {**p.supplier_meta, "gone": True}
        result.hidden += 1

    await session.commit()
    global last_result, last_sync_at
    last_result, last_sync_at = result, datetime.now(timezone.utc)
    log.info("Ta’minotchi: +%d ~%d -%d (o‘tkazildi %d), kurs %.2f", result.created, result.updated, result.hidden, result.skipped, rate)
    return result


async def run_forever(interval: int) -> None:
    """Backend ishlab turganda katalogni muntazam yangilaydi (xato bo‘lsa keyingi safar qayta urinadi)."""
    while True:
        try:
            async with SessionLocal() as session:
                await sync(session)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Ta’minotchi katalogini yangilab bo‘lmadi")
        await asyncio.sleep(interval)
