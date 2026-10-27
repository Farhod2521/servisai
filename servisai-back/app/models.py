import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    # Hisobdagi mablag‘ (so‘mda)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    # Shaxsiy taklif havolasi kodi (birinchi so‘ralganda yaratiladi)
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    # Shu foydalanuvchini kim taklif qilgan (faqat ro‘yxatdan o‘tishda belgilanadi)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    orders: Mapped[list["Order"]] = relationship(back_populates="user")

    @property
    def has_google(self) -> bool:
        return self.google_id is not None


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    # Frontend katalogidagi slug bilan bir xil (masalan "chatgpt-plus")
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)
    old_price: Mapped[int | None] = mapped_column(Integer)
    durations: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    # durations qaysi birlikda: month — oy, day — kun
    duration_unit: Mapped[str] = mapped_column(String(8), default="month", server_default="month")
    # Katalog filtri: chat | design | code | office | social | other
    category: Mapped[str] = mapped_column(String(32), default="other", server_default="other")
    # Kartochkadagi belgi: popular | sale | new | api
    badge: Mapped[str | None] = mapped_column(String(16))
    # Servis sahifasidagi "Nimalar kiradi?" ro‘yxati
    features: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    # Katalogdagi tartib (kichik = yuqorida)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Saytdagi boshlang‘ich "sotib olganlar" soni; haqiqiy xaridlar shu songa qo‘shiladi
    sold_base: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Sotuvdagi soni: NULL — cheklanmagan, 0 — tugagan (saytda oq-qora, sotib bo‘lmaydi)
    stock: Mapped[int | None] = mapped_column(Integer, CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"))
    # manual — admin qo‘lda yetkazadi; auto — har xaridorga delivery_items dan alohida element darhol beriladi
    delivery_mode: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    # Mijozga ko‘rsatiladigan yetkazib berish vaqti (masalan "10 daqiqa – 1 soat")
    delivery_time: Mapped[str] = mapped_column(String(64), default="10 daqiqa – 1 soat", server_default="10 daqiqa – 1 soat")
    # Servis sahifasidagi "Muhim ma’lumot" (qoidalar, kafolat shartlari)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def instant_delivery(self) -> bool:
        """Avtomatik rejimda soni = berilmagan elementlar soni, shuning uchun sotuvda bo‘lsa darhol beriladi."""
        return self.delivery_mode == "auto"

    # Ro‘yxat endpointlarida buyurtmalardan hisoblab qo‘yiladi (bazada ustun emas;
    # annotatsiyasiz, aks holda SQLAlchemy uni ustun deb tushunadi)
    sold_count = 0


class OrderStatus(str, enum.Enum):
    pending = "pending"  # To‘lov kutilmoqda
    paid = "paid"  # To‘langan
    processing = "processing"  # Faollashtirilmoqda
    completed = "completed"  # Bajarildi
    cancelled = "cancelled"  # Bekor qilindi


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    # Mahsulot keyinchalik o‘zgarsa ham buyurtma tarixi saqlanib qolishi uchun nusxa
    product_name: Mapped[str] = mapped_column(String(255))
    # Nomi tarixiy: son duration_unit birligida (oy yoki kun)
    duration_months: Mapped[int] = mapped_column(Integer)
    duration_unit: Mapped[str] = mapped_column(String(8), default="month", server_default="month")
    quantity: Mapped[int] = mapped_column(
        Integer, CheckConstraint("quantity >= 1", name="ck_orders_quantity_positive"), default=1, server_default="1"
    )
    # Jami to‘langan summa (narx × soni)
    price: Mapped[int] = mapped_column(Integer)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.pending, index=True
    )
    comment: Mapped[str | None] = mapped_column(Text)
    # Bajarilgandan so‘ng mijozga ko‘rsatiladigan ma’lumot (login, faollashtirish yo‘riqnomasi va h.k.)
    delivery_info: Mapped[str | None] = mapped_column(Text)
    # Hisobdan to‘langan buyurtma bekor qilinsa, pul hisobga qaytariladi
    paid_from_balance: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    user: Mapped[User] = relationship(back_populates="orders")
    events: Mapped[list["OrderEvent"]] = relationship(
        back_populates="order", order_by=lambda: (OrderEvent.created_at, OrderEvent.id), cascade="all, delete-orphan"
    )

    @property
    def number(self) -> str:
        return f"SA-{self.id:06d}"


