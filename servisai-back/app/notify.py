"""Telegram Bot API orqali xabar yuborish (xato bo‘lsa jim o‘tkazib yuboriladi)."""

import html
import logging

import httpx

from .config import settings
from .models import Order, OrderStatus, User

log = logging.getLogger(__name__)

STATUS_LABELS = {
    OrderStatus.pending: "⏳ To‘lov kutilmoqda",
    OrderStatus.paid: "💳 To‘landi",
    OrderStatus.processing: "⚙️ Faollashtirilmoqda",
    OrderStatus.completed: "✅ Bajarildi",
    OrderStatus.cancelled: "❌ Bekor qilindi",
}


def format_price(n: int) -> str:
    return f"{n:,}".replace(",", " ")


async def send_message(chat_id: int | str, text: str) -> None:
    if not settings.telegram_bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    except httpx.HTTPError:
        log.warning("Telegramga xabar yuborib bo‘lmadi", exc_info=True)


async def notify_order_created(order: Order, user: User) -> None:
    summary = (
        f"<b>{order.number}</b> — {html.escape(order.product_name)} ({order.duration_months} oy)\n"
        f"Narxi: {format_price(order.price)} so‘m"
    )
    if user.telegram_id:
        await send_message(
            user.telegram_id,
            f"🛒 Buyurtmangiz qabul qilindi!\n\n{summary}\n\nTo‘lov va faollashtirish bo‘yicha operator tez orada bog‘lanadi.",
        )
    contact = " / ".join(
        html.escape(c)
        for c in (user.full_name, user.email, user.phone, user.telegram_username and f"@{user.telegram_username}")
        if c
    )
    await send_message(settings.telegram_admin_chat_id, f"🆕 Yangi buyurtma\n\n{summary}\nMijoz: {contact}")


async def notify_order_status(order: Order, user: User, note: str | None) -> None:
    if not user.telegram_id:
        return
    text = f"<b>{order.number}</b> — {html.escape(order.product_name)}\nHolati: {STATUS_LABELS[order.status]}"
    if note:
        text += f"\n\n{html.escape(note)}"
    await send_message(user.telegram_id, text)
