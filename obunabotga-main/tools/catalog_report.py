"""Ta'minotchi katalogidan HISOBOT yaratadi (API kalit hisobotga YOZILMAYDI).

Nima uchun: nomlar o'zbekchaga to'g'ri o'girilganini, narx/kafolat/qo'llanma mosligini va API javobidagi
qo'shimcha maydonlar (tavsif, ko'rsatma) bor-yo'qligini tekshirish uchun.

Ishga tushirish (CANBOSO_API_KEY muhit o'zgaruvchisi bo'lishi shart):
    python tools/catalog_report.py            # catalog_report.md yaratadi
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BOT_TOKEN", "123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from services import canboso, guides  # noqa: E402
from database.models import Product, ProductSource  # noqa: E402


def _cut(v, n=300):
    t = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return t if len(t) <= n else t[:n] + "…"


async def main() -> None:
    if not os.getenv("CANBOSO_API_KEY"):
        raise SystemExit("CANBOSO_API_KEY o'rnatilmagan")
    items = await canboso.fetch_products()
    try:
        rate = await canboso.usd_rate()
    except Exception:
        rate = float(os.getenv("USD_TO_UZS", "12000"))

    keys: Counter = Counter()
    for it in items:
        keys.update(it.keys())

    Path(ROOT / "catalog_raw.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")   # kalitsiz, to'liq xom ro'yxat
    out = [f"# Katalog hisoboti\n\nMahsulotlar: {len(items)} · USD kursi: {rate:.0f}\n"]
    out.append("## API javobidagi maydonlar (nechta mahsulotda bor)\n")
    out += [f"- `{k}`: {n}" for k, n in keys.most_common()]
    extra = [k for k in keys if k not in ("productId", "name", "price", "availability", "productType", "purchaseRequirements", "emoji")]
    out.append("\n## Qo'shimcha maydonlar namunasi (tavsif/ko'rsatma bo'lishi mumkin)\n")
    for k in extra:
        vals = [it[k] for it in items if it.get(k)][:3]
        out.append(f"- `{k}`: " + " | ".join(_cut(v) for v in vals))
    out.append("\n## To'liq 6 ta xom mahsulot (turli turdan)\n")
    seen, shown = set(), 0
    for it in items:
        t = it.get("productType")
        if t in seen and shown >= 3:
            continue
        seen.add(t)
        out.append("```json\n" + json.dumps(it, ensure_ascii=False, indent=1)[:1500] + "\n```")
        shown += 1
        if shown >= 6:
            break

    out.append("\n## Hamma mahsulot: xom nom → botdagi nom | brend | kafolat | narx | yashirinmi\n")
    out.append("| xom nom | botdagi nom | brend | kafolat | tur | asl $ | sotuv so'm | yashirin |\n|---|---|---|---|---|---|---|---|")
    brands: Counter = Counter()
    for raw in items:
        try:
            it = canboso.parse_item(raw)
        except ValueError as ex:
            out.append(f"| {raw.get('name')} | ❌ {ex} | | | | | | |")
            continue
        _, price = canboso.sell_price_uzs(it["usd"], rate, it["name"], it["brand"], it["warranty"])
        brands[it["brand"] or "—"] += 1
        out.append(f"| {raw.get('name')} | {it['name']} | {it['brand'] or '—'} | {it['warranty'] or '—'} | {it['type']} | {it['usd']} | {price} | {'ha' if it['blocked'] else ''} |")

    out.append("\n## Uzoq muddatli obunalar (6 oydan ko'p) va ularning kafolati\n")
    out.append("| botdagi nom | kafolat (aniqlangan) | xom nom | xom maydonlardagi «warrant/guarant/kafolat» matnlari |\n|---|---|---|---|")
    import re as _re
    for raw in items:
        try:
            it = canboso.parse_item(raw)
        except ValueError:
            continue
        mo = canboso.duration_days(it["name"])
        if it["blocked"] or not mo or mo < 180:
            continue
        hints = [f"{k}: {_cut(v, 160)}" for k, v in raw.items() if isinstance(v, str) and k != "name" and _re.search(r"warrant|guarant|kafolat", v, _re.I)]
        out.append(f"| {it['name']} | {it['warranty'] or '— (aniqlanmadi)'} | {raw.get('name')} | {'; '.join(hints)} |")

    out.append("\n## Brendlar\n")
    out.append(", ".join(f"{b} ({n})" for b, n in brands.most_common()))

    out.append("\n## Qo'llanma namunalari (har bir brenddan bittadan)\n")
    done = set()
    for raw in items:
        try:
            it = canboso.parse_item(raw)
        except ValueError:
            continue
        if it["blocked"] or it["brand"] in done:
            continue
        done.add(it["brand"])
        p = Product(name=it["name"], brand=it["brand"], logo=it["logo"], source=ProductSource.API, external_id=it["external_id"],
                    price=1, supplier_data=json.dumps({"type": it["type"], "warranty": it["warranty"]}))
        out.append(f"### {it['name']}\n```\n{guides.default_guide(p)}\n```")
        if len(done) >= 25:
            break

    Path(ROOT / "catalog_report.md").write_text("\n".join(out), encoding="utf-8")
    print(f"✅ catalog_report.md yaratildi ({len(items)} mahsulot)")


if __name__ == "__main__":
    asyncio.run(main())
