"""Frontend katalogidagi mahsulotlarni bazaga yozadi (mavjud bo‘lsa yangilaydi)."""

import asyncio

from sqlalchemy.dialects.postgresql import insert

from .database import SessionLocal, engine
from .models import Product

PRODUCTS = [
    {
        "id": "chatgpt-plus",
        "name": "ChatGPT Plus",
        "description": "GPT-4, DALL-E, Advanced Data Analysis va yana ko‘p imkoniyatlar",
        "price": 129000,
        "old_price": None,
        "durations": [1],
    },
    {
        "id": "gemini-advanced",
        "name": "Gemini Advanced",
        "description": "Google’ning eng yangi AI modeli, 1.5 Pro, 2TB gacha imkoniyatlar",
        "price": 129000,
        "old_price": None,
        "durations": [18],
    },
    {
        "id": "capcut-pro",
        "name": "CapCut Pro",
        "description": "Premium shablonlar, AI video, tafsirlar, barcha funksiyalar",
        "price": 69000,
        "old_price": None,
        "durations": [1],
    },
]


async def main() -> None:
    async with SessionLocal() as session:
        for data in PRODUCTS:
            stmt = insert(Product).values(**data)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Product.id],
                set_={k: stmt.excluded[k] for k in data if k != "id"},
            )
            await session.execute(stmt)
        await session.commit()
    await engine.dispose()
    print(f"Seed: {len(PRODUCTS)} ta mahsulot")


if __name__ == "__main__":
    asyncio.run(main())
