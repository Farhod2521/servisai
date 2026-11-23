"""Hisobot boti: savdo + foyda, yo'naltirish, /start bosmaganlar uchun zaxira yo'li.   Ishga tushirish:  python tests/test_alerts.py"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="11,22", EXTRA_ADMIN_IDS="", TELEGRAM_OWNER_ID="11",
                  DATABASE_URL=f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/t.db", CANBOSO_API_KEY="k")

from config import settings  # noqa: E402
from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Category, DeliveryType, Order, OrderItem, OrderStatus, Product, ProductSource, User  # noqa: E402
from services import alerts, notify  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


class FakeBot:
    def __init__(self, deny: set[int] = frozenset(), name="main"):
        self.sent, self.deny, self.name = [], deny, name

    async def send_message(self, chat_id, text, **kw):
        if chat_id in self.deny:
            raise RuntimeError("Forbidden: bot can't initiate conversation with a user")
        self.sent.append((chat_id, text))

    async def get_me(self):
        class Me:
            username = "obunalar_hisobot_bot"
        return Me()


async def seed():
    await init_db()
    async with SessionMaker() as s:
        c = Category(name_uz="AI", emoji="🤖", sort_order=1)
        s.add(c)
        await s.flush()
        p1 = Product(category_id=c.id, emoji="🤖", name="ChatGPT Plus 1 oy", description="", price=200_000, supplier_price=164_000,
                     delivery_type=DeliveryType.MANUAL, source=ProductSource.API, external_id="cb:1", unlimited=True)
        p2 = Product(category_id=c.id, emoji="🎬", name="CapCut Pro 7 kun", description="", price=12_000, supplier_price=5_000,
                     delivery_type=DeliveryType.MANUAL, source=ProductSource.API, external_id="cb:2", unlimited=True)
        p3 = Product(category_id=c.id, emoji="🧩", name="Qo'lda mahsulot", description="", price=50_000,
                     delivery_type=DeliveryType.MANUAL, unlimited=True)
        u = User(tg_id=777, full_name="Ali Valiyev", username="ali")
        s.add_all([p1, p2, p3, u])
        await s.flush()
        o1 = Order(user_id=u.id, total=200_000, status=OrderStatus.DELIVERED)
        o2 = Order(user_id=u.id, total=24_000, status=OrderStatus.DELIVERED)
        s.add_all([o1, o2])
        await s.flush()
        s.add(OrderItem(order_id=o1.id, product_id=p1.id, product_name=p1.name, price=200_000, qty=1, status="ok"))
        s.add(OrderItem(order_id=o2.id, product_id=p2.id, product_name=p2.name, price=12_000, qty=2, status="ok"))
        await s.commit()
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        o2 = await s.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == o2.id))
        return o2, u, p3


async def main() -> None:
    o2, u, p3 = await seed()
    rep = await notify.sale_report(o2)
    check(rep["revenue"] == 24_000 and rep["cost"] == 10_000, "savdo: aylanma 24 000, tannarx 10 000 (5 000 × 2)")
    check(rep["today_n"] == 2 and rep["today_rev"] == 224_000 and rep["today_profit"] == 36_000 + 14_000, "bugun: 2 ta savdo, foyda 50 000")
    text = notify.sale_text(u, o2, rep)
    check("Yangi savdo" in text and "+14 000" in text and "Foyda" in text and "Bugun" in text and "tannarx" in text, "xabar: foyda +14 000 va bugungi jami ko'rsatilgan")

    # ── 1 / 10 / 30 kunlik hisobot ──
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from services import stats
    async with SessionMaker() as s:
        p1 = await s.scalar(select(Product).where(Product.external_id == "cb:1"))
        u0 = await s.scalar(select(User))
        for age, qty in ((5, 3), (20, 2)):
            o = Order(user_id=u0.id, total=p1.price * qty, status=OrderStatus.DELIVERED, created_at=datetime.utcnow() - timedelta(days=age))
            s.add(o)
            await s.flush()
            s.add(OrderItem(order_id=o.id, product_id=p1.id, product_name=p1.name, price=p1.price, qty=qty, status="ok"))
        await s.commit()
    r1, r10, r30 = await stats.report(1), await stats.report(10), await stats.report(30)
    check((r1["orders"], r10["orders"], r30["orders"]) == (2, 3, 4), "savdolar soni: bugun 2, 10 kunda 3, 30 kunda 4")
    check(r1["profit"] == 50_000 and r10["profit"] == 50_000 + 3 * 36_000 and r30["profit"] == 50_000 + 5 * 36_000, "foyda: 1 kun 50 000, 10 kun +108 000, 30 kun +72 000 yana")
    check(r30["top"][0][0] == "ChatGPT Plus 1 oy" and r30["top"][0][1]["qty"] == 6, "nima ko'p olingan: ChatGPT Plus 1 oy — 6 ta (birinchi o'rinda)")
    txt30 = stats.report_text(r30)
    check("Oxirgi 30 kun" in txt30 and "Nima ko'p olingan" in txt30 and "Kunlar bo'yicha" in txt30 and "ChatGPT Plus 1 oy" in txt30, "30 kunlik hisobot matni: top mahsulotlar va kunlar bo'yicha")
    check("Bugun" in stats.report_text(r1) and "Kunlar bo'yicha" not in stats.report_text(r1), "1 kunlik hisobotda kunlar jadvali yo'q")
    from services import alerts_bot
    secs = alerts_bot._seconds_until_daily(datetime(2026, 10, 6, 17, 0))     # 22:00 Toshkent → 23:55 gacha 1 s 55 daq
    check(abs(secs - 6900) < 1, "kunlik hisobot 23:55 (Toshkent) da yuboriladi")
    check(alerts_bot._seconds_until_daily(datetime(2026, 10, 6, 19, 0)) > 23 * 3600, "23:55 dan keyin — ertangi kunga")

    # tannarxi noma'lum (qo'lda) mahsulot
    from types import SimpleNamespace as NS
    manual = NS(id=9, items=[NS(product_id=p3.id, product_name=p3.name, price=50_000, qty=1, status="ok")])
    r2 = await notify.sale_report(manual)
    check(r2["unknown"] == 1 and "noma'lum" in notify.sale_text(u, manual, r2), "tannarxi noma'lum mahsulot — «noma'lum» deb yoziladi, foyda to'qib chiqarilmaydi")

    # ta'minotchi hamyoni
    from services import canboso
    settings.canboso_api_key = "k"
    async def bal_low(): return 7.5
    async def bal_ok(): return 52.0
    canboso.fetch_balance = bal_low
    line = await canboso.balance_line()
    check("$7.50" in line and "Hamyon kam" in line, "hamyon $10 dan kam — ogohlantirish bilan ko'rsatiladi")
    canboso.fetch_balance = bal_ok
    line = await canboso.balance_line()
    check("$52.00" in line and "kam" not in line, "hamyon yetarli — faqat qoldiq")
    main = FakeBot()
    await notify.notify_admins_order(main, u, o2)
    check(main.sent and "Ta'minotchi hamyoni: <b>$52.00</b>" in main.sent[0][1] and "Foyda" in main.sent[0][1], "har bir savdo xabarida foyda va ta'minotchi hamyoni qoldig'i")
    async def bal_none(): return None
    canboso.fetch_balance = bal_none
    check(await canboso.balance_line() == "", "hamyonni olib bo'lmasa — qator chiqmaydi (xabar to'xtamaydi)")
    settings.canboso_api_key = ""

    # token yo'q: asosiy bot orqali adminlarga (owner + adminlar, takrorsiz)
    check(settings.alert_bot_token == "" and not alerts.enabled(), "token berilmasa — hisobot boti o'chiq")
    main = FakeBot()
    n = await alerts.broadcast(main, "salom")
    check(n == 2 and sorted(c for c, _ in main.sent) == [11, 22] and len(main.sent) == 2, "token yo'q: asosiy bot orqali owner va adminlarga (takrorsiz)")

    # token bor: hisobot boti orqali
    settings.alert_bot_token = "1:FAKE-TEST-TOKEN"
    ab = FakeBot(name="alert")
    alerts._bot = ab
    main = FakeBot()
    n = await alerts.broadcast(main, "🛒 savdo")
    check(n == 2 and len(ab.sent) == 2 and not main.sent, "token bor: xabar hisobot boti orqali, asosiy bot jim")
    # owner_only
    ab.sent.clear()
    await alerts.broadcast(main, "💰 to'lov", owner_only=True)
    check([c for c, _ in ab.sent] == [11], "to'lov hisobotlari — faqat owner ga")

    # /start bosmagan admin: asosiy bot orqali + ulash havolasi (bir marta)
    ab = FakeBot(deny={22}, name="alert")
    alerts._bot = ab
    main = FakeBot()
    n = await alerts.broadcast(main, "🛒 savdo")
    check([c for c, _ in ab.sent] == [11] and [c for c, _ in main.sent] == [22], "/start bosmagan admin: xabar asosiy bot orqali boradi (yo'qolmaydi)")
    check("t.me/obunalar_hisobot_bot" in main.sent[0][1], "ulanish havolasi yuboriladi")
    main2 = FakeBot()
    await alerts.broadcast(main2, "🛒 yana")
    check("t.me/obunalar_hisobot_bot" not in main2.sent[0][1], "havola har xabarda takrorlanmaydi")

    # qo'shimcha guruh
    settings.alert_chat_id = "-1001234567890"
    ab = FakeBot(name="alert")
    alerts._bot = ab
    await alerts.broadcast(FakeBot(), "x")
    check(any(c == -1001234567890 for c, _ in ab.sent), "ixtiyoriy guruh/kanalga ham yuboriladi")
    settings.alert_chat_id = ""
    settings.alert_bot_token = ""
    alerts._bot = None

    # hisobot botining webhook yo'li: secret'siz so'rov rad etiladi
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    settings.alert_bot_token = "123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678"
    app = web.Application()
    alerts_bot.setup(app)
    async with TestClient(TestServer(app)) as cl:
        r = await cl.post(alerts_bot.path(), json={"update_id": 1})
        check(r.status == 401, "hisobot boti webhooki: secret tokensiz so'rov rad etiladi (401)")
        r = await cl.post("/alert/yoq", json={"update_id": 1})
        check(r.status == 404, "boshqa yo'l — 404")
    settings.alert_bot_token = ""
    alerts._bot = None
    print("\n✅ Hisobot boti testlari o'tdi")


asyncio.run(main())
