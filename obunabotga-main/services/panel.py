"""Admin bosh sahifasi: bugungi ko'rsatkichlar bir qarashda. Hammasi bitta xabarda."""
from __future__ import annotations

import asyncio
import html
import os
import time
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Order, OrderStatus, TopupOrder, User
from locales.texts import money
from services import canboso, runtime, stats
from services.emoji import e as emoji_html

TZ = timedelta(hours=5)
_wallet: tuple[float, float | None] = (0.0, None)        # (vaqt, USD qoldiq) — 60 soniya keshlanadi


async def supplier_wallet() -> float | None:
    """Ta'minotchi hamyoni (USD). Sekin bo'lsa ham bosh sahifani kutdirmaydi (2.5 soniya)."""
    global _wallet
    if not settings.canboso_api_key:
        return None
    ts, val = _wallet
    if time.monotonic() - ts < 60:
        return val
    try:
        val = await asyncio.wait_for(canboso.fetch_balance(), 2.5)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        val = None
    _wallet = (time.monotonic(), val)
    return val


_su: tuple[float, int | None] = (0.0, None)


async def starsuno_balance() -> float | None:
    """Fragment hamyonidagi TON, 60 soniya keshlanadi; sekin bo'lsa bosh sahifani kutdirmaydi."""
    global _su
    from services import fragment_tg
    ts, val = _su
    if time.monotonic() - ts < 60:
        return val
    try:
        val = await asyncio.wait_for(fragment_tg.wallet_ton(), 2.5)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        val = None
    _su = (time.monotonic(), val)
    return val
    try:
        val = await asyncio.wait_for(starsuno.fetch_balance(), 2.5)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        val = None
    _su = (time.monotonic(), val)
    return val


async def counts(s: AsyncSession) -> dict:
    """Diqqat talab qiladigan sonlar: bajarilmagan buyurtmalar, kutilayotgan to'lovlar, jami mijozlar."""
    pending = await s.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PAID)) or 0
    topups = await s.scalar(select(func.count(TopupOrder.id)).where(TopupOrder.status == "pending")) or 0
    users = await s.scalar(select(func.count(User.id))) or 0
    return {"pending": int(pending), "topups": int(topups), "users": int(users)}


async def catalog_block(s: AsyncSession) -> str:
    """Obunalar ta'minotchidan yuklanyaptimi: kalit, oxirgi yangilanish, xato, nechta obuna mavjud."""
    from handlers.shop import SERVICES, availability
    from services.catalog_sync import STATUS
    avail = await availability(s)
    _upd = emoji_html("🔄", runtime.LAST_UPDATE_EMOJI)       # «Oxirgi yangilanish» belgisi (premium)
    have = sum(1 for b in SERVICES if avail.get(b))
    lines = [f"📦 <b>Katalog</b>: obunalar <b>{have}/{len(SERVICES)}</b> mavjud"]
    if not settings.canboso_api_key:
        lines.append("⚠️ <b>CANBOSO_API_KEY kiritilmagan</b> — obunalar yuklanmaydi. Render → Environment ga qo'shing.")
        return "\n".join(lines)
    if STATUS.get("last_ok"):
        t = (STATUS["last_ok"] + TZ).strftime("%H:%M")
        lines.append(f"{_upd} Oxirgi yangilanish: {t} · ta'minotchida {STATUS.get('seen', 0)} ta mahsulot")
    elif STATUS.get("last_try"):
        lines.append(f"{_upd} Katalog hali bir marta ham yuklanmadi")
    else:
        lines.append(f"{_upd} Katalog yuklanmoqda (bot ishga tushganidan ~20 soniya keyin)...")
    if STATUS.get("last_error"):
        lines.append(f"⚠️ Oxirgi xato: <code>{html.escape(STATUS['last_error'][:200])}</code>")
    missing = [b for b in SERVICES if not avail.get(b)]
    if missing and STATUS.get("last_ok"):
        lines.append("🔴 Hozir yo'q: " + ", ".join(missing))
    return "\n".join(lines)


def db_block() -> str:
    """Baza holati: doimiy (Postgres) bo'lsa ma'lumot yo'qolmaydi; Render'da SQLite bo'lsa ogohlantiradi va zaxira vaqtini ko'rsatadi."""
    from services import backup
    if settings.is_postgres:
        return "🗄 Baza: doimiy (Postgres) ✅ — yangilanganda ma'lumot yo'qolmaydi"
    if not os.environ.get("RENDER"):
        d = backup.local_dir()                       # kompyuterda: baza fayli doimiy + «zaxira» papkasidagi nusxalar
        files = sorted(d.glob(f"{backup.LOCAL_PREFIX}-*.json.gz")) if d and d.is_dir() else []
        if not files:
            return "💾 Zaxira: hali yozilmagan (birinchi o'zgarishdan keyin «zaxira» papkasida paydo bo'ladi)"
        last = datetime.fromtimestamp(files[-1].stat().st_mtime).strftime("%d.%m %H:%M")
        return f"💾 Zaxira: «zaxira» papkasida {len(files)} ta nusxa · oxirgisi {last} · Telegram chatingizda ham pinlangan"
    last = backup.STATE.get("last_upload")
    t = (last + TZ).strftime("%H:%M") if last else "hali yo'q"
    return ("⚠️ <b>Baza vaqtinchalik (SQLite)</b>: Render yangilanganda mijozlar va balanslar yo'qolishi mumkin!\n"
            "Hal qilish: Render → Environment → <code>DATABASE_URL</code> ga doimiy Postgres (neon.tech) ulang.\n"
            f"💾 Oxirgi zaxira: {t} (Telegram chatingizda pinlangan fayl; /zaxira)")


