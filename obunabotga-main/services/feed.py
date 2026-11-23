"""Do'kon xabarlari kanali: faqat SOTUV va BALANS TO'LDIRISH haqida xabar (yangi mijoz xabari yo'q).

Kanal ID si FEED_CHAT_ID env da (bot kanalda admin bo'lishi kerak). Bo'sh bo'lsa — hech narsa yuborilmaydi.
Format mijoz bergan namunaga mos (🎉 OBUNA SOTIB OLINDI / 💵 BALANS TO'LDIRILDI). Foyda va tannarx bu yerda ko'rsatilmaydi.
"""
from __future__ import annotations

import calendar
import html
import logging
import re
from datetime import date, datetime, timedelta

from config import settings
from locales.texts import money

log = logging.getLogger("uzshop.feed")
TZ = timedelta(hours=5)


def enabled() -> bool:
    return bool((settings.feed_chat_id or "").strip())


def _chat():
    v = settings.feed_chat_id.strip()
    return int(v) if v.lstrip("-").isdigit() else v


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def expiry(start: datetime, name: str) -> str:
    """«GPT Go 1 oy» → «07.10.2026 → 07.11.2026». Muddat nomda bo'lmasa — bo'sh."""
    m = re.search(r"(?<![\w.])(\d+)\s*(soat|kun|hafta|oy|yil)\b", name or "", re.I)
    if not m:
        return ""
    n, unit = int(m.group(1)), m.group(2).lower()
    d0 = (start + TZ).date()
    d1 = (_add_months(d0, n) if unit == "oy" else _add_months(d0, 12 * n) if unit == "yil"
          else d0 + timedelta(days=n * (7 if unit == "hafta" else 1 if unit == "kun" else 0)))
    if unit == "soat":
        d1 = (start + TZ + timedelta(hours=n)).date()
    return f"{d0:%d.%m.%Y} → {d1:%d.%m.%Y}"


def _who(full_name: str | None, username: str | None) -> str:
    name = html.escape((full_name or "—").strip() or "—")
    return f"{name} | @{html.escape(username)}" if username else name


def _stamp(dt: datetime | None) -> str:
    return f"{((dt or datetime.utcnow()) + TZ):%d.%m.%Y, %H:%M}"


def sale_text(user, order, source: str = "Bot balansi") -> str:
    when = order.created_at or datetime.utcnow()
    items = [i for i in order.items if i.status != "failed"]
    lines = ["🎉 <b>OBUNA SOTIB OLINDI</b>", "",
             f"👤 Foydalanuvchi: {_who(user.full_name, user.username)}",
             f"🆔 Telegram ID: <code>{user.tg_id}</code>", ""]
    for it in items:
        total = it.price * it.qty
        qty = f" × {it.qty}" if it.qty > 1 else ""
        lines.append(f"📦 Obuna: {html.escape(it.product_name)}{qty}")
        lines.append(f"💰 Summa: {money(total)}")
    if len(items) > 1:
        lines.append(f"💵 Jami: {money(sum(i.price * i.qty for i in items))}")
    lines.append(f"💳 To'lov manbasi: {source}")
    spans = [expiry(when, i.product_name) for i in items]
    if any(spans):
        lines.append(f"📅 Amal qilish muddati: {next(s for s in spans if s)}" if len({s for s in spans if s}) == 1
                     else "📅 Amal qilish muddati: " + "; ".join(s or "—" for s in spans))
    lines += ["", f"🧾 Buyurtma: #ORD-{order.id}", f"🕒 {_stamp(when)}"]
    return "\n".join(lines)


def topup_text(full_name: str | None, username: str | None, tg_id: int, amount: int, ref: str, when: datetime | None = None) -> str:
    return "\n".join(["💵 <b>BALANS TO'LDIRILDI</b>", "",
                      f"👤 Foydalanuvchi: {_who(full_name, username)}",
                      f"🆔 Telegram ID: <code>{tg_id}</code>",
                      f"💰 Summa: {money(amount)}", "",
                      f"🧾 Buyurtma: #{ref}", f"🕒 {_stamp(when)}"])


async def _post(bot, text: str) -> bool:
    if not enabled():
        return False
    try:
        await bot.send_message(_chat(), text)
        return True
    except Exception as ex:  # noqa: BLE001 — kanal xatosi savdoni to'xtatmasin
        log.warning("Do'kon kanaliga yuborilmadi (%s): %s", type(ex).__name__, ex)
        return False


async def sale(bot, user, order) -> bool:
    return await _post(bot, sale_text(user, order)) if enabled() else False


async def topup(bot, tg_id: int, amount: int, ref: str, username: str | None = None, when: datetime | None = None) -> bool:
    if not enabled():
        return False
    from sqlalchemy import select

    from database.db import SessionMaker
    from database.models import User
    full = None
    try:
        async with SessionMaker() as s:
            u = await s.scalar(select(User).where(User.tg_id == tg_id))
            full, username = (u.full_name if u else None), (username or (u.username if u else None))
    except Exception:  # noqa: BLE001
        pass
    return await _post(bot, topup_text(full, username, tg_id, amount, ref, when))
