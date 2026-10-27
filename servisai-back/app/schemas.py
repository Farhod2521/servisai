from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .models import OrderStatus, TopUpStatus, TransactionType


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORM):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    telegram_id: int | None
    telegram_username: str | None
    has_google: bool
    balance: int
    is_admin: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32, pattern=r"^\+?[0-9 ()-]{7,32}$")


class UserStats(BaseModel):
    total_orders: int
    active_orders: int
    completed_orders: int
    total_spent: int


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class GoogleLoginIn(BaseModel):
    credential: str
    # Taklif havolasidagi kod (faqat yangi ro‘yxatdan o‘tishda hisobga olinadi)
    ref: str | None = Field(default=None, max_length=32)


class TelegramInitOut(BaseModel):
    token: str
    bot_url: str
    expires_in: int


class TelegramStatusOut(BaseModel):
    status: str  # pending | confirmed | expired | error
    detail: str | None = None
    access_token: str | None = None
    user: UserOut | None = None


class AuthConfigOut(BaseModel):
    google_client_id: str | None
    telegram_bot_username: str | None


ProductCategory = Literal["chat", "design", "code", "office", "social", "other"]
ProductBadge = Literal["popular", "sale", "new", "api"]


class ProductOut(ORM):
    id: str
    name: str
    description: str
    price: int
    old_price: int | None
    durations: list[int]
    duration_unit: str
    category: str
    badge: str | None
    features: list[str]
    # None — cheklanmagan, 0 — tugagan
    stock: int | None
    # To‘langan (bekor qilinmagan) buyurtmalar soni
    sold_count: int
    delivery_time: str
    # Xariddan so‘ng darhol beriladimi (avtomatik matnning o‘zi ommaga ko‘rsatilmaydi)
    instant_delivery: bool
    notes: str


class AdminProductOut(ProductOut):
    delivery_mode: str
    # Boshlang‘ich son (sold_count = sold_base + haqiqiy xaridlar)
    sold_base: int
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