async def home_view(s: AsyncSession) -> tuple[str, dict]:
    """(bosh sahifa matni, tugmalar uchun sonlar)."""
    c = await counts(s)
    today = await stats.report(1)
    now = (datetime.utcnow() + TZ).strftime("%d.%m.%Y %H:%M")
    lines = [
        "🎛 <b>Boshqaruv markazi</b>",
        f"<i>{now}</i>",
        "",
        "📅 <b>Bugun</b>",
        f"🛒 Savdo: <b>{today['orders']}</b> ta · {money(today['revenue'])}",
        f"📈 Foyda: <b>+{money(today['profit'])}</b>",
        f"💳 Hamyon to'ldirish: {money(today['deposits'])}",
        f"👥 Yangi mijoz: <b>{today['new_users']}</b>  (jami {c['users']})",
    ]
    lines += ["", await catalog_block(s)]
    if db_block():
        lines += ["", db_block()]
    alerts = []
    if c["pending"]:
        alerts.append(f"🧾 Bajarilmagan buyurtma: <b>{c['pending']}</b>")
    if c["topups"]:
        alerts.append(f"⏳ Kutilayotgan to'lov: <b>{c['topups']}</b>")
    wallet = await supplier_wallet()
    if wallet is not None:
        warn = "  ⚠️ <b>kam, to'ldiring!</b>" if wallet < settings.supplier_low_usd else ""
        alerts.append(f"💼 Ta'minotchi hamyoni: <b>${wallet:,.2f}</b>{warn}")
    from services import fragment_tg
    if fragment_tg.configured():
        ton = await starsuno_balance()
        if ton is not None:
            warn = "  ⚠️ <b>kam, to'ldiring!</b>" if ton < 2 else ""
            alerts.append(f"⭐ Fragment hamyoni: <b>{ton:g} TON</b>{warn}")
    lines += ["", "⚡ <b>Diqqat</b>"] + alerts if alerts else []
    lines += ["", "Kerakli bo'limni tanlang 👇"]
    return "\n".join(lines), c


# Bo'limlar: kalit → (sarlavha, qisqa tushuntirish, [(tugma, callback), ...]). Tugmalar 2 tadan joylashadi.
SECTIONS: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    "shop": ("🛍 Obunalar", "Mahsulotlarni ko'rish, qo'shish, yoqish/o'chirish, zaxira va katalog.", [
        ("📦 Mahsulotlar", "a:prods"), ("📂 Bo'limlar", "a:cats"),
        ("➕ Mahsulot qo'shish", "a:prod_add"), ("➕ Bo'lim qo'shish", "a:cat_add"),
        ("🌐 API'dan qo'shish", "a:api:0:-1"), ("📋 Qo'shilganlar", "a:apix"),
        ("🔄 Katalogni yangilash", "a:sync"), ("🏷 Brend emojilari", "a:bemoji"),
    ]),
    "price": ("💰 Narx va foyda", "Sotuv narxlari qanday hisoblanishi: foyda, dollar kursi, ustama.", [
        ("💰 Narxlar", "a:prices"), ("💹 Foyda foizi", "a:markup"),
        ("💱 USD kursi", "a:rate"), ("🧮 Ustama jadvali", "a:tiers"),
        ("📈 Narx o'zgarishlari", "a:pchg:24:0"), ("🏷 Brend foizlari", "a:bm"),
    ]),
    "tg": ("⭐ Stars / Premium", "Telegram Stars va Premium (Fragment): hamyon, narxlar, ustama foizi.", [
        ("📊 Holat va narxlar", "a:tg"), ("💹 Ustama foizi", "a:tgm"),
    ]),
    "pay": ("💳 To'lovlar", "Karta, kelgan to'lovlar va avtomatik tasdiqlash.", [
        ("💳 To'lov sozlamalari", "a:pay"), ("📋 To'lovlar ro'yxati", "pay:adm_list"),
        ("📊 To'lov statistikasi", "pay:adm_stats"), ("🔎 Tekshiruv", "pay:adm_diag"),
    ]),
    "msg": ("📣 Xabarlar", "Mijozlarga xabar yuborish va avtomatik xabarlar.", [
        ("📢 Hammaga xabar", "a:bc"), ("🔔 Yangi obuna xabari", "a:notify"),
        ("👋 /start matni", "a:welcome"),
    ]),
    "report": ("📊 Hisobotlar", "Savdo, foyda va eng ko'p olingan obunalar.", [
        ("📈 Bugun", "a:sale:1"), ("📈 10 kun", "a:sale:10"),
        ("📈 30 kun", "a:sale:30"), ("📊 Umumiy hisob", "a:stats"),
    ]),
    "settings": ("⚙️ Sozlamalar", "Yordam, premium emoji va boshqa sozlamalar.", [
        ("🆘 Yordam (username)", "a:support"), ("😀 Premium emoji", "a:emoji"),
        ("🏷 Brend emojilari", "a:bemoji"), ("👋 /start matni", "a:welcome"),
    ]),
}


def section_text(key: str) -> str:
    title, hint, _ = SECTIONS[key]
    return f"<b>{title}</b>\n<i>{html.escape(hint)}</i>"
