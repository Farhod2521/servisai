"""To‘langan buyurtmani ta’minotchidan sotib olib yetkazish.

  • muvaffaqiyatli → yetkazilgan ma’lumot (akkaunt, kod...) buyurtmaga yoziladi, buyurtma bajarildi;
  • ta’minotchi hali tugatmagan (slot, akkaunt yangilash) → «Faollashtirilmoqda», admin kuzatadi;
  • xarid O‘TMAGAN → buyurtma bekor, pul hisobga qaytariladi;
  • natija noma’lum → pul QAYTARILMAYDI (xarid o‘tgan bo‘lishi mumkin), admin ta’minotchi panelida tekshiradi.

Har bir buyurtma noyob Idempotency-Key bilan yuboriladi — qayta urinish ikki marta sotib olmaydi.
"""

import html
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Order, OrderEvent, OrderStatus, Product, TransactionType
from ..notify import send_message
from ..stock import give_back
from ..wallet import change_balance
from . import client

log = logging.getLogger("servisai.supplier")


def idempotency_key(order: Order) -> str:
    return f"servisai-o{order.id}"


async def fulfill(session: AsyncSession, order: Order) -> str | None:
    """Ta’minotchi mahsuloti bo‘lsa sotib oladi va buyurtmani yangilaydi (commit qiladi).

    Natija: "ok" | "processing" | "failed" | "unknown"; ta’minotchi mahsuloti bo‘lmasa None.
    `order.events` oldindan yuklangan bo‘lishi kerak.
    """
    product = await session.get(Product, order.product_id) if order.product_id else None
    if product is None or product.delivery_mode != "supplier" or not product.external_id or order.status != OrderStatus.paid:
        return None

    need = product.needs_input
    value = order.customer_input or ""
    res = await client.purchase(
        product.external_id,
        order.quantity,
        idempotency_key(order),
        email=value if need == "email" else None,
        accounts=value.splitlines() if need == "accounts" else None,
    )
    order.supplier_ref = res.order_code[:64] or None

    if res.kind == "ok" and res.completed:
        order.status = OrderStatus.completed
        order.delivery_info = res.content
        order.events.append(OrderEvent(status=OrderStatus.completed, note="Avtomatik yetkazib berildi"))
        outcome = "ok"
    elif res.kind == "ok":
        order.status = OrderStatus.processing
        if res.content:
            order.delivery_info = res.content
        order.events.append(OrderEvent(status=OrderStatus.processing, note="Faollashtirilmoqda — tayyor bo‘lgach shu yerda ko‘rasiz"))
        outcome = "processing"
    elif res.kind == "failed":
        order.status = OrderStatus.cancelled
        note = "Servis hozircha bera olmadi, buyurtma bekor qilindi"
        if order.paid_from_balance and order.price > 0:
            await change_balance(
                session, order.user_id, order.price, TransactionType.refund, note=f"{order.number} bekor qilindi", order_id=order.id
            )
            note += ". Mablag‘ hisobingizga qaytarildi"
        await give_back(session, order.product_id, order.quantity)
        order.events.append(OrderEvent(status=OrderStatus.cancelled, note=note))
        outcome = "failed"
    else:
        # Pul qaytarilmaydi: xarid o‘tgan bo‘lishi mumkin. Buyurtma «To‘langan»da qoladi, admin tekshiradi.
        outcome = "unknown"
    await session.commit()

    if outcome != "ok":
        log.warning("Ta’minotchi: %s %s — %s", order.number, outcome, res.message)
        await alert_admin(order, outcome, res.message)
    return outcome


async def alert_admin(order: Order, outcome: str, message: str) -> None:
    head = {
        "processing": "⏳ Ta’minotchi buyurtmani hali tugatmadi (slot/akkaunt yangilash)",
        "failed": "❌ Ta’minotchi xaridni rad etdi — mijoz puli qaytarildi",
        "unknown": "❓ Ta’minotchi javobi noma’lum — pul QAYTARILMADI",
    }[outcome]
    lines = [f"⚠️ <b>{order.number}</b> — {html.escape(order.product_name)}", head]
    if message:
        lines.append(f"Sabab: {html.escape(message)}")
    if order.supplier_ref:
        lines.append(f"Ta’minotchi kodi: <code>{html.escape(order.supplier_ref)}</code>")
    if outcome == "unknown":
        lines.append(f"Ta’minotchi panelida <code>{idempotency_key(order)}</code> buyurtmasini tekshiring.")
    if any(w in (message or "").lower() for w in ("balance", "wallet", "insufficient")):
        lines.append("💳 Ta’minotchidagi hamyon yetarli emas — uni to‘ldiring.")
    try:
        await send_message(settings.telegram_admin_chat_id, "\n".join(lines))
    except Exception:  # noqa: BLE001 — xabar ketmasa ham buyurtma saqlangan
        log.exception("Adminga xabar yuborilmadi")