Price = Annotated[int, Field(ge=0, le=1_000_000_000)]
Feature = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProductFields(BaseModel):
    """Yaratish va tahrirlashda umumiy tekshiruvlar."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    price: Price | None = None
    old_price: Price | None = None
    durations: list[Annotated[int, Field(ge=1, le=366)]] | None = Field(default=None, min_length=1, max_length=12)
    duration_unit: Literal["day", "month"] | None = None
    category: ProductCategory | None = None
    badge: ProductBadge | None = None
    features: list[Feature] | None = Field(default=None, max_length=20)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    # null — cheklanmagan
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    sold_base: int | None = Field(default=None, ge=0, le=10_000_000)
    delivery_mode: Literal["auto", "manual"] | None = None
    delivery_time: str | None = Field(default=None, min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=3000)
    is_active: bool | None = None

    @field_validator("name", "description", "delivery_time", "notes")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else v

    @field_validator("durations")
    @classmethod
    def _unique_sorted(cls, v: list[int] | None) -> list[int] | None:
        return sorted(set(v)) if v is not None else v


class ProductCreate(ProductFields):
    # URL’da ishlatiladi (/mahsulotlar/<id>) va keyin o‘zgartirilmaydi
    id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=255)
    price: Price
    durations: list[Annotated[int, Field(ge=1, le=366)]] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def _old_price_higher(self):
        if self.old_price is not None and self.old_price <= self.price:
            raise ValueError("Eski narx hozirgi narxdan katta bo‘lishi kerak")
        return self


class ProductUpdate(ProductFields):
    pass


class AdminStats(BaseModel):
    users_total: int
    users_new_7d: int
    products_active: int
    products_total: int
    orders_total: int
    # To‘langan, lekin hali bajarilmagan (pending/paid/processing)
    orders_active: int
    revenue_total: int
    revenue_30d: int
    topups_pending: int
    suggestions_new: int


class AdminUserOut(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    telegram_id: int | None
    telegram_username: str | None
    balance: int
    is_admin: bool
    created_at: datetime
    last_login_at: datetime | None
    orders_count: int
    # To‘langan (bekor qilinmagan) buyurtmalar summasi
    total_spent: int


class AdminUserList(BaseModel):
    items: list[AdminUserOut]
    total: int
    # Barcha foydalanuvchilar hisobidagi jami mablag‘ (filtrdan qat’i nazar)
    total_balance: int
    users_with_balance: int


class DeliveryItemOut(BaseModel):
    id: int
    content: str
    created_at: datetime
    delivered_at: datetime | None
    order_id: int | None
    order_number: str | None
    user_id: int | None
    user_name: str | None


class DeliveryItemsAdd(BaseModel):
    # Har bir qator — alohida element (havola, kod...)
    lines: list[Annotated[str, StringConstraints(max_length=2000)]] = Field(min_length=1, max_length=1000)


class DeliveryItemsAddOut(BaseModel):
    added: int
    # Bo‘sh yoki ro‘yxatda allaqachon bor (berilmagan) qatorlar
    skipped: int
    stock: int | None


class AdminUserTopUp(BaseModel):
    id: int
    amount: int
    status: TopUpStatus
    admin_note: str | None
    created_at: datetime


class TopProductOut(BaseModel):
    product_id: str | None
    product_name: str
    orders: int
    revenue: int


# Bir buyurtmada olinadigan eng ko‘p son (cheklanmagan mahsulotlar uchun ham)
MAX_ORDER_QUANTITY = 100


class OrderCreate(BaseModel):
    product_id: str
    duration_months: int | None = None
    quantity: int = Field(default=1, ge=1, le=MAX_ORDER_QUANTITY)
    comment: str | None = Field(default=None, max_length=1000)


class OrderEventOut(ORM):
    id: int
    status: OrderStatus
    note: str | None
    created_at: datetime


class OrderOut(ORM):
    id: int
    number: str
    product_id: str | None
    product_name: str
    duration_months: int
    duration_unit: str
    quantity: int
    # Jami summa (narx × soni)
    price: int
    status: OrderStatus
    comment: str | None
    delivery_info: str | None
    paid_from_balance: bool
    created_at: datetime
    updated_at: datetime


class AdminOrderOut(OrderOut):
    user_id: int
    user_name: str
    user_telegram_username: str | None
    user_phone: str | None


class OrderDetailOut(OrderOut):
    events: list[OrderEventOut]


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int


class HistoryItemOut(BaseModel):
    id: int
    order_id: int
    order_number: str
    product_name: str
    status: OrderStatus
    note: str | None
    created_at: datetime


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note: str | None = Field(default=None, max_length=1000)
    delivery_info: str | None = None


class WalletOut(BaseModel):
    balance: int
    card_number: str | None
    card_holder: str | None
    min_amount: int
    max_amount: int
    # Admin chati sozlanmagan bo‘lsa to‘ldirib bo‘lmaydi
    topup_enabled: bool


class TopUpOut(ORM):
    id: int
    amount: int
    status: TopUpStatus
    admin_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class TransactionOut(ORM):
    id: int
    type: TransactionType
    amount: int
    balance_after: int
    note: str | None
    order_id: int | None
    topup_id: int | None
    created_at: datetime


class TopUpReview(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


# OrderOut e’lon qilinganidan keyin turishi kerak
class AdminUserDetail(BaseModel):
    user: AdminUserOut
    # Taklif qilgan do‘stlari soni va kim taklif qilgani
    friends: int
    referred_by_name: str | None
    # Tasdiqlangan to‘ldirishlar yig‘indisi
    topped_up: int
    topups: list[AdminUserTopUp]
    orders: list[OrderOut]


# ---------- Do‘st taklif qilish ----------


class ReferralFriendOut(BaseModel):
    name: str
    joined_at: datetime


class MyRewardOut(BaseModel):
    id: int
    title: str
    required_friends: int
    product_id: str
    product_name: str
    quantity: int
    achieved: bool
    granted: bool
    order_number: str | None


class PublicRewardOut(BaseModel):
    """Saytdagi taklif oynasi uchun (kirmagan foydalanuvchiga ham ko‘rinadi)."""

    id: int
    title: str
    required_friends: int
    product_id: str
    product_name: str
    quantity: int


class MyReferralOut(BaseModel):
    code: str
    site_link: str
    bot_link: str | None
    friends: int
    friends_list: list[ReferralFriendOut]
    rewards: list[MyRewardOut]


class ClaimOut(BaseModel):
    granted: list[MyRewardOut]


class RewardIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    required_friends: int = Field(ge=1, le=10_000)
    product_id: str
    quantity: int = Field(default=1, ge=1, le=100)
    is_active: bool = True

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RewardOut(BaseModel):
    id: int
    title: str
    required_friends: int
    product_id: str
    product_name: str
    quantity: int
    is_active: bool
    granted_count: int
    # Shartni bajargan (lekin hali olmagan bo‘lishi mumkin) foydalanuvchilar
    eligible_count: int
    created_at: datetime


class RewardGrantOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_telegram_username: str | None
    reward_title: str
    order_id: int | None
    order_number: str | None
    order_status: OrderStatus | None
    created_at: datetime


class TopReferrerOut(BaseModel):
    user_id: int
    user_name: str
    user_telegram_username: str | None
    friends: int


# ---------- Takliflar ----------


class SuggestionIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Taklif juda qisqa")
        return v


class SuggestionReply(SuggestionIn):
    pass


class SuggestionOut(ORM):
    id: int
    text: str
    reply: str | None
    replied_at: datetime | None
    reply_seen: bool
    created_at: datetime


class AdminSuggestionOut(SuggestionOut):
    user_id: int
    user_name: str
    user_telegram_username: str | None
    replied_by: str | None
