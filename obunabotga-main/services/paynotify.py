"""Avtomatik to'lov: Telegram xabarlari (mijozga yo'riqnoma, muvaffaqiyat; ownerga hisobot va nomzodlar)."""
from __future__ import annotations

import base64
import html
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from database.db import SessionMaker
from database.models import TopupOrder, User
from locales.texts import money
from services import runtime, topup

log = logging.getLogger("uzshop.paynotify")


def is_owner(tg_id: int | None) -> bool:
    """To'lov administratori — FAQAT raqamli Telegram ID bo'yicha (username emas)."""
    return tg_id is not None and int(tg_id) == int(settings.owner_id)


def mask_card(num: str) -> str:
    d = "".join(c for c in num if c.isdigit())
    return f"{d[:4]} •••• •••• {d[-4:]}" if len(d) >= 12 else "••••"


def fmt_card(num: str) -> str:
    d = "".join(c for c in num if c.isdigit())
    return " ".join(d[i:i + 4] for i in range(0, len(d), 4)) if d else num


# ─────────────────────────── To'lov havolalari ───────────────────────────

def payme_enabled() -> bool:
    return bool(settings.payme_merchant_id and settings.payme_auth_key)


def click_enabled() -> bool:
    return bool(settings.click_merchant_id and settings.click_service_id and settings.click_secret_key)


def card_enabled() -> bool:
    return bool(runtime.card_number())


def return_url() -> str:
    if settings.telegram_bot_username:
        return f"https://t.me/{settings.telegram_bot_username.lstrip('@')}"
    return settings.webapp_public_url or settings.public_url or "https://t.me"


def payme_url(order: TopupOrder) -> str | None:
    if not payme_enabled():
        return None
    raw = f"m={settings.payme_merchant_id};ac.order_id={order.id};a={order.payment_amount * 100};c={return_url()}"
    return "https://checkout.paycom.uz/" + base64.b64encode(raw.encode()).decode()


def click_url(order: TopupOrder) -> str | None:
    if not click_enabled():
        return None
    from urllib.parse import quote
    return ("https://my.click.uz/services/pay"
            f"?service_id={settings.click_service_id}&merchant_id={settings.click_merchant_id}"
            f"&amount={order.payment_amount}&transaction_param={order.id}&return_url={quote(return_url(), safe='')}")


# ─────────────────────────── Mijozga ───────────────────────────

def order_text(order: TopupOrder) -> str:
    lines = [f"💳 <b>To'lov — buyurtma #{order.id}</b>", ""]
    if card_enabled():
        lines.append(f"Karta: <code>{fmt_card(runtime.card_number())}</code>")
        if runtime.card_owner():
            lines.append(f"Karta egasi: <b>{html.escape(runtime.card_owner())}</b>")
    lines += [
        f"💵 Aniq summa: <b>{money(order.payment_amount)}</b>",
        "",
        "⚠️ Aynan shu summani yuboring (tiyinigacha) — to'lov shunda avtomatik tasdiqlanadi.",
        f"⏱ Muddat: 30 daqiqa ({topup.to_tashkent_time(order.expires_at)} gacha)",
    ]
    return "\n".join(lines)


def order_kb(order: TopupOrder) -> InlineKeyboardMarkup:
    rows = []
    pu, cu = payme_url(order), click_url(order)
    if pu:
        rows.append([InlineKeyboardButton(text="💳 Payme orqali to'lash", url=pu)])
    if cu:
        rows.append([InlineKeyboardButton(text="💳 Click orqali to'lash", url=cu)])
    rows.append([InlineKeyboardButton(text="✅ To'lov qildim — tekshirish", callback_data=f"pay:check:{order.id}")])
    rows.append([InlineKeyboardButton(text="❌ Buyurtmani bekor qilish", callback_data=f"pay:cancel:{order.id}")])
    tail = [InlineKeyboardButton(text="📊 Mening hisobim", callback_data="pay:me")]
    if runtime.support_username():
        tail.append(InlineKeyboardButton(text="💬 Yordam", url=f"https://t.me/{runtime.support_username()}"))
    rows.append(tail)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_order(bot, order: TopupOrder) -> None:
    await bot.send_message(order.telegram_chat_id, order_text(order), reply_markup=order_kb(order))
    who = f"@{order.username}" if order.username else f"ID {order.telegram_chat_id}"
    from services import alerts
    await alerts.broadcast(bot, (f"🧾 <b>To'ldirish so'rovi</b> · #{order.id}\n👤 {html.escape(who)} (<code>{order.telegram_chat_id}</code>)\n"
                                 f"💵 {money(order.payment_amount)} (asosiy {money(order.base_amount)}) · {order.provider}"), owner_only=True)


