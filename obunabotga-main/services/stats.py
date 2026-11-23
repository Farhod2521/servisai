"""Savdo hisoboti: oxirgi 1 / 10 / 30 kun — nechta savdo, nima ko'p olingan, qancha tushum va FOYDA.

Kunlar Toshkent vaqti bilan (UTC+5): «1 kun» — bugun 00:00 dan, «10 kun» — oxirgi 10 kun (bugun ham).
Foyda = sotuv narxi − ta'minotchi tannarxi (mahsulotning hozirgi tannarxi). Tannarxi noma'lum mahsulotlar alohida aytiladi.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database.db import SessionMaker
from database.models import Order, OrderStatus, Payment, PaymentStatus, Product, User
from locales.texts import money

TZ = timedelta(hours=5)
PERIODS = (1, 10, 30)


def day_start_utc(days: int, now: datetime | None = None) -> datetime:
    """`days` kunlik oynaning boshi (UTC): Toshkentdagi bugungi yarim tundan (days-1) kun oldin."""
    local = (now or datetime.utcnow()) + TZ
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days - 1) - TZ


async def report(days: int, now: datetime | None = None) -> dict:
    start = day_start_utc(days, now)
    async with SessionMaker() as s:
        orders = list(await s.scalars(
            select(Order).options(selectinload(Order.items))
            .where(Order.created_at >= start, Order.status.in_([OrderStatus.DELIVERED, OrderStatus.PAID]))))
        pids = {i.product_id for o in orders for i in o.items if i.product_id}
        prods = {p.id: p for p in await s.scalars(select(Product).where(Product.id.in_(pids)))} if pids else {}
        deposits = await s.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.PAID, Payment.created_at >= start)) or 0
        new_users = await s.scalar(select(func.count(User.id)).where(User.created_at >= start)) or 0

    per: dict[str, dict] = {}
    by_day: dict[str, dict] = {}
    unknown = units = 0
    revenue = cost = 0
    for o in orders:
        day = ((o.created_at or start) + TZ).strftime("%d.%m")
        d = by_day.setdefault(day, {"n": 0, "profit": 0})
        d["n"] += 1
        for it in o.items:
            if it.status == "failed":
                continue
            total = it.price * it.qty
            sp = getattr(prods.get(it.product_id), "supplier_price", None)
            c = int(sp) * it.qty if sp else None
            row = per.setdefault(it.product_name, {"qty": 0, "revenue": 0, "profit": 0, "unknown": False})
            row["qty"] += it.qty
            row["revenue"] += total
            units += it.qty
            revenue += total
            if c is None:
                unknown += 1
                row["unknown"] = True
            else:
                cost += c
                row["profit"] += total - c
                d["profit"] += total - c
    top = sorted(per.items(), key=lambda kv: (-kv[1]["qty"], -kv[1]["revenue"]))
    return {"days": days, "orders": len(orders), "units": units, "revenue": revenue, "cost": cost,
            "profit": revenue - cost, "unknown": unknown, "top": top, "by_day": by_day,
            "deposits": int(deposits), "new_users": int(new_users)}


def title(days: int) -> str:
    return "Bugun" if days == 1 else f"Oxirgi {days} kun"


def report_text(rep: dict, top_n: int = 12) -> str:
    days = rep["days"]
    lines = [f"📈 <b>Savdo hisoboti — {title(days)}</b>", ""]
    if not rep["orders"]:
        lines.append("Bu davrda savdo bo'lmadi.")
    else:
        lines += [
            f"🛒 Savdolar: <b>{rep['orders']}</b> ta ({rep['units']} dona)",
            f"💵 Aylanma: <b>{money(rep['revenue'])}</b>",
            f"📈 Foyda: <b>+{money(rep['profit'])}</b>"
            + (f" ({rep['unknown']} ta mahsulotning tannarxi noma'lum)" if rep["unknown"] else ""),
        ]
    lines += [f"👥 Yangi mijozlar: <b>{rep['new_users']}</b>", f"💳 Hamyon to'ldirishlar: <b>{money(rep['deposits'])}</b>"]
    if rep["top"]:
        lines += ["", "🔥 <b>Nima ko'p olingan:</b>"]
        for i, (name, r) in enumerate(rep["top"][:top_n], 1):
            profit = f" · +{money(r['profit'])}" if not r["unknown"] else " · foyda noma'lum"
            lines.append(f"{i}. {html.escape(name)} — <b>{r['qty']}</b> ta · {money(r['revenue'])}{profit}")
        if len(rep["top"]) > top_n:
            lines.append(f"… yana {len(rep['top']) - top_n} xil mahsulot")
    if days > 1 and rep["by_day"]:
        lines += ["", "📅 <b>Kunlar bo'yicha:</b>"]
        items = sorted(rep["by_day"].items(), key=lambda kv: (kv[0][3:], kv[0][:2]))
        for day, d in items[-10:]:
            lines.append(f"{day} — {d['n']} ta · +{money(d['profit'])}")
        if len(items) > 10:
            lines.append(f"(oxirgi 10 kun ko'rsatildi; jami {len(items)} kun savdo bor)")
    return "\n".join(lines)[:4000]
