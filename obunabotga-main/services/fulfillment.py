"""Buyurtmani ta'minotchi orqali bajarish.

Oqim: foydalanuvchi balansidan pul yechiladi (repo.create_order) → shu yerda
ta'minotchi mahsulotlari uchun canboso'dan xarid qilinadi:

  • muvaffaqiyatli  → yetkazilgan ma'lumot (akkaunt, kod...) buyurtmaga yoziladi;
  • xarid O'TMAGAN  → shu mahsulot puli foydalanuvchiga qaytariladi;
  • natija noma'lum → pul QAYTARILMAYDI (xarid o'tgan bo'lishi mumkin), buyurtma
                      "pending" bo'ladi va admin qo'lda tekshirishi uchun xabar oladi.

Har bir xarid noyob Idempotency-Key bilan yuboriladi, shuning uchun qayta urinish
ikki marta sotib olishga olib kelmaydi.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, OrderStatus, Product, User
from services import canboso

log = logging.getLogger("uzshop.fulfill")

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


@dataclass
class Report:
    failed: list[tuple[str, str]] = field(default_factory=list)    # (mahsulot, sabab)
    unknown: list[tuple[str, str]] = field(default_factory=list)   # (mahsulot, sabab)
    refunded: int = 0

    @property
    def problems(self) -> bool:
        return bool(self.failed or self.unknown)


# ─────────────────────────── Kiritilgan ma'lumotni tekshirish ───────────────────────────

def needs_input(product: Product) -> str | None:
    """'email' | 'accounts' | None — xarid paytida foydalanuvchidan nima so'raladi."""
    if not canboso.is_supplier_product(product):
        return None
    return canboso.product_meta(product).get("need")


def clean_extras(product: Product, qty: int, email: str | None, accounts: list | None) -> dict:
    """Mahsulot talab qilgan email/akkauntlarni tekshiradi. Xato bo'lsa ValueError (o'zbekcha)."""
    if not canboso.is_supplier_product(product):
        return {}
    meta = canboso.product_meta(product)
    fixed = meta.get("fixed_qty")
    if fixed and qty != fixed:
        raise ValueError(f"Bu mahsulotdan bir martada faqat {fixed} ta olish mumkin.")
    need = meta.get("need")
    if need == "email":
        email = (email or "").strip()
        if not _EMAIL.match(email):
            raise ValueError("To'g'ri email manzil kiriting.")
        return {"email": email}
    if need == "accounts":
        rows = [str(a).strip() for a in (accounts or []) if str(a).strip()]
        if len(rows) != qty:
            raise ValueError(f"{qty} ta akkaunt kiriting (har qatorga bittadan).")
        if any(len(r) < 3 or len(r) > 200 for r in rows):
            raise ValueError("Akkaunt ma'lumoti noto'g'ri.")
        return {"accounts": rows}
    return {}


# ─────────────────────────── Bajarish ───────────────────────────

async def fulfill(
    s: AsyncSession, user: User, order: Order, extras: dict[int, dict] | None = None
) -> Report:
    extras = extras or {}
    rep = Report()

    for item in order.items:
        product = await s.get(Product, item.product_id) if item.product_id else None
        if not product or not canboso.is_supplier_product(product):
            continue
        ex = extras.get(item.product_id, {})
        item.customer_input = ex.get("email") or "\n".join(ex.get("accounts") or []) or None
        res = await canboso.purchase(
            product.external_id, item.qty, f"uzshop-o{order.id}-i{item.id}",
            email=ex.get("email"), accounts=ex.get("accounts"),
        )
        item.supplier_ref = (res.order_code or "")[:64] or None
        if res.kind == "ok":
            item.delivered_content = res.content
            item.status = "ok" if res.completed else "pending"
        elif res.kind == "failed":
            refund = item.price * item.qty
            user.balance += refund
            order.total -= refund
            item.status = "failed"
            item.delivered_content = ""
            rep.refunded += refund
            rep.failed.append((item.product_name, res.message))
            log.warning("Ta'minotchi xaridni rad etdi (order %s): %s", order.id, res.message)
        else:
            item.status = "pending"
            rep.unknown.append((item.product_name, res.message))
            log.error("Ta'minotchi natijasi noma'lum (order %s): %s", order.id, res.message)

    live = [i for i in order.items if i.status != "failed"]
    if not live:
        order.status = OrderStatus.CANCELLED
    elif all(i.status == "ok" and i.delivered_content for i in live):
        order.status = OrderStatus.DELIVERED
    else:
        order.status = OrderStatus.PAID
    await s.commit()
    return rep


async def alert_admins(bot, user: User, order: Order, rep: Report) -> None:
    """Muammo bo'lsa (rad etildi / noma'lum) adminlarga xabar."""
    if not rep.problems:
        return
    lines = [f"⚠️ <b>Ta'minotchi bilan muammo — buyurtma #{order.id}</b>",
             f"👤 {html.escape(user.full_name)} (<code>{user.tg_id}</code>)"]
    for name, why in rep.failed:
        lines.append(f"❌ {html.escape(name)}: {html.escape(why or '—')}\n   Mijoz puli qaytarildi.")
    for name, why in rep.unknown:
        lines.append(f"❓ {html.escape(name)}: natija noma'lum ({html.escape(why or '—')})\n"
                     "   Pul qaytarilmadi — ta'minotchi panelida buyurtmani tekshiring.")
    if any("balance" in (w or "").lower() or "wallet" in (w or "").lower() for _, w in rep.failed):
        lines.append("\n💳 Ta'minotchidagi hamyon yetarli emas — uni to'ldiring.")
    from services import alerts
    await alerts.broadcast(bot, "\n".join(lines))

