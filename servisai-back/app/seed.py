"""Boshlang‘ich katalogni (mahsulotlar va sovg‘a qoidalari) bazaga qo‘shadi.

Ma’lumot `seed_catalog.json` dan olinadi (lokal bazadan eksport qilingan; shaxsiy ma’lumotlarsiz).
Mavjud mahsulotlarga tegilmaydi: ular admin paneldan tahrirlanadi va har restartda qayta yozilib ketmasligi kerak.
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .database import SessionLocal, engine
from .models import Product, ReferralReward

CATALOG = Path(__file__).with_name("seed_catalog.json")


async def main() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    async with SessionLocal() as session:
        added = 0
        for product in data["products"]:
            values = dict(product)
            # Avtomatik mahsulotning havolalari (maxfiy) faylga kirmaydi — soni ular qo‘shilganda o‘sadi
            if values.get("delivery_mode") == "auto":
                values["stock"] = 0
            stmt = insert(Product).values(**values).on_conflict_do_nothing(index_elements=[Product.id])
            added += (await session.execute(stmt)).rowcount

        rewards = 0
        for reward in data.get("rewards", []):
            exists = await session.scalar(
                select(ReferralReward.id).where(
                    ReferralReward.product_id == reward["product_id"],
                    ReferralReward.required_friends == reward["required_friends"],
                )
            )
            product_exists = await session.scalar(select(Product.id).where(Product.id == reward["product_id"]))
            if exists is None and product_exists is not None:
                session.add(ReferralReward(**reward))
                rewards += 1
        await session.commit()
    await engine.dispose()
    print(f"Seed: {added} ta yangi mahsulot, {rewards} ta yangi sovg‘a qo‘shildi")


if __name__ == "__main__":
    asyncio.run(main())
