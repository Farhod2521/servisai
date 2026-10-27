"""Buyurtma berish mantig‘i: sayt API, Telegram bot va sovg‘alar shu yerdan foydalanadi.

Commit va xabarnomalar chaqiruvchi tomonda qilinadi.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DeliveryItem, Order, OrderEvent, OrderStatus, Product, TransactionType, User
from .notify import format_price
from .stock import take
from .wallet import InsufficientFunds, change_balance


class ShopError(Exception):
    """Mijozga ko‘rsatiladigan xato. `status` — HTTP kodi (API uchun)."""

    def __init__(self, status: int, message: str, *, need_topup: bool = False):
        super().__init__(message)
        self.status = status
        self.message = message
        # Balans yetmagan — "Hisobni to‘ldirish" taklif qilinadi
        self.need_topup = need_topup


async def place_order(
    session: AsyncSession,
    user: User,
    product: Product,
    *,
    quantity: int = 1,
    duration: int | None = None,
    comment: str | None = None,
    gift_note: str | None = None,
) -> Order:
    """Buyurtma yaratadi va to‘lovni hisobdan yechadi.

    `gift_note` berilsa — sovg‘a: pul yechilmaydi, mahsulot tugagan bo‘lsa ham buyurtma yaratiladi
    (keyin admin qo‘lda yetkazadi). Xato bo‘lsa ShopError; sessiya rollback qilingan bo‘ladi.
    """
    gift = gift_note is not None
    if not product.is_active and not gift:
        raise ShopError(404, "Mahsulot topilmadi")
    duration = duration or product.durations[0]
    if duration not in product.durations:
        raise ShopError(422, "Bu muddat mavjud emas")

    in_stock = await take(session, product, quantity)
    if not in_stock and not gift:
        await session.refresh(product)  # boshqa xarid shu orada sonni o‘zgartirgan bo‘lishi mumkin
        if not product.stock:
            raise ShopError(409, "Afsuski, bu servis hozircha tugagan")
        raise ShopError(409, f"Bazada faqat {product.stock} ta bor. Sonini {product.stock} tagacha kamaytiring")

    # Avtomatik mahsulot: har bir dona uchun ro‘yxatdan alohida (hali berilmagan) element olinadi
    items: list[DeliveryItem] = []
    if product.instant_delivery and in_stock:
        items = list(
            (
                await session.scalars(
                    select(DeliveryItem)
                    .where(DeliveryItem.product_id == product.id, DeliveryItem.order_id.is_(None))
                    .order_by(DeliveryItem.id)
                    .limit(quantity)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if len(items) < quantity:
            if not gift:
                await session.rollback()
                raise ShopError(409, f"Bazada faqat {len(items)} ta bor. Sonini {len(items)} tagacha kamaytiring")
            items = []  # sovg‘a: admin qo‘lda yetkazadi
    instant = bool(items)

    total = 0 if gift else product.price * quantity
    paid_note = gift_note if gift else "Hisobdan to‘landi"
    order = Order(
        user_id=user.id,
        product_id=product.id,
        product_name=product.name,
        duration_months=duration,
        quantity=quantity,
        price=total,
        comment=comment or gift_note,
        status=OrderStatus.completed if instant else OrderStatus.paid,
        delivery_info="\n".join(i.content for i in items) if instant else None,
        paid_from_balance=not gift,
        events=[
            OrderEvent(status=OrderStatus.pending, note="Buyurtma yaratildi" + (f" ({quantity} ta)" if quantity > 1 else "")),
            OrderEvent(status=OrderStatus.paid, note=paid_note),
            *([OrderEvent(status=OrderStatus.completed, note="Avtomatik yetkazib berildi")] if instant else []),
        ],
    )
    session.add(order)
    await session.flush()
    now = datetime.now(timezone.utc)
    for item in items:
        item.order_id, item.user_id, item.delivered_at = order.id, user.id, now

    if not gift:
        try:
            await change_balance(
                session,
                user.id,
                -total,
                TransactionType.purchase,
                note=f"{product.name} xaridi" + (f" × {quantity}" if quantity > 1 else ""),
                order_id=order.id,
            )
        except InsufficientFunds as e:
            await session.rollback()
            raise ShopError(
                402,
                f"Hisobingizda mablag‘ yetarli emas. Balans: {format_price(e.balance)} so‘m, kerak: {format_price(total)} so‘m",
                need_topup=True,
            )
    return order
