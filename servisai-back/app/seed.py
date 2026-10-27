"""Boshlang‘ich mahsulotlarni bazaga qo‘shadi.

Mavjud mahsulotlarga tegilmaydi: ular admin paneldan tahrirlanadi va har restartda
qayta yozilib ketmasligi kerak.
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert

from .database import SessionLocal, engine
from .models import Product

PRODUCTS = [
    {
        "id": "chatgpt-plus",
        "name": "ChatGPT Plus",
        "description": "GPT-4, DALL-E, Advanced Data Analysis va yana ko‘p imkoniyatlar",
        "price": 200000,
        "old_price": None,
        "durations": [1],
        "category": "chat",
        "badge": "popular",
        "features": [
            "GPT-4o va eng yangi OpenAI modellariga kirish",
            "DALL-E bilan rasm yaratish",
            "Advanced Data Analysis — fayl va jadvallarni tahlil qilish",
            "Custom GPT’lar yaratish va ishlatish",
            "Ovozli suhbat rejimi",
            "Bepul versiyaga nisbatan yuqori limitlar",
        ],
        "sort_order": 1,
    },
    {
        "id": "gemini-advanced",
        "name": "Gemini Advanced",
        "description": "Google’ning eng yangi AI modeli, 1.5 Pro, 2TB gacha imkoniyatlar",
        "price": 35000,
        "old_price": None,
        "durations": [18],
        "category": "chat",
        "badge": "new",
        "features": [
            "Gemini 1.5 Pro — Google’ning eng kuchli modeli",
            "1 million tokengacha kontekst",
            "2TB Google One bulutli xotirasi",
            "Gmail, Docs va Sheets ichida Gemini",
            "Uzun hujjat va kodlarni tahlil qilish",
            "18 oy davomida to‘liq imkoniyatlar",
        ],
        "sort_order": 3,
    },
    {
        "id": "capcut-pro",
        "name": "CapCut Pro",
        "description": "Premium shablonlar, AI video, tafsirlar, barcha funksiyalar",
        "price": 40000,
        "old_price": None,
        "durations": [1],
        "category": "design",
        "badge": "popular",
        "features": [
            "Barcha Pro shablon va effektlar",
            "AI video tahrirlash vositalari",
            "Suv belgisisiz eksport",
            "4K sifatda eksport",
            "Avtomatik subtitrlar",
            "Bulutli xotira",
        ],
        "sort_order": 2,
    },
]


async def main() -> None:
    async with SessionLocal() as session:
        added = 0
        for data in PRODUCTS:
            stmt = insert(Product).values(**data).on_conflict_do_nothing(index_elements=[Product.id])
            added += (await session.execute(stmt)).rowcount
        await session.commit()
    await engine.dispose()
    print(f"Seed: {added} ta yangi mahsulot qo‘shildi")


if __name__ == "__main__":
    asyncio.run(main())