class OrderEvent(Base):
    """Buyurtma tarixi: har bir status o‘zgarishi alohida yoziladi."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="events")


class TelegramLoginStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    used = "used"


class TelegramLoginSession(Base):
    """Sayt -> bot -> sayt kirish oqimi uchun bir martalik token."""

    __tablename__ = "telegram_login_sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[TelegramLoginStatus] = mapped_column(
        Enum(TelegramLoginStatus, name="telegram_login_status"), default=TelegramLoginStatus.pending
    )
    # Agar tizimga kirgan foydalanuvchi Telegramni profiliga ulayotgan bo‘lsa
    link_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Saytdagi taklif kodi: bot kirishni tasdiqlaganda yangi foydalanuvchiga biriktiriladi
    ref_code: Mapped[str | None] = mapped_column(String(16))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    error: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TopUpStatus(str, enum.Enum):
    pending = "pending"  # Admin tekshiruvida
    approved = "approved"  # Tasdiqlandi, hisobga tushdi
    rejected = "rejected"  # Rad etildi


class TopUp(Base):
    """Hisobni to‘ldirish so‘rovi: foydalanuvchi chek yuboradi, admin Telegramda tasdiqlaydi."""

    __tablename__ = "topups"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    receipt_path: Mapped[str] = mapped_column(String(255))
    status: Mapped[TopUpStatus] = mapped_column(
        Enum(TopUpStatus, name="topup_status"), default=TopUpStatus.pending, index=True
    )
    admin_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()


class TransactionType(str, enum.Enum):
    topup = "topup"  # Hisob to‘ldirildi
    purchase = "purchase"  # Xarid uchun yechildi
    refund = "refund"  # Bekor qilingan buyurtma qaytarildi


class Transaction(Base):
    """Hisobdagi har bir harakat (kirim +, chiqim -)."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"))
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    topup_id: Mapped[int | None] = mapped_column(ForeignKey("topups.id", ondelete="SET NULL"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeliveryItem(Base):
    """Avtomatik mahsulotning bitta nusxasi (havola, kod, login...). Har biri faqat bitta xaridorga beriladi."""

    __tablename__ = "delivery_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    # NULL — hali hech kimga berilmagan
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReferralReward(Base):
    """Sovg‘a qoidasi: N ta do‘st taklif qilgan foydalanuvchiga mahsulot bepul beriladi."""

    __tablename__ = "referral_rewards"
    __table_args__ = (
        CheckConstraint("required_friends >= 1", name="ck_rewards_friends_positive"),
        CheckConstraint("quantity >= 1", name="ck_rewards_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    required_friends: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship(lazy="joined")


class RewardGrant(Base):
    """Foydalanuvchiga berilgan sovg‘a (har biri bir marta)."""

    __tablename__ = "reward_grants"
    __table_args__ = (UniqueConstraint("user_id", "reward_id", name="uq_reward_grants_user_reward"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reward_id: Mapped[int] = mapped_column(ForeignKey("referral_rewards.id", ondelete="CASCADE"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Suggestion(Base):
    """Foydalanuvchi taklifi (qaysi servis kerak va h.k.) va adminning javobi."""

    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    reply: Mapped[str | None] = mapped_column(Text)
    replied_by: Mapped[str | None] = mapped_column(String(255))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Foydalanuvchi javobni saytda ko‘rdimi
    reply_seen: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
