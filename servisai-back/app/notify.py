"""Telegram Bot API orqali xabar yuborish (xato bo‘lsa jim o‘tkazib yuboriladi)."""

import html
import json
import logging

import httpx

from .config import settings
from .models import Order, OrderStatus, TopUp, User

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


def user_contact(user: User) -> str:
    return " / ".join(
        html.escape(c)
        for c in (user.full_name, user.email, user.phone, user.telegram_username and f"@{user.telegram_username}")
        if c
    )


def topup_caption(topup: TopUp, user: User) -> str:
    return (
        f"💰 <b>Hisobni to‘ldirish #{topup.id}</b>\n\n"
        f"Summa: <b>{format_price(topup.amount)} so‘m</b>\n"
        f"Mijoz: {user_contact(user)} (ID {user.id})\n"
        f"Joriy balans: {format_price(user.balance)} so‘m"
    )


def topup_keyboard(topup_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Tasdiqlash", "callback_data": f"topup:approve:{topup_id}"},
                {"text": "❌ Rad etish", "callback_data": f"topup:reject:{topup_id}"},
            ]
        ]
    }


async def send_topup_to_admin(topup: TopUp, user: User, file_name: str, content: bytes, content_type: str) -> bool:
    """Chekni admin chatiga tugmalar bilan yuboradi. Muvaffaqiyatli bo‘lsa True."""
    if not settings.telegram_bot_token or not settings.telegram_admin_chat_id:
        return False
    is_photo = content_type in ("image/jpeg", "image/png", "image/webp")
    method, field = ("sendPhoto", "photo") if is_photo else ("sendDocument", "document")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    data = {
        "chat_id": settings.telegram_admin_chat_id,
        "caption": topup_caption(topup, user),
        "parse_mode": "HTML",
        "reply_markup": json.dumps(topup_keyboard(topup.id)),
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, data=data, files={field: (file_name, content, content_type)})
        if not res.json().get("ok"):
            log.warning("Chekni yuborib bo‘lmadi: %s", res.text)
            return False
        return True
    except (httpx.HTTPError, ValueError):
        log.warning("Chekni yuborib bo‘lmadi", exc_info=True)
        return False


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
            f"🛒 Buyurtmangiz qabul qilindi!\n\n{summary}\n\n"
            + ("Summa hisobingizdan yechildi. " if order.paid_from_balance else "")
            + "Faollashtirish bo‘yicha operator tez orada bog‘lanadi.",
        )
    paid = "\n💳 Hisobdan to‘landi" if order.paid_from_balance else ""
    await send_message(settings.telegram_admin_chat_id, f"🆕 Yangi buyurtma\n\n{summary}{paid}\nMijoz: {user_contact(user)}")


async def notify_order_status(order: Order, user: User, note: str | None) -> None:
    if not user.telegram_id:
        return
    text = f"<b>{order.number}</b> — {html.escape(order.product_name)}\nHolati: {STATUS_LABELS[order.status]}"
    if note:
        text += f"\n\n{html.escape(note)}"
    await send_message(user.telegram_id, text)


async def notify_topup_result(topup: TopUp, user: User) -> None:
    if not user.telegram_id:
        return
    if topup.status.value == "approved":
        text = (
            f"✅ Hisobingiz <b>{format_price(topup.amount)} so‘m</b>ga to‘ldirildi!\n"
            f"Joriy balans: <b>{format_price(user.balance)} so‘m</b>"
        )
    else:
        text = f"❌ {format_price(topup.amount)} so‘mlik to‘ldirish so‘rovingiz (#{topup.id}) rad etildi."
        if topup.admin_note:
            text += f"\nSabab: {html.escape(topup.admin_note)}"
        text += "\nSavollar bo‘lsa, operatorga yozing."
    await send_message(user.telegram_id, text)
