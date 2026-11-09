"""Buyurtma berish mantig‘i: sayt API, Telegram bot va sovg‘alar shu yerdan foydalanadi.

Commit va xabarnomalar chaqiruvchi tomonda qilinadi.
"""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DeliveryItem, Order, OrderEvent, OrderStatus, Product, TransactionType, User
from .notify import format_price
from .stock import take
from .wallet import InsufficientFunds, change_balance


_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


class ShopError(Exception):
    """Mijozga ko‘rsatiladigan xato. `status` — HTTP kodi (API uchun)."""

    def __init__(self, status: int, message: str, *, need_topup: bool = False):
        super().__init__(message)
        self.status = status
        self.message = message
        # Balans yetmagan — "Hisobni to‘ldirish" taklif qilinadi
        self.need_topup = need_topup


def clean_customer_input(product: Product, quantity: int, value: str | None) -> str | None:
    """Ta’minotchi mahsuloti talab qilgan email/akkauntlarni tekshiradi (ServesAI botidagi qoidalar)."""
    fixed = product.fixed_quantity
    if fixed and quantity != fixed:
        raise ShopError(422, f"Bu mahsulotdan bir martada faqat {fixed} ta olish mumkin")
    need = product.needs_input
    if need == "email":
        email = (value or "").strip()
        if not _EMAIL.match(email):
            raise ShopError(422, "Obuna biriktiriladigan to‘g‘ri email manzilni kiriting")
        return email
    if need == "accounts":
        rows = [r.strip() for r in (value or "").splitlines() if r.strip()]
        if len(rows) != quantity:
            raise ShopError(422, f"{quantity} ta akkaunt ma’lumotini kiriting (har qatorga bittadan)")
        if any(len(r) < 3 or len(r) > 200 for r in rows):
            raise ShopError(422, "Akkaunt ma’lumoti noto‘g‘ri")
        return "\n".join(rows)
    return None


async def place_order(
    session: AsyncSession,
    user: User,
    product: Product,
    *,
    quantity: int = 1,
    duration: int | None = None,
    comment: str | None = None,
    gift_note: str | None = None,
    customer_input: str | None = None,
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
    customer_input = clean_customer_input(product, quantity, customer_input) if not gift else None

    in_stock = await take(session, product, quantity)
    if not in_stock and not gift:
        await session.refresh(product)  # boshqa xarid shu orada sonni o‘zgartirgan bo‘lishi mumkin
        if not product.stock:
            raise ShopError(409, "Afsuski, bu servis hozircha tugagan")
        raise ShopError(409, f"Bazada faqat {product.stock} ta bor. Sonini {product.stock} tagacha kamaytiring")

    # Avtomatik mahsulot: har bir dona uchun ro‘yxatdan alohida (hali berilmagan) element olinadi
    items: list[DeliveryItem] = []
    if product.delivery_mode == "auto" and in_stock:
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
        duration_unit=product.duration_unit,
        quantity=quantity,
        price=total,
        comment=comment or gift_note,
        status=OrderStatus.completed if instant else OrderStatus.paid,
        delivery_info="\n".join(i.content for i in items) if instant else None,
        paid_from_balance=not gift,
        customer_input=customer_input,
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
