"""Namuna ma'lumot: RENAX AI obuna tariflari.

Ishga tushirish: python seed.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from database.db import SessionMaker, init_db
from database.models import Category, DeliveryType, Product


async def main() -> None:
    await init_db()
    async with SessionMaker() as s:
        if await s.scalar(select(Category).limit(1)):
            print("Baza allaqachon to'ldirilgan.")
            return

        cat = Category(emoji="🤖", name_uz="RENAX AI obunalar",
                       name_ru="Подписки RENAX AI", name_en="RENAX AI plans",
                       sort_order=10)
        s.add(cat)
        await s.flush()

        plans = [
            ("🥉", "Bronza — 1 oy", "Kuniga 50 ta AI so'rov\nMatn generatsiyasi\nO'zbek tilida to'liq qo'llab-quvvatlash", 19_000),
            ("🥈", "Silver — 1 oy", "Kuniga 300 ta AI so'rov\nMatn + rasm generatsiyasi\nTezkor javob navbati", 49_000),
            ("💎", "VIP — 1 oy", "Cheksiz AI so'rovlar\nMatn + rasm + video\nEng kuchli modellar\n24/7 qo'llab-quvvatlash", 99_000),
        ]
        for emoji, name, desc, price in plans:
            s.add(Product(
                category_id=cat.id, emoji=emoji, name=name, description=desc,
                price=price, delivery_type=DeliveryType.MANUAL, unlimited=True,
            ))
        await s.commit()
        print("✅ Namuna ma'lumot qo'shildi.")


if __name__ == "__main__":
    asyncio.run(main())