def paid_text(order: TopupOrder, balance: int | None) -> str:
    text = (f"✅ <b>To'lov qabul qilindi!</b>\n\nBuyurtma #{order.id}\n"
            f"💵 Hamyonga qo'shildi: <b>{money(order.payment_amount)}</b>\n")
    if balance is not None:
        text += f"💰 Hozirgi balans: <b>{money(balance)}</b>\n"
    return text + f"🕒 {topup.to_tashkent(order.paid_at)}\n\nEndi «Obunalar» bo'limidan obuna sotib olishingiz mumkin."


# ─────────────────────────── Ownerga ───────────────────────────

async def notify_owner(bot, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await bot.send_message(settings.owner_id, text, reply_markup=kb)
    except Exception as ex:  # noqa: BLE001 — owner botni bloklagan bo'lishi mumkin
        log.warning("Ownerga xabar yuborilmadi: %s", type(ex).__name__)


def _order_line(o: TopupOrder, user: User | None = None) -> str:
    who = f"@{o.username}" if o.username else f"ID {o.telegram_chat_id}"
    return (f"• #{o.id} · {money(o.payment_amount)} · {html.escape(who)} · "
            f"{topup.to_tashkent(o.created_at)} · {o.status}")


def candidate_kb(order_ids: list[int], credit_id: int | None) -> InlineKeyboardMarkup:
    rows = []
    for oid in order_ids[:5]:
        suffix = f":{credit_id}" if credit_id else ""
        rows.append([InlineKeyboardButton(text=f"✅ Tasdiqlash #{oid}", callback_data=f"pay:adm_ok:{oid}{suffix}"),
                     InlineKeyboardButton(text=f"❌ Rad etish #{oid}", callback_data=f"pay:adm_no:{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def report_paid(bot, order: TopupOrder, balance: int | None, source: str) -> None:
    """Mijozga muvaffaqiyat xabari + ownerga to'lov hisoboti."""
    try:
        await bot.send_message(order.telegram_chat_id, paid_text(order, balance))
    except Exception as ex:  # noqa: BLE001 — mijoz botni bloklagan
        log.info("Mijozga to'lov xabari yuborilmadi: %s", type(ex).__name__)
    who = f"@{order.username}" if order.username else f"ID {order.telegram_chat_id}"
    from services import alerts
    await alerts.broadcast(bot, (
        f"💰 <b>To'lov qabul qilindi</b> · #{order.id}\n"
        f"👤 {html.escape(who)} (<code>{order.telegram_chat_id}</code>)\n"
        f"💵 {money(order.payment_amount)} (asosiy {money(order.base_amount)})\n"
        f"🔌 {html.escape(source)} · {topup.to_tashkent(order.paid_at)}"), owner_only=True)
    from services import feed
    await feed.topup(bot, order.telegram_chat_id, order.payment_amount, f"TOP-{order.id}", order.username, order.paid_at)


async def process_incoming(bot, source: str, source_msg_id: str, text: str, provider: str = "card") -> topup.Outcome:
    """Kirim xabarini qayta ishlaydi va natijaga qarab xabarlarni yuboradi (CardXabar va SMS uchun bir xil)."""
    async with SessionMaker() as s:
        out = await topup.handle_incoming(s, source, source_msg_id, text, provider)
        if out.kind == "matched" and out.order:
            await report_paid(bot, out.order, out.result.balance if out.result else None, f"{provider}:{source}")
        elif out.kind in ("candidate", "late") and out.credit and out.candidates:
            head = ("⚠️ <b>Bir nechta mos buyurtma / avto-tasdiq o'chiq</b>" if out.kind == "candidate"
                    else "⏰ <b>To'lov KECH tushdi</b> (buyurtma muddati tugagan)")
            body = "\n".join(_order_line(o) for o in out.candidates[:5])
            await notify_owner(bot, (
                f"{head}\n\n💵 Kelgan summa: <b>{money(out.credit.amount)}</b>\n{body}\n\n"
                f"Xabar: <i>{html.escape(out.credit.text[:160])}</i>\n\nQaysi buyurtmani tasdiqlaysiz?"),
                candidate_kb([o.id for o in out.candidates], out.credit.id))
        return out
