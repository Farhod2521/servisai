from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import OrderStatus


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


class ProductOut(ORM):
    id: str
    name: str
    description: str
    price: int
    old_price: int | None
    durations: list[int]


class OrderCreate(BaseModel):
    product_id: str
    duration_months: int | None = None
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
    price: int
    status: OrderStatus
    comment: str | None
    delivery_info: str | None
    created_at: datetime
    updated_at: datetime


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
