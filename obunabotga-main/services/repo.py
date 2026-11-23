"""Baza bilan ishlovchi yordamchi funksiyalar (repository qatlami)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings

from database.models import (
    CartItem, Category, DeliveryType, Order, OrderItem, OrderStatus,
    Payment, PaymentStatus, Product, StockItem, User,
)


# ─────────────────────────── Foydalanuvchi ───────────────────────────

async def get_or_create_user(
    s: AsyncSession, tg_id: int, username: str | None, full_name: str,
    referred_by: int | None = None,
) -> User:
    user = await s.scalar(select(User).where(User.tg_id == tg_id))
    if user:
        if user.username != username or user.full_name != full_name:
            user.username, user.full_name = username, full_name
            await s.commit()
        return user
    user = User(
        tg_id=tg_id, username=username, full_name=full_name,
        referred_by=referred_by if referred_by != tg_id else None,
    )
    s.add(user)
    try:
        await s.commit()
    except IntegrityError:        # ikki so'rov bir vaqtda yangi foydalanuvchini yaratmoqchi bo'ldi — ikkinchisi mavjudini oladi
        await s.rollback()
        return await s.scalar(select(User).where(User.tg_id == tg_id))
    await s.refresh(user)
    from services import alerts
    alerts.schedule_new_user(user)       # hisobot boti yoqilgan bo'lsa — «Yangi mijoz» xabari
    return user


async def set_lang(s: AsyncSession, user: User, lang: str) -> None:
    user.lang = lang
    await s.commit()


async def add_balance(s: AsyncSession, user: User, amount: int) -> None:
    user.balance += amount
    await s.commit()


# ─────────────────────────── Katalog ───────────────────────────

async def active_categories(s: AsyncSession) -> list[Category]:
    res = await s.scalars(
        select(Category).where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.id)
    )
    return list(res)


async def get_category(s: AsyncSession, cat_id: int) -> Category | None:
    return await s.get(Category, cat_id)


async def category_products(s: AsyncSession, cat_id: int) -> list[Product]:
    res = await s.scalars(
        select(Product)
        .where(Product.category_id == cat_id, Product.is_active.is_(True))
        .options(selectinload(Product.stock))
        .order_by(Product.id)
    )
    return list(res)


async def get_product(s: AsyncSession, pid: int) -> Product | None:
    return await s.scalar(
        select(Product).where(Product.id == pid).options(selectinload(Product.stock))
    )


async def stock_count(s: AsyncSession, product: Product) -> int:
    """Mavjud qoldiq.

    Uch xil manba bo'lishi mumkin:
      • unlimited=True      → cheksiz (obuna, xizmat)
      • stock_qty berilgan  → ta'minotchi e'lon qilgan son
      • aks holda           → sotilmagan StockItem qatorlari soni
    """
    if product.unlimited:
        return 10**9
    if product.stock_qty is not None:
        return max(product.stock_qty, 0)
    return await s.scalar(
        select(func.count(StockItem.id)).where(
            StockItem.product_id == product.id, StockItem.is_sold.is_(False)
        )
    ) or 0


async def storefront_products(s: AsyncSession) -> list[Product]:
    """Mini App uchun: faol kategoriyalardagi barcha faol mahsulotlar."""
    res = await s.scalars(
        select(Product)
        .join(Category, Category.id == Product.category_id)
        .where(Product.is_active.is_(True), Category.is_active.is_(True))
        .options(selectinload(Product.stock))
        .order_by(Category.sort_order, Product.id)
    )
    return list(res)


async def sales_by_product(s: AsyncSession) -> dict[int, int]:
    """product_id → sotilgan dona (mashhurlik tartibi uchun)."""
    rows = await s.execute(
        select(OrderItem.product_id, func.coalesce(func.sum(OrderItem.qty), 0))
        .where(OrderItem.product_id.is_not(None))
        .group_by(OrderItem.product_id)
    )
    return {pid: int(n) for pid, n in rows}


def stock_of(product: Product) -> int | None:
    """Yuklangan zaxiradan qoldiq. None = cheksiz. (stock_count bilan bir xil qoida.)"""
    if product.unlimited:
        return None
    if product.stock_qty is not None:
        return max(product.stock_qty, 0)
    return sum(1 for item in product.stock if not item.is_sold)


# ─────────────────────────── Savat ───────────────────────────

async def cart_items(s: AsyncSession, user: User) -> list[CartItem]:
    res = await s.scalars(
        select(CartItem).where(CartItem.user_id == user.id)
        .options(selectinload(CartItem.product))
    )
    return list(res)


async def cart_add(s: AsyncSession, user: User, product: Product, qty: int = 1) -> None:
    item = await s.scalar(
        select(CartItem).where(
            CartItem.user_id == user.id, CartItem.product_id == product.id
        )
    )
    if item:
        item.qty += qty
    else:
        s.add(CartItem(user_id=user.id, product_id=product.id, qty=qty))
    await s.commit()


async def cart_clear(s: AsyncSession, user: User) -> None:
    for item in await cart_items(s, user):
        await s.delete(item)
    await s.commit()


# ─────────────────────────── Buyurtma ───────────────────────────

class OutOfStock(Exception):
    def __init__(self, product_name: str):
        self.product_name = product_name
        super().__init__(product_name)


class NotEnoughBalance(Exception):
    def __init__(self, need: int, have: int):
        self.need, self.have = need, have
        super().__init__()


async def create_order(
    s: AsyncSession, user: User, lines: list[tuple[Product, int]]
) -> Order:
    """Balansdan yechib, zaxirani band qilib buyurtma yaratadi.

    Zaxira SELECT ... WITH FOR UPDATE orqali qulflanadi (PostgreSQL'da),
    shu sababli bir vaqtda ikki xarid bitta kodni olmaydi.
    """
    total = sum(p.price * q for p, q in lines)
    if user.balance < total:
        raise NotEnoughBalance(total, user.balance)

    order = Order(user_id=user.id, total=total, status=OrderStatus.PAID)
    s.add(order)
    await s.flush()

    for product, qty in lines:
        delivered: list[str] = []

        # Ta'minotchi qoldig'i bilan ishlaydigan tovarlar
        if product.stock_qty is not None and not product.unlimited:
            if product.stock_qty < qty:
                name = product.name  # rollback obyektni eskirtiradi — nomni oldindan olamiz
                await s.rollback()
                raise OutOfStock(name)
            product.stock_qty -= qty
            if product.stock_qty <= 0:
                product.is_active = False

        elif product.delivery_type == DeliveryType.AUTO and not product.unlimited:
            stmt = (
                select(StockItem)
                .where(StockItem.product_id == product.id, StockItem.is_sold.is_(False))
                .limit(qty)
            )
            if settings.is_postgres:
                stmt = stmt.with_for_update(skip_locked=True)
            picked = list(await s.scalars(stmt))
            if len(picked) < qty:
                name = product.name
                await s.rollback()
                raise OutOfStock(name)
            for item in picked:
                item.is_sold = True
                item.sold_at = datetime.utcnow()
                delivered.append(item.content)

        s.add(OrderItem(
            order_id=order.id, product_id=product.id, product_name=product.name,
            price=product.price, qty=qty, delivered_content="\n".join(delivered),
        ))

    user.balance -= total
    if all(p.delivery_type == DeliveryType.AUTO for p, _ in lines):
        order.status = OrderStatus.DELIVERED
    await s.commit()

    # items ni aniq yuklab qaytaramiz (refresh relationship'ni kafolatlamaydi)
    loaded = await s.scalar(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return loaded or order


async def user_orders(s: AsyncSession, user: User, limit: int = 15) -> list[Order]:
    res = await s.scalars(
        select(Order).where(Order.user_id == user.id)
        .order_by(Order.id.desc()).limit(limit)
    )
    return list(res)


# ─────────────────────────── To'lov ───────────────────────────

async def create_payment(
    s: AsyncSession, user: User, amount: int, provider: str
) -> Payment:
    p = Payment(user_id=user.id, amount=amount, provider=provider)
    s.add(p)
    await s.commit()
    await s.refresh(p)
    return p


async def user_payments(s: AsyncSession, user: User, limit: int = 20) -> list[Payment]:
    res = await s.scalars(
        select(Payment).where(Payment.user_id == user.id)
        .order_by(Payment.id.desc()).limit(limit)
    )
    return list(res)


async def mark_payment_paid(s: AsyncSession, payment_id: int) -> Payment | None:
    """To'lovni tasdiqlaydi va balansga qo'shadi. Ikki marta qo'shilmaydi."""
    p = await s.scalar(
        select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.user))
    )
    if not p or p.status == PaymentStatus.PAID:
        return p
    p.status = PaymentStatus.PAID
    p.paid_at = datetime.utcnow()
    p.user.balance += p.amount
    await s.commit()
    return p


# ─────────────────────────── Statistika ───────────────────────────

async def stats(s: AsyncSession) -> dict:
    users = await s.scalar(select(func.count(User.id))) or 0
    orders = await s.scalar(select(func.count(Order.id))) or 0
    revenue = await s.scalar(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]))
    ) or 0
    products = await s.scalar(
        select(func.count(Product.id)).where(Product.is_active.is_(True))
    ) or 0
    in_stock = await s.scalar(
        select(func.count(StockItem.id)).where(StockItem.is_sold.is_(False))
    ) or 0
    pending_orders = await s.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PAID)
    ) or 0
    return {
        "users": users, "orders": orders, "revenue": revenue,
        "products": products, "in_stock": in_stock, "pending_orders": pending_orders,
    }


async def all_user_ids(s: AsyncSession) -> list[int]:
    res = await s.scalars(select(User.tg_id).where(User.is_banned.is_(False)))
    return list(res)
