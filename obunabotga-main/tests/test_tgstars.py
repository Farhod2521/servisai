"""Telegram Stars / Premium: xarid oqimi (mijoz → pul yechish/qaytarish → admin xabari). Manba — Fragment;
bu yerda Fragment o'rniga soxta javoblar beradigan mijoz ishlatiladi (narx/natija hisob-kitobi bir xil).

Ishga tushirish:  python tests/test_tgstars.py   (internet va haqiqiy kalit shart emas)
Tekshiriladi: muvaffaqiyat, aniq rad (pul qaytadi), noma'lum natija (pul QAYTMAYDI, qayta urinish yo'q), balans yetmasligi,
username tekshiruvi, narx + ustama, «Obunalar» ro'yxatida tugmalar.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(
    BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678",
    ADMIN_IDS="1",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db",
    STARSUNO_KEY="test-key-123",
)

from sqlalchemy import select  # noqa: E402

from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Order, OrderStatus  # noqa: E402
from handlers import tgstars  # noqa: E402
from handlers.shop import services_kb  # noqa: E402
from services import fragment_tg, repo, runtime, starsuno  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


CALLS: list[tuple[str, dict]] = []
REPLY: dict = {}


async def fake_get(path: str, **params):
    CALLS.append((path, params))
    r = REPLY.get(path)
    if isinstance(r, Exception):
        raise r
    return r


class FakeMsg:
    def __init__(self):
        self.texts: list[str] = []
        self.bot = None

    async def edit_text(self, text, reply_markup=None):
        self.texts.append(text)

    async def answer(self, text, reply_markup=None):
        self.texts.append(text)


async def run(kind, qty, target, balance=1_000_000):
    CALLS.clear()
    async with SessionMaker() as s:
        u = await repo.get_or_create_user(s, 555, "Test", "tester")
        u.balance = balance
        await s.commit()
        msg = FakeMsg()
        price = await tgstars._quote(kind, qty)
        await tgstars._execute(msg, s, u, "uz", kind, qty, target, price)
        order = await s.scalar(select(Order).order_by(Order.id.desc()))
        return u.balance, order, msg, price


async def _low_ton():
    return 1.0


async def main() -> None:
    await init_db()
    starsuno._get = fake_get
    # Fragment o'rniga — soxta javoblar beradigan mijoz (internetsiz); hamyonda 1 TON (kam)
    fragment_tg.configured = lambda: True
    fragment_tg.star_unit_price, fragment_tg.premium_prices = starsuno.star_unit_price, starsuno.premium_prices
    fragment_tg.buy_stars, fragment_tg.buy_premium = starsuno.buy_stars, starsuno.buy_premium
    fragment_tg.fetch_balance, fragment_tg.wallet_ton = starsuno.fetch_balance, _low_ton
    alerts_sent: list[str] = []

    async def fake_alert(bot, text):
        alerts_sent.append(text)
    tgstars._alert = fake_alert

    REPLY["stars/price"] = {"ok": True, "price": 250, "currency": "so'm"}
    REPLY["premium/price"] = {"ok": True, "prices": {"3": 170000, "6": 220000, "12": 390000}, "currency": "so'm"}
    REPLY["balance"] = {"ok": True, "balance": 100000, "currency": "so'm"}

    # 1) username
    v = starsuno.valid_username
    check(v("@monk_1") == "monk_1" and v("https://t.me/Monk99/") == "Monk99" and v("ab") is None and v("a b cde") is None
          and v("1abcde") is None and v("") is None, "username: @ va havola olinadi, yaroqsizi rad etiladi")

    # 2) narx + ustama (sukut 10%), yaxlitlash 100 so'mgacha
    check(await starsuno.stars_price(100) == 27500 and await starsuno.premium_price(3) == 187000,
          "narx: 100 Stars=27 500, Premium 3 oy=187 000 (tannarx + 10%)")
    await runtime.set_value("tg_markup", "20")
    check(await starsuno.stars_price(100) == 30000 and await starsuno.premium_price(12) == 468000, "ustama 20% ga o'zgarsa narx ham o'zgaradi")
    await runtime.set_value("tg_markup", "10")
    check(await starsuno.fetch_balance() == 100000, "StarsUno balansi o'qiladi")

    # 3) muvaffaqiyatli Stars xaridi
    REPLY["stars/buy"] = {"ok": True, "message": "Yulduz muvaffaqiyatli yuborildi!", "balance": 50000}
    bal, order, msg, price = await run("stars", 100, "monk")
    check(CALLS[-1] == ("stars/buy", {"username": "monk", "amount": 100}), "so'rov: username @siz, amount to'g'ri")
    check(bal == 1_000_000 - price and order.status == OrderStatus.DELIVERED and order.items[0].status == "ok", "pul yechildi, buyurtma bajarildi")
    check("Yuborildi" in msg.texts[-1], "mijozga «Yuborildi» xabari")
    check(any("Savdo" in a for a in alerts_sent) and any("TON kam" in a for a in alerts_sent),
          "adminga savdo xabari va Fragment hamyonida TON kamayganda ogohlantirish (1 < 2 TON)")

    # 4) Premium muvaffaqiyatli (javob faqat {"ok": true})
    REPLY["premium/buy"] = {"ok": True}
    bal, order, msg, price = await run("premium", 12, "monk")
    check(CALLS[-1] == ("premium/buy", {"username": "monk", "month": 12}) and order.status == OrderStatus.DELIVERED, "Premium 12 oy: so'rov va natija to'g'ri")

    # 5) aniq rad: username topilmadi → pul qaytadi
    REPLY["stars/buy"] = {"ok": False, "code": "006", "error": "Username topilmadi"}
    bal, order, msg, price = await run("stars", 50, "nouser")
    check(bal == 1_000_000 and order.status == OrderStatus.CANCELLED and order.items[0].status == "failed" and order.total == 0,
          "006: pul to'liq qaytdi, buyurtma bekor")
    check("@username topilmadi" in msg.texts[-1] and "qaytarildi" in msg.texts[-1], "mijozga aniq sabab aytiladi")

    # 6) StarsUno hisobida pul yo'q (003): mijozga qaytadi + admin ogohlantiriladi
    alerts_sent.clear()
    REPLY["stars/buy"] = {"ok": False, "code": "003", "error": "Hisobda mablag' yetarli emas"}
    bal, order, msg, price = await run("stars", 50, "monk")
    check(bal == 1_000_000 and order.status == OrderStatus.CANCELLED, "003: mijoz puli qaytdi")
    check(alerts_sent and "Fragment" in alerts_sent[0] and "to'ldiring" in alerts_sent[0], "003: adminga «Fragment hamyonini to'ldiring» xabari")

    # 7) noma'lum natija: 004 va tarmoq xatosi — pul QAYTMAYDI, buyurtma kutilmoqda, admin ogohlantiriladi
    for reply in ({"ok": False, "code": "004", "error": "Stars yuborishda xatolik"}, starsuno.SupplierError("Javob olinmadi: TimeoutError")):
        alerts_sent.clear()
        REPLY["stars/buy"] = reply
        bal, order, msg, price = await run("stars", 50, "monk")
        check(bal == 1_000_000 - price and order.status == OrderStatus.PAID and order.items[0].status == "pending",
              f"noma'lum natija ({type(reply).__name__ if not isinstance(reply, dict) else reply['code']}): pul qaytmadi, buyurtma kutilmoqda")
        check(len([c for c in CALLS if c[0] == "stars/buy"]) == 1, "  qayta urinish YO'Q (ikki marta yuborilmaydi)")
        check(alerts_sent and "natija noma'lum" in alerts_sent[0] and "Qaytadan buyurtma bermang" in msg.texts[-1], "  admin va mijoz xabardor")

    # 8) ulanib bo'lmadi (so'rov umuman yuborilmagan) → aniq rad, pul qaytadi
    REPLY["stars/buy"] = ConnectionRefusedError("dns")
    bal, order, msg, price = await run("stars", 50, "monk")
    check(bal == 1_000_000 and order.status == OrderStatus.CANCELLED, "ulanmagan: pul qaytdi")

    # 9) balans yetmasa — so'rov yuborilmaydi
    REPLY["stars/buy"] = {"ok": True, "balance": 1}
    bal, order, msg, price = await run("stars", 100, "monk", balance=1000)
    check(bal == 1000 and not [c for c in CALLS if c[0].endswith("/buy")] and "yetarli emas" in msg.texts[-1],
          "hisobda pul yetmasa Fragment'ga so'rov YUBORILMAYDI")

    # 10) miqdor/muddat chegaralari API'ga yetmasdan rad etiladi
    CALLS.clear()
    r1, r2 = await starsuno.buy_stars("monk", 49), await starsuno.buy_premium("monk", 5)
    check(r1.kind == r2.kind == "failed" and not CALLS, "49 Stars va 5 oy so'ralmaydi")

    # 11) «Obunalar» ro'yxatida Stars/Premium tugmalari
    kb = services_kb({"ChatGPT": True})
    last = [b.callback_data for b in kb.inline_keyboard[-1]]
    check(last == ["tg:stars", "tg:prem"], "«Obunalar» ro'yxati tagida ⭐ Stars va 👑 Premium tugmalari bor")

    # 12) tugmalardagi emoji premium ikonkaga aylanadi (Stars = oltin yulduz, Premium = binafsha yulduz), rang saqlanadi
    from middlewares.emoji_fallback import _strip_button_icons
    from services.emoji import button_icons
    conv = button_icons(kb)
    row = {b.text: b for r in conv.inline_keyboard for b in r}
    stars, prem = row["Telegram Stars"], row["Telegram Premium"]
    check(stars.model_extra["icon_custom_emoji_id"] == "5438553238217450600" and prem.model_extra["icon_custom_emoji_id"] == "5438186851737299383",
          "⭐ Stars tugmasi oltin yulduz, 👑 Premium — binafsha yulduz ikonkasi bilan")
    check(stars.style == "success" and prem.style == "success", "ikkalasi yashil fonli")
    back = _strip_button_icons(conv)
    check({b.text for r in back.inline_keyboard for b in r} >= {"⭐ Telegram Stars", "👑 Telegram Premium"},
          "premium rad etilsa emoji tugma matniga qaytadi (ikonka ketsa ham yo'qolmaydi)")
    rows_ = [[tgstars.InlineKeyboardButton(text="👑 3 oy — 187 000 so'm", callback_data="x")], [tgstars.InlineKeyboardButton(text="Faqat matn", callback_data="y")]]
    c2 = button_icons(tgstars.InlineKeyboardMarkup(inline_keyboard=rows_))
    check(c2.inline_keyboard[0][0].text == "3 oy — 187 000 so'm" and c2.inline_keyboard[1][0].text == "Faqat matn", "matn ichidagi/emojisiz tugmalarga tegilmaydi")
    check("<tg-emoji emoji-id=\"5438553238217450600\">" in __import__("services.emoji", fromlist=["x"]).premiumize("⭐ Stars"), "xabar matnidagi ⭐ ham premium")

    from services.emoji import premiumize as pz
    allx = pz("✨ 📭 🏠 📧 🎟 🔴 ❓ ✏️ 📊 📄 🤔 🔔 🆕 🔄")
    check(allx.count("<tg-emoji") == 14 and "5413759431399718342" in allx and "5972210698636234017" not in allx, "yangi 14 ta emoji (✨ 📭 🏠 📧 🎟 🔴 ❓ ✏ 📊 📄 🤔 🔔 🆕 🔄) premium")
    from services import runtime as rt
    check(rt.LAST_UPDATE_EMOJI == "5260687119092817530", "«Oxirgi yangilanish» belgisi o'z ID siga ega")

    fragment_tg.configured = lambda: False
    check(len(services_kb({"ChatGPT": True}).inline_keyboard) == 1, "Fragment sozlanmagan bo'lsa tugmalar chiqmaydi")
    print("\nHAMMASI JOYIDA")


asyncio.run(main())
