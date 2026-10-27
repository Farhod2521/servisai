"""Mahsulot soni (ombor) va sotilganlar hisobi."""

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DeliveryItem, Order, OrderStatus, Product

# Sotilgan deb hisoblanadigan buyurtmalar (bekor qilinganlari pul va soni qaytarilgani uchun kirmaydi)
SOLD_STATUSES = (OrderStatus.paid, OrderStatus.processing, OrderStatus.completed)


async def attach_sold_counts(session: AsyncSession, products: Sequence[Product]) -> Sequence[Product]:
    ids = [p.id for p in products]
    if ids:
        rows = await session.execute(
            select(Order.product_id, func.sum(Order.quantity))
            .where(Order.product_id.in_(ids), Order.status.in_(SOLD_STATUSES))
            .group_by(Order.product_id)
        )
        counts = dict(rows.all())
        for p in products:
            p.sold_count = counts.get(p.id, 0)
    return products


async def take(session: AsyncSession, product: Product, quantity: int) -> bool:
    """Sotuv uchun `quantity` tasini ayiradi. Yetmasa False (bir vaqtdagi xaridlarda ham manfiyga tushmaydi)."""
    if product.stock is None:
        return True
    taken = await session.execute(
        update(Product)
        .where(Product.id == product.id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
        .returning(Product.id)
    )
    return taken.first() is not None


async def give_back(session: AsyncSession, product_id: str | None, quantity: int) -> None:
    """Bekor qilingan buyurtma sonini qaytaradi (cheklanmagan mahsulotga tegilmaydi)."""
    if product_id is not None:
        await session.execute(
            update(Product).where(Product.id == product_id, Product.stock.is_not(None)).values(stock=Product.stock + quantity)
        )


async def sync_pool_stock(session: AsyncSession, product: Product) -> None:
    """Avtomatik mahsulotda soni = hali berilmagan elementlar soni."""
    if product.delivery_mode == "auto":
        product.stock = await session.scalar(
            select(func.count(DeliveryItem.id)).where(DeliveryItem.product_id == product.id, DeliveryItem.order_id.is_(None))
        )


async def was_auto_delivered(session: AsyncSession, order_id: int) -> bool:
    """Buyurtmaga element berilganmi (bekor qilinsa ham u ro‘yxatga qaytarilmaydi — mijoz uni ko‘rgan)."""
    return bool(await session.scalar(select(func.count(DeliveryItem.id)).where(DeliveryItem.order_id == order_id)))
