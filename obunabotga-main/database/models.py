"""Baza modellari.

Pul birligi: so'm, butun son sifatida saqlanadi (tiyin yo'q).
Har bir mahsulotning zaxirasi StockItem jadvalida yotadi — bitta StockItem
= bitta sotiladigan birlik. Sotilgandan keyin is_sold=True bo'ladi.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, LargeBinary, String, Text, func, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    PENDING = "pending"      # to'lov kutilmoqda
    PAID = "paid"            # to'langan, yetkazilmagan
    DELIVERED = "delivered"  # yetkazildi
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryType(str, enum.Enum):
    AUTO = "auto"      # zaxiradan avtomatik matn beriladi
    MANUAL = "manual"  # admin qo'lda bajaradi


class ProductSource(str, enum.Enum):
    MANUAL = "manual"  # admin qo'lda kiritgan
    API = "api"        # ta'minotchi API sidan kelgan


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    lang: Mapped[str] = mapped_column(String(4), default="uz")
    balance: Mapped[int] = mapped_column(BigInteger, default=0)  # so'm
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Yangi mahsulot / zaxira xabarnomalarini olish (mijoz xabar tagidagi tugma bilan o'chiradi)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    cart_items: Mapped[list["CartItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    emoji: Mapped[str] = mapped_column(String(32), default="📦")
    # Premium (custom) emoji id — ixtiyoriy
    custom_emoji_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name_uz: Mapped[str] = mapped_column(String(128))
    name_ru: Mapped[str] = mapped_column(String(128), default="")
    name_en: Mapped[str] = mapped_column(String(128), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    products: Mapped[list["Product"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

    def name(self, lang: str = "uz") -> str:
        return getattr(self, f"name_{lang}", None) or self.name_uz


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    emoji: Mapped[str] = mapped_column(String(32), default="🔹")
    custom_emoji_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(BigInteger)  # so'm
    old_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivery_type: Mapped[DeliveryType] = mapped_column(
        Enum(DeliveryType), default=DeliveryType.AUTO
    )
    # MANUAL turdagi mahsulot uchun cheksiz zaxira imkoniyati
    unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    announced: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Tashqi katalog (ta'minotchi API si) ──
    source: Mapped[ProductSource] = mapped_column(
        Enum(ProductSource), default=ProductSource.MANUAL, index=True
    )
    # Ta'minotchidagi ID — sinxronizatsiya shu bo'yicha ishlaydi
    external_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Ta'minotchi e'lon qilgan qoldiq (StockItem qatorlari o'rniga)
    stock_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ta'minotchining o'z narxi — marja hisoblash uchun saqlanadi
    supplier_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Brend (logotip uchun): ko'rsatiladigan nom va logotip olinadigan sayt domeni
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Qo'llanma: mahsulotdan qanday foydalaniladi / qanday kiriladi (admin yozadi, sinxronlash tegmaydi)
    guide: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ta'minotchi ma'lumoti (JSON): turi, talab qilinadigan maydonlar, kafolat
    guide_video: Mapped[str | None] = mapped_column(Text, nullable=True)   # video qo'llanma: "tg:<file_id>" yoki havola
    warranty_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # buyurtmada ko'rsatiladigan kafolat matni (admin)
    supplier_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Admin qo'lda o'zgartirgan maydonlar (JSON ro'yxat) — sinxronlash ularni qayta yozmaydi
    overrides: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped[Category] = relationship(back_populates="products")
    stock: Mapped[list["StockItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class StockItem(Base):
    """Bitta sotiladigan birlik (masalan: bitta aktivatsiya kodi yoki havola)."""
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    product: Mapped[Product] = relationship(back_populates="stock")


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    qty: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped[User] = relationship(back_populates="cart_items")
    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    total: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255))
    price: Mapped[int] = mapped_column(BigInteger)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    delivered_content: Mapped[str] = mapped_column(Text, default="")
    # ok — bajarildi, pending — qo'lda bajariladi/tekshiriladi, failed — bekor (pul qaytarilgan)
    status: Mapped[str] = mapped_column(String(16), default="ok", server_default="ok")
    customer_input: Mapped[str | None] = mapped_column(Text, nullable=True)   # mijoz kiritgan email / akkauntlar
    supplier_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)  # ta'minotchidagi buyurtma kodi

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(BigInteger)
    provider: Mapped[str] = mapped_column(String(32), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.CREATED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()

class TopupOrder(Base):
    """Hamyonni to'ldirish buyurtmasi (avtomatik to'lov). paymentAmount = baseAmount + noyob 101–999 so'm."""
    __tablename__ = "topup_orders"
    __table_args__ = (
        # Bir vaqtda faol (pending) ikki buyurtmada bir xil summa bo'lmaydi — bazaning o'zi kafolatlaydi
        Index("uq_topup_pending_amount", "payment_amount", unique=True,
              sqlite_where=text("status = 'pending'"), postgresql_where=text("status = 'pending'")),
        # Bir to'lov tranzaksiyasi ikki marta ishlatilmaydi
        Index("uq_topup_provider_txn", "provider", "provider_txn_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_id: Mapped[str] = mapped_column(String(32), default="topup")
    base_amount: Mapped[int] = mapped_column(BigInteger)
    payment_amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)   # pending|paid|cancelled|expired
    provider: Mapped[str] = mapped_column(String(12), default="card")                # card|payme|click
    provider_txn_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()


class BankCredit(Base):
    """CardXabarBot / SMS orqali kelgan kirim xabarlari (takror qayta ishlanmasligi va «tekshirish» uchun)."""
    __tablename__ = "bank_credits"
    __table_args__ = (Index("uq_bank_credit_msg", "source", "source_msg_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    source_msg_id: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(BigInteger, index=True)
    text: Mapped[str] = mapped_column(String(400), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="new")   # new|matched|candidate


class PaymeTransaction(Base):
    __tablename__ = "payme_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    payme_id: Mapped[str] = mapped_column(String(64), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("topup_orders.id", ondelete="CASCADE"), index=True)
    amount_tiyin: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[int] = mapped_column(Integer, default=1)          # 1 yaratilgan, 2 bajarilgan, -1/-2 bekor
    create_time: Mapped[int] = mapped_column(BigInteger)            # millisekund
    perform_time: Mapped[int] = mapped_column(BigInteger, default=0)
    cancel_time: Mapped[int] = mapped_column(BigInteger, default=0)
    reason: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ClickTransaction(Base):
    __tablename__ = "click_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    click_trans_id: Mapped[str] = mapped_column(String(64), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("topup_orders.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(12), default="prepared")   # prepared|completed|cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PaymentLog(Base):
    """To'lov jurnali: har bir muhim hodisa (yaratildi, tasdiqlandi, rad etildi, xato)."""
    __tablename__ = "payment_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str | None] = mapped_column(String(12), nullable=True)
    detail: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PriceChange(Base):
    """Mahsulot narxi o'zgargan payt (ta'minotchi narxi/kurs yoki admin): admin «Narx o'zgarishlari» da ko'radi."""
    __tablename__ = "price_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    old_price: Mapped[int] = mapped_column(BigInteger)
    new_price: Mapped[int] = mapped_column(BigInteger)
    old_supplier: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_supplier: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="sync")     # sync | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class ProductImage(Base):
    """Admin yuklagan mahsulot rasmi (bazada saqlanadi — Render qayta ishga tushganda yo'qolmaydi)."""
    __tablename__ = "product_images"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    mime: Mapped[str] = mapped_column(String(32), default="image/jpeg")
    tg_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)   # xabarnomada qayta yuborish uchun
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    """Admin paneldan o'zgartiriladigan sozlamalar (foyda foizi, kurs, premium emoji...)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
