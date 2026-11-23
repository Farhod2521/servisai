"""Xaridlar va to'lovlar haqidagi bot xabarlari."""
from __future__ import annotations

import html
import re

from config import settings
from database.models import User
from locales.texts import money, t
from services import canboso


def _steps(guide: str) -> str:
    """Qo'llanma qatorlari — raqamlangan qadamlar (admin yozgan «1)», «-» belgilari olib tashlanadi)."""
    lines = [re.sub(r"^\s*(?:\d+[.)]|[-•*])\s*", "", ln).strip() for ln in guide.splitlines()]
    lines = [html.escape(ln) for ln in lines if ln]
    return "\n".join(f"{i}) {ln}" for i, ln in enumerate(lines, 1)) if len(lines) > 1 else (lines[0] if lines else "")


def order_success_text(lang: str, order, balance: int, guides: dict[int, str] | None = None,
                       warranties: dict[int, str] | None = None, support: str | None = None) -> str:
    """Buyurtma natijasi: yetkazilgan kodlar, qaytarilgan mablag', qo'lda bajariladiganlar."""
    blocks: list[str] = []
    manual = False
    for item in order.items:
        name = html.escape(item.product_name)
        if item.status == "failed":
            blocks.append(f"❌ <b>{name}</b> — {t(lang, 'item_failed')}")
        elif item.delivered_content:
            blocks.append(f"📄 <b>{name}</b>\n<code>{html.escape(item.delivered_content)}</code>")
        else:
            manual = True
    for guide in dict.fromkeys(  # admin yozgan qo'llanma (har biri bir martadan)
        (guides or {}).get(i.product_id) for i in order.items if i.status != "failed"
    ):
        if guide:
            blocks.append(f"{t(lang, 'guide_title')}\n{_steps(guide)}")
    for note in dict.fromkeys(      # kafolat matni (har biri bir martadan) + murojaat yo'li
        (warranties or {}).get(i.product_id) for i in order.items if i.status != "failed"
    ):
        if note:
            blocks.append(f"🛡 <b>Kafolat:</b> {html.escape(note)}\n<i>Muammo chiqsa: «Yordam» bo'limi orqali administratorga yozing.</i>")
    if support and any(i.status != "failed" for i in order.items):
        blocks.append(f"❓ Qo'llanmaga tushunmasangiz @{html.escape(support.lstrip('@'))} ga yozing.")
    delivery = "\n\n".join(blocks)
    if manual:
        delivery = (delivery + "\n\n" + t(lang, "order_manual_note")).strip()
    if all(i.status == "failed" for i in order.items):
        return t(lang, "order_failed", balance=money(balance), delivery=delivery)
    return t(
        lang, "order_success", order_id=order.id,
        total=money(order.total), balance=money(balance), delivery=delivery,
    )


def _cost_of(item, prod) -> int | None:
    """Mahsulotning ta'minotchidagi tannarxi (so'm) × soni. Noma'lum bo'lsa None."""
    sp = getattr(prod, "supplier_price", None) if prod else None
    return int(sp) * item.qty if sp else None


async def sale_report(order) -> dict:
    """Savdo foydasi: har bir mahsulot bo'yicha tannarx va foyda + bugungi jami (Toshkent vaqti bilan)."""
    from datetime import datetime, timedelta

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from database.db import SessionMaker
    from database.models import Order as OrderModel, OrderStatus, Product

    def split(o, prods):
        revenue = cost = unknown = 0
        rows = []
        for it in o.items:
            if it.status == "failed":
                continue
            total = it.price * it.qty
            c = _cost_of(it, prods.get(it.product_id))
            revenue += total
            if c is None:
                unknown += 1
            else:
                cost += c
            rows.append((it, total, c))
        return revenue, cost, unknown, rows

    async with SessionMaker() as s:
        pids = {i.product_id for i in order.items if i.product_id}
        prods = {p.id: p for p in await s.scalars(select(Product).where(Product.id.in_(pids)))} if pids else {}
        revenue, cost, unknown, rows = split(order, prods)
        day = (datetime.utcnow() + timedelta(hours=5)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=5)
        todays = list(await s.scalars(
            select(OrderModel).options(selectinload(OrderModel.items))
            .where(OrderModel.created_at >= day, OrderModel.status.in_([OrderStatus.DELIVERED, OrderStatus.PAID]))))
        allp = {p.id: p for p in await s.scalars(select(Product).where(Product.id.in_(
            {i.product_id for o in todays for i in o.items if i.product_id})))} if todays else {}
        t_rev = t_profit = 0
        for o in todays:
            r, c, _, _ = split(o, allp)
            t_rev += r
            t_profit += r - c
    return {"revenue": revenue, "cost": cost, "unknown": unknown, "rows": rows,
            "today_n": len(todays), "today_rev": t_rev, "today_profit": t_profit}


def sale_text(user: User, order, rep: dict) -> str:
    lines = [f"🛒 <b>Yangi savdo #{order.id}</b>",
             f"👤 {html.escape(user.full_name)} (<code>{user.tg_id}</code>)" + (f" @{html.escape(user.username)}" if user.username else "")]
    for it, total, c in rep["rows"]:
        tail = f"tannarx {money(c)} → <b>+{money(total - c)}</b>" if c is not None else "tannarx noma'lum"
        lines.append(f"• {html.escape(it.product_name)} × {it.qty} — {money(total)} ({tail})")
    lines.append(f"\n💵 Jami: <b>{money(rep['revenue'])}</b>")
    if rep["cost"] or not rep["unknown"]:
        lines.append(f"📈 <b>Foyda: +{money(rep['revenue'] - rep['cost'])}</b>"
                     + (f" ({rep['unknown']} ta mahsulotning tannarxi noma'lum)" if rep["unknown"] else ""))
    lines.append(f"📊 Bugun: <b>{rep['today_n']}</b> ta savdo · aylanma {money(rep['today_rev'])} · foyda <b>+{money(rep['today_profit'])}</b>")
    return "\n".join(lines)


async def notify_admins_order(bot, user: User, order) -> None:
    from services import alerts
    try:
        text = sale_text(user, order, await sale_report(order))
    except Exception:  # noqa: BLE001 — hisob xatosi xabarni to'xtatmasin: eskicha qisqa matn
        text = (f"🧾 <b>Yangi buyurtma #{order.id}</b>\n👤 {html.escape(user.full_name)} (<code>{user.tg_id}</code>)\n"
                f"💵 {money(order.total)}\n" + "\n".join(f"• {html.escape(i.product_name)} × {i.qty}" for i in order.items))
    try:
        bal = await canboso.balance_line()
        text += f"\n{bal}" if bal else ""
    except Exception:  # noqa: BLE001 — hamyon so'rovi xabarni to'xtatmasin
        pass
    await alerts.broadcast(bot, text)
    from services import feed
    await feed.sale(bot, user, order)           # mijozning do'kon kanali (FEED_CHAT_ID), foyda ko'rsatilmaydi


async def notify_admins_payment(bot, user: User, payment, provider) -> None:
    text = (
        f"💳 <b>To'lov so'rovi #{payment.id}</b>\n"
        f"👤 {html.escape(user.full_name)} (<code>{user.tg_id}</code>)\n"
        f"💵 {money(payment.amount)}\n"
        f"🏦 {provider.title}\n\n"
        f"Tasdiqlash: <code>/approve {payment.id}</code>"
    )
    for admin_id in settings.admins:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            pass
