"""Avtomatik to'lov tizimi testlari (internet, token va haqiqiy Telegram shart emas).

Ishga tushirish:  python tests/test_payments.py
"""
from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(
    BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678",
    ADMIN_IDS="1",
    EXTRA_ADMIN_IDS="7330213371",
    TELEGRAM_OWNER_ID="7330213371",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db",
    WEBHOOK_URL="https://example.onrender.com",
    PAYMENT_CARD_NUMBER="8600123412341234",
    PAYMENT_CARD_OWNER="TEST OWNER",
    SMS_WEBHOOK_SECRET="sms-secret-xyz",
    PAYME_MERCHANT_ID="merchant1",
    PAYME_KEY="payme-test-key",
    CLICK_MERCHANT_ID="777",
    CLICK_SERVICE_ID="999",
    CLICK_SECRET_KEY="click-test-secret",
    CARD_SOURCES="humocardbot,cardxabarbot",
)
OWNER = 7330213371

from aiogram import Bot  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, Update, User as TgUser  # noqa: E402
from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

import bot as B  # noqa: E402
from database.db import SessionMaker, engine, init_db  # noqa: E402
from database.models import (  # noqa: E402
    BankCredit, ClickTransaction, Payment, PaymeTransaction, TopupOrder, User,
)
from services import cardbridge, paynotify, runtime, topup  # noqa: E402
from webapp import payments_api  # noqa: E402
from webapp.server import setup_webapp  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str, object]] = []

    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.sent.append((chat_id, text, reply_markup))

    def to(self, chat_id):
        return [t for c, t, _ in self.sent if c == chat_id]


async def make_user(tg_id: int, name: str = "Ali") -> User:
    async with SessionMaker() as s:
        u = User(tg_id=tg_id, full_name=name, username=f"u{tg_id}", balance=0)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def balance(tg_id: int) -> int:
    async with SessionMaker() as s:
        return (await s.scalar(select(User.balance).where(User.tg_id == tg_id)))


async def new_order(user: User, base: int = 49_000, provider: str = "card") -> TopupOrder:
    async with SessionMaker() as s:
        u = await s.get(User, user.id)
        return await topup.create_order(s, u, base, provider, chat_id=u.tg_id)


async def order_status(oid: int) -> str:
    async with SessionMaker() as s:
        return (await topup.get_order(s, oid)).status


async def expire(oid: int) -> None:
    async with SessionMaker() as s:
        o = await topup.get_order(s, oid)
        o.expires_at = topup.utcnow() - datetime.timedelta(minutes=1)
        await s.commit()


def payme_hdr(key="payme-test-key") -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"Paycom:{key}".encode()).decode()}


def click_params(order, action, trans="555", prepare_id=None, error="0", amount=None, secret="click-test-secret", sign=None):
    p = {"click_trans_id": trans, "service_id": "999", "click_paydoc_id": "1", "merchant_trans_id": str(order.id),
         "amount": str(amount if amount is not None else order.payment_amount), "action": str(action),
         "error": error, "error_note": "", "sign_time": "2026-10-05 12:00:00"}
    if prepare_id is not None:
        p["merchant_prepare_id"] = str(prepare_id)
    parts = [p["click_trans_id"], p["service_id"], secret, p["merchant_trans_id"]]
    if action == 1:
        parts.append(p["merchant_prepare_id"])
    parts += [p["amount"], p["action"], p["sign_time"]]
    p["sign_string"] = sign or hashlib.md5("".join(parts).encode()).hexdigest()
    return p


# ── dispatcher uchun soxta Telegram ──
SENT: list[tuple[int, str]] = []


async def fake_call(self, method, request_timeout=None):
    name = type(method).__name__
    SENT.append((getattr(method, "chat_id", 0), (getattr(method, "text", "") or "")))
    if name in ("SendMessage", "EditMessageText"):
        return Message(message_id=2, date=datetime.datetime.now(), chat=Chat(id=5, type="private"), text="x")
    return True


_uid = 1000


def _cb(uid: int, data: str) -> Update:
    global _uid
    _uid += 1
    base = Message(message_id=_uid, date=datetime.datetime.now(), chat=Chat(id=uid, type="private"), text="panel")
    cq = CallbackQuery(id=str(_uid), from_user=TgUser(id=uid, is_bot=False, first_name="X"),
                       chat_instance="x", message=base, data=data)
    return Update(update_id=_uid, callback_query=cq)


async def main() -> None:
    await init_db()
    await runtime.load()
    bot = FakeBot()
    cust = await make_user(1001, "Mijoz")
    other = await make_user(1002, "Begona")

    # ── Noyob summa, 30 daqiqa ──
    orders = [await new_order(cust if i % 2 == 0 else other, 49_000) for i in range(6)]
    amounts = [o.payment_amount for o in orders]
    check(len(set(amounts)) == 6 and all(49_000 + 1 <= a <= 49_000 + topup.extra_limit(49_000) for a in amounts),
          "paymentAmount = baseAmount + noyob qo'shimcha (49 000 → 49 001–49 490) va faol buyurtmalarda takrorlanmaydi")
    check([topup.extra_limit(b) for b in (1_000, 5_000, 20_000, 50_000, 100_000, 1_000_000)] == [100, 100, 200, 500, 999, 999],
          "qo'shimcha adolatli: 1 000 → 1001–1100, 20 000 → +200 gacha, 50 000 → +500 gacha, katta summada ko'pi bilan 999")

    check(all(timedelta_ok(o) for o in orders), "buyurtma 30 daqiqa amal qiladi")
    for o in orders[1:]:
        async with SessionMaker() as s:
            await topup.cancel_order(s, o.id)
    o1 = orders[0]
    small = [await new_order(other, 1_000) for _ in range(3)]
    check(all(1_001 <= o.payment_amount <= 1_100 for o in small), "1 000 so'm to'ldirish → 1 001 … 1 100 so'm oralig'ida")
    for o in small:
        async with SessionMaker() as s:
            await topup.cancel_order(s, o.id)
    text = paynotify.order_text(o1)
    check("8600 1234 1234 1234" in text and "TEST OWNER" in text and f"#{o1.id}" in text and "30 daqiqa" in text
          and "49" in text, "mijozga karta, karta egasi, aniq summa, buyurtma ID va 30 daqiqa ko'rsatiladi")

    # ── 1. To'g'ri kirim xabari buyurtmani topadi ──
    msg = f"➕ Пополнение {o1.payment_amount:,.2f} UZS".replace(",", " ")
    out = await paynotify.process_incoming(bot, "cardxabarbot", "c1:1", msg)
    check(out.kind == "matched" and await order_status(o1.id) == "paid", "1. to'g'ri kirim xabari buyurtmani topadi va tasdiqlaydi")
    check(await balance(1001) == o1.payment_amount and any("To'lov qabul qilindi" in t for t in bot.to(1001)),
          "   hamyonga qo'shildi, mijozga xabar bordi")
    check(any("To'lov qabul qilindi" in t for t in bot.to(OWNER)), "   ownerga (7330213371) hisobot bordi")

    # ── CardXabarBot haqiqiy formati: kirim + qoldiq (kasrli) bir xabarda ──
    from services.topup import parse_credit
    real = "🟢 Perevod na kartu\n➕ 1 068.00 UZS\n💳 ***3860\n📍 AO PAYNET, UZ\n🕒 06.10.26 01:04\n💵 1 020 074.01 UZS"
    pr = parse_credit(real)
    check(pr.kind == "credit" and pr.amount == 1068, "CardXabarBot haqiqiy xabari: kirim 1 068 so'm (qoldiq 1 020 074.01 hisobga olinmaydi)")
    check(parse_credit("➕ Пополнение 49 437.00 UZS\n💰 Баланс: 1 200 000.50 UZS").amount == 49437, "   qoldiq so'zi bilan ham to'g'ri")
    check(parse_credit("➖ Оплата 500.00 UZS\n💵 1 020 074.01 UZS").kind == "debit", "   chiqim + qoldiq — baribir chiqim")
    check(parse_credit("➕ 1 068.50 UZS").kind == "unknown", "   kasrli kirim (50 tiyin) tarif bermaydi")
    oReal = await new_order(other, 1_000)
    realmsg = real.replace("1 068.00", f"{oReal.payment_amount:,}.00".replace(",", " "))
    out = await paynotify.process_incoming(bot, "cardxabarbot", "real:1", realmsg)
    check(out.kind == "matched" and await order_status(oReal.id) == "paid", "   haqiqiy format bilan buyurtma avtomatik tasdiqlandi")

    # ── HUMOcardbot: kirim xabari shu botdan kelsa buyurtma avtomatik tasdiqlanadi; begonadan kelsa — yo'q ──
    oH = await new_order(other, 5_000)
    humo = f"➕ {oH.payment_amount:,}.00 UZS\n💳 HUMOCARD *3860\n📍 P2P TRANSFER\n🕓 12:00\n💰 2 000 000.00 UZS".replace(",", " ")
    handled = await cardbridge.on_message(bot, sender_username="HUMOcardbot", is_private=True, chat_id=77, msg_id=1, text=humo)
    check(handled and await order_status(oH.id) == "paid", "HUMOcardbot'dan kelgan kirim buyurtmani avtomatik tasdiqlaydi")
    oF = await new_order(other, 5_000)
    fake = f"➕ {oF.payment_amount:,}.00 UZS".replace(",", " ")
    check(await cardbridge.on_message(bot, sender_username="somebody_else", is_private=True, chat_id=78, msg_id=2, text=fake) is False
          and await order_status(oF.id) == "pending", "   begona odamdan kelgan «kirim» xabari e'tiborsiz (soxta to'lov o'tmaydi)")
    check(await cardbridge.on_message(bot, sender_username="HUMOcardbot", is_private=False, chat_id=79, msg_id=3, text=fake) is False
          and await order_status(oF.id) == "pending", "   guruhdagi xabar e'tiborsiz (faqat shaxsiy chat)")
    os.environ.pop("CARD_SOURCES", None)
    from config import Settings
    check({"humocardbot", "cardxabarbot"} <= set(Settings(_env_file=None).card_source_list), "sukut manbalar: humocardbot va cardxabarbot")

    # ── 2. Chiqim xabari tarif bermaydi ──
    o2 = await new_order(cust, 49_000)
    for bad in (f"➖ Оплата {o2.payment_amount} UZS", f"{o2.payment_amount} so'm yechildi", f"yechib olindi {o2.payment_amount} UZS",
                f"xarid {o2.payment_amount} UZS", f"purchase {o2.payment_amount} UZS", f"withdraw {o2.payment_amount} UZS",
                f"списание {o2.payment_amount} UZS", f"снят {o2.payment_amount} UZS", f"-{o2.payment_amount} UZS"):
        out = await paynotify.process_incoming(bot, "cardxabarbot", f"debit:{hash(bad)}", bad)
        check(out.kind == "ignored", f"2. chiqim «{bad[:22]}…» e'tiborsiz")
    check(await order_status(o2.id) == "pending" and await balance(1001) == o1.payment_amount, "   chiqim xabarlari tarif bermadi")

    # ── 3. Noto'g'ri summa ──
    out = await paynotify.process_incoming(bot, "cardxabarbot", "c1:3", f"➕ Пополнение {o2.payment_amount + 1} UZS")
    check(out.kind == "unmatched" and await order_status(o2.id) == "pending", "3. noto'g'ri summa tarif bermaydi")

    # ── 4. Muddati tugagan ──
    await expire(o2.id)
    bot.sent.clear()
    out = await paynotify.process_incoming(bot, "cardxabarbot", "c1:4", f"➕ Пополнение {o2.payment_amount} UZS")
    check(out.kind == "late" and await order_status(o2.id) == "expired" and await balance(1001) == o1.payment_amount,
          "4. muddati tugagan buyurtma avtomatik tarif bermaydi")
    owner_msgs = [(t, kb) for c, t, kb in bot.sent if c == OWNER]
    btns = [b.text for r in owner_msgs[0][1].inline_keyboard for b in r]
    check(owner_msgs and "KECH" in owner_msgs[0][0] and any("Tasdiqlash" in b for b in btns) and any("Rad etish" in b for b in btns),
          "   ownerga nomzod buyurtma va ✅ Tasdiqlash / ❌ Rad etish tugmalari yuborildi")

    # ── 5. Bir xil to'lov ikki marta tarif bermaydi ──
    before = await balance(1001)
    out = await paynotify.process_incoming(bot, "cardxabarbot", "c1:1", msg)
    check(out.kind == "duplicate" and await balance(1001) == before, "5. xuddi shu xabar ikkinchi marta tarif bermaydi")
    out = await paynotify.process_incoming(bot, "cardxabarbot", "c1:99", msg)
    check(await balance(1001) == before, "   shu summa boshqa xabar bilan kelsa ham (buyurtma to'langan) qayta tarif yo'q")
    async with SessionMaker() as s:
        res = await topup.confirm_order(s, o1.id, "card", "other-txn")
    check(res.status == "already_paid" and await balance(1001) == before, "   confirmOrder to'langan buyurtmada already_paid")

    # ── 14. Bir vaqtda ikki chaqiruv — bitta marta ──
    o3 = await new_order(cust, 20_000)

    async def conf(tag):
        async with SessionMaker() as s:
            return await topup.confirm_order(s, o3.id, "card", f"race:{tag}")

    r1, r2 = await asyncio.gather(conf("a"), conf("b"))
    check(sorted([r1.status, r2.status])[0] in ("already_paid", "duplicate_txn", "expired") and [r1.ok, r2.ok].count(True) == 1
          and await balance(1001) == before + o3.payment_amount, "14. ikki parallel confirmOrder faqat bir marta tarif beradi")
    # admin callbacklari ham (ikki marta bosish)
    Bot.__call__ = fake_call
    dp = B.build_dispatcher()
    tbot = Bot(B.settings.bot_token)
    o4 = await new_order(cust, 30_000)
    bal = await balance(1001)
    await asyncio.gather(dp.feed_update(tbot, _cb(OWNER, f"pay:adm_ok:{o4.id}")), dp.feed_update(tbot, _cb(OWNER, f"pay:adm_ok:{o4.id}")))
    check(await balance(1001) == bal + o4.payment_amount and await order_status(o4.id) == "paid",
          "   ikki marta bosilgan «✅ Tasdiqlash» faqat bir marta tarif beradi")

    # ── 11. Begona admin tugmalarini ishlata olmaydi ──
    o5 = await new_order(cust, 25_000)
    await dp.feed_update(tbot, _cb(777, f"pay:adm_ok:{o5.id}"))
    await dp.feed_update(tbot, _cb(1, f"pay:adm_ok:{o5.id}"))        # ADMIN_IDS dagi boshqa admin ham to'lov admini emas
    await dp.feed_update(tbot, _cb(777, f"pay:adm_no:{o5.id}"))
    await dp.feed_update(tbot, _cb(777, "pay:adm_auto"))
    check(await order_status(o5.id) == "pending" and runtime.autoconfirm_enabled(),
          "11. begona Telegram foydalanuvchi to'lov admin tugmalarini ishlata olmaydi (faqat raqamli owner ID)")
    await dp.feed_update(tbot, _cb(1001, f"pay:check:{o5.id}"))        # o'zining buyurtmasi — xavfsiz
    await dp.feed_update(tbot, _cb(1002, f"pay:cancel:{o5.id}"))       # begona mijoz boshqaning buyurtmasini bekor qila olmaydi
    check(await order_status(o5.id) == "pending", "   begona mijoz boshqaning buyurtmasini bekor qila olmaydi (callback egasi tekshiriladi)")
    await dp.feed_update(tbot, _cb(1001, f"pay:cancel:{o5.id}"))
    check(await order_status(o5.id) == "cancelled", "   mijoz o'z buyurtmasini bekor qila oladi")
    await dp.feed_update(tbot, _cb(OWNER, "pay:adm_auto"))
    check(runtime.autoconfirm_enabled() is False, "   owner avto-tasdiqni o'chira oladi")
    o6 = await new_order(cust, 15_000)
    bot.sent.clear()
    out = await paynotify.process_incoming(bot, "cardxabarbot", "c1:6", f"+{o6.payment_amount} so'm kartangizga tushdi")
    check(out.kind == "candidate" and await order_status(o6.id) == "pending" and bot.to(OWNER),
          "   avto-tasdiq o'chiq bo'lsa — to'lov ownerga nomzod sifatida yuboriladi, o'zi tasdiqlanmaydi")
    await dp.feed_update(tbot, _cb(OWNER, "pay:adm_auto"))
    check(runtime.autoconfirm_enabled(), "   avto-tasdiq qayta yoqildi")

    # ── 12. Begona CardXabar manbasi ──
    o7 = await new_order(cust, 18_000)
    ok_foreign = await cardbridge.on_message(bot, sender_username="evilbot", is_private=True, chat_id=5, msg_id=1,
                                             text=f"➕ Пополнение {o7.payment_amount} UZS")
    ok_group = await cardbridge.on_message(bot, sender_username="cardxabarbot", is_private=False, chat_id=-100, msg_id=2,
                                           text=f"➕ Пополнение {o7.payment_amount} UZS")
    check(not ok_foreign and not ok_group and await order_status(o7.id) == "pending",
          "12. begona manba va guruh xabarlari e'tiborsiz qoldiriladi")
    ok_real = await cardbridge.on_message(bot, sender_username="CardXabarBot", is_private=True, chat_id=5, msg_id=3,
                                          text=f"➕ Пополнение {o7.payment_amount} UZS")
    check(ok_real and await order_status(o7.id) == "paid", "   ruxsat berilgan manba (CardXabarBot) xabari qayta ishlanadi")

    # ── SMS webhook ──
    app = web.Application()
    setup_webapp(app, bot)
    async with TestClient(TestServer(app)) as cl:
        o8 = await new_order(cust, 22_000)
        r = await cl.post("/api/payments/sms", json={"secret": "wrong", "text": f"+{o8.payment_amount} UZS"})
        check(r.status == 403, "6. noto'g'ri webhook secret → 403")
        r = await cl.post("/api/payments/sms", json={"text": f"+{o8.payment_amount} UZS"})
        check(r.status == 403, "   secret yo'q → 403")
        r = await cl.post("/api/payments/sms", json={"secret": "sms-secret-xyz", "text": "x" * 5000})
        check(r.status == 400, "   juda uzun matn rad etiladi")
        check(await order_status(o8.id) == "pending", "   noto'g'ri so'rovlar tarif bermadi")
        r = await cl.post("/api/payments/sms", json={"secret": "sms-secret-xyz", "text": f"Kirim: +{o8.payment_amount} so'm"})
        check(r.status == 200 and await order_status(o8.id) == "paid", "   to'g'ri secret + kirim SMS → tasdiqlandi")
        # oson ulanish: kalit/matn havolada, forma, sarlavha yoki oddiy matn ko'rinishida ham qabul qilinadi
        o9 = await new_order(cust, 23_000)
        r = await cl.get("/api/payments/sms", params={"secret": "sms-secret-xyz", "text": f"Kirim: +{o9.payment_amount} so'm"})
        check(r.status == 200 and await order_status(o9.id) == "paid", "   GET ?secret=…&text=… (oddiy SMS ilovasi) ishlaydi")
        o10 = await new_order(cust, 24_000)
        r = await cl.post("/api/payments/sms", data={"key": "sms-secret-xyz", "message": f"Kirim: +{o10.payment_amount} so'm"})
        check(r.status == 200 and await order_status(o10.id) == "paid", "   forma (key, message) ishlaydi")
        o11 = await new_order(cust, 25_000)
        r = await cl.post("/api/payments/sms", data=f"Kirim: +{o11.payment_amount} so'm", headers={"X-Secret": "sms-secret-xyz", "Content-Type": "text/plain"})
        check(r.status == 200 and await order_status(o11.id) == "paid", "   oddiy matn + X-Secret sarlavha ishlaydi")
        r = await cl.get("/api/payments/sms", params={"secret": "yolg'on", "text": "+1000 UZS"})
        check(r.status == 403, "   noto'g'ri kalit GET'da ham rad etiladi")
        statuses = []
        for _ in range(25):
            statuses.append((await cl.post("/api/payments/sms", json={"secret": "bad", "text": "x"})).status)
        check(429 in statuses, "   rate limit ishlaydi")
        payments_api._hits.clear()

        # ── Payme ──
        oP = await new_order(cust, 40_000, "payme")
        amt = oP.payment_amount * 100

        async def rpc(method, params, headers=None):
            r = await cl.post("/api/payments/payme", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                              headers=headers if headers is not None else payme_hdr())
            return await r.json()

        res = await rpc("CheckPerformTransaction", {"amount": amt, "account": {"order_id": oP.id}}, headers={})
        check(res.get("error", {}).get("code") == -32504, "7. Payme Authorization'siz rad etiladi")
        res = await rpc("CheckPerformTransaction", {"amount": amt, "account": {"order_id": oP.id}}, headers=payme_hdr("wrong"))
        check(res.get("error", {}).get("code") == -32504, "   noto'g'ri Payme kalit rad etiladi")
        res = await rpc("CheckPerformTransaction", {"amount": amt + 100, "account": {"order_id": oP.id}})
        check(res.get("error", {}).get("code") == -31001, "8. Payme noto'g'ri summa rad etiladi (-31001)")
        res = await rpc("CheckPerformTransaction", {"amount": amt, "account": {"order_id": 999999}})
        check(res.get("error", {}).get("code") == -31050, "   mavjud bo'lmagan buyurtma (-31050)")
        res = await rpc("CheckPerformTransaction", {"amount": amt, "account": {"order_id": oP.id}})
        check(res.get("result") == {"allow": True}, "   CheckPerformTransaction: to'g'ri buyurtma ruxsat etiladi")
        res = await rpc("CreateTransaction", {"id": "pm-1", "time": int(time.time() * 1000), "amount": amt, "account": {"order_id": oP.id}})
        check(res["result"]["state"] == 1, "   CreateTransaction (state 1)")
        res2 = await rpc("CreateTransaction", {"id": "pm-1", "time": 1, "amount": amt, "account": {"order_id": oP.id}})
        check(res2["result"]["create_time"] == res["result"]["create_time"], "   CreateTransaction takror — o'sha natija")
        res3 = await rpc("CreateTransaction", {"id": "pm-2", "time": int(time.time() * 1000), "amount": amt, "account": {"order_id": oP.id}})
        check(res3.get("error", {}).get("code") == -31099, "   boshqa faol tranzaksiyasi bor buyurtmaga ikkinchisi yaratilmaydi")
        balP = await balance(1001)
        res = await rpc("PerformTransaction", {"id": "pm-1"})
        check(res["result"]["state"] == 2 and await balance(1001) == balP + oP.payment_amount, "   PerformTransaction — tarif bir marta beriladi")
        res = await rpc("PerformTransaction", {"id": "pm-1"})
        check(res["result"]["state"] == 2 and await balance(1001) == balP + oP.payment_amount, "   PerformTransaction takror — qayta tarif yo'q")
        res = await rpc("CheckTransaction", {"id": "pm-1"})
        check(res["result"]["state"] == 2 and res["result"]["perform_time"] > 0 and res["result"]["cancel_time"] == 0, "   CheckTransaction")
        res = await rpc("CancelTransaction", {"id": "pm-1", "reason": 5})
        check(res["result"]["state"] == -2 and await balance(1001) == balP, "   CancelTransaction (to'langan): mablag' qaytarib olinadi, state -2")
        res = await rpc("PerformTransaction", {"id": "pm-nope"})
        check(res.get("error", {}).get("code") == -31003, "   mavjud bo'lmagan tranzaksiya (-31003)")
        # muddati tugagan / bekor qilingan buyurtmaga tarif yo'q
        oE = await new_order(cust, 41_000, "payme")
        await expire(oE.id)
        res = await rpc("CheckPerformTransaction", {"amount": oE.payment_amount * 100, "account": {"order_id": oE.id}})
        check(res.get("error", {}).get("code") == -31008, "   muddati tugagan buyurtmaga Payme tranzaksiya ochilmaydi")
        oC = await new_order(cust, 42_000, "payme")
        await rpc("CreateTransaction", {"id": "pm-3", "time": int(time.time() * 1000), "amount": oC.payment_amount * 100, "account": {"order_id": oC.id}})
        await rpc("CancelTransaction", {"id": "pm-3", "reason": 3})
        res = await rpc("PerformTransaction", {"id": "pm-3"})
        check(res.get("error", {}).get("code") == -31008 and await order_status(oC.id) == "pending",
              "   bekor qilingan tranzaksiyaga tarif berilmaydi")
        async with SessionMaker() as s:
            n = await s.scalar(select(func.count()).select_from(PaymeTransaction))
        check(n == 2, "   Payme tranzaksiyalari bazada (unique id, create/perform/cancel vaqtlari)")
        paynotify_url = paynotify.payme_url(oC)
        raw = base64.b64decode(paynotify_url.rsplit("/", 1)[1]).decode()
        check(f"m=merchant1;ac.order_id={oC.id};a={oC.payment_amount * 100};c=" in raw, "   Payme havolasi: m, ac.order_id, a (tiyin), c")

        # ── Click ──
        oK = await new_order(cust, 43_000, "click")
        r = await cl.post("/api/payments/click/prepare", data=click_params(oK, 0, sign="0" * 32))
        check((await r.json())["error"] == -1, "9. Click noto'g'ri imzo rad etiladi")
        r = await cl.post("/api/payments/click/prepare", data=click_params(oK, 0, amount=oK.payment_amount + 5))
        check((await r.json())["error"] == -2, "   Click noto'g'ri summa (-2)")
        r = await cl.post("/api/payments/click/prepare", data=click_params(oK, 0))
        prep = await r.json()
        check(prep["error"] == 0 and await order_status(oK.id) == "pending", "   Click prepare tarif bermaydi")
        balK = await balance(1001)
        r = await cl.post("/api/payments/click/complete", data={**click_params(oK, 1, prepare_id=prep["merchant_prepare_id"]), "error": ""})
        check((await r.json())["error"] == -8, "   Click complete: error maydoni bo'sh/yaroqsiz bo'lsa rad etiladi")
        r = await cl.post("/api/payments/click/complete", data=click_params(oK, 1, prepare_id=prep["merchant_prepare_id"]))
        comp = await r.json()
        check(comp["error"] == 0 and await order_status(oK.id) == "paid" and await balance(1001) == balK + oK.payment_amount,
              "   Click complete muvaffaqiyatli — tarif beriladi")
        r = await cl.post("/api/payments/click/complete", data=click_params(oK, 1, prepare_id=prep["merchant_prepare_id"]))
        check((await r.json())["error"] == -4 and await balance(1001) == balK + oK.payment_amount,
              "10. Click complete takrorlansa tarif qayta berilmaydi (-4)")
        r = await cl.post("/api/payments/click/prepare", data={**click_params(oK, 0), "service_id": "111"})
        check((await r.json())["error"] == -1, "   service_id mos kelmasa rad etiladi")
        click_link = paynotify.click_url(oK)
        check("service_id=999" in click_link and "merchant_id=777" in click_link and f"transaction_param={oK.id}" in click_link
              and f"amount={oK.payment_amount}" in click_link, "   Click havolasi: service_id, merchant_id, amount, transaction_param")

    # ── Owner kartani o'zgartiradi (faqat owner) ──
    def _msg(uid, text):
        global _uid
        _uid += 1
        m = Message(message_id=_uid, date=datetime.datetime.now(), chat=Chat(id=uid, type="private"),
                    from_user=TgUser(id=uid, is_bot=False, first_name="X"), text=text)
        return Update(update_id=_uid, message=m)

    await dp.feed_update(tbot, _cb(777, "pay:adm_card"))
    await dp.feed_update(tbot, _msg(777, "9860 1111 2222 3333"))
    check(runtime.card_number() == "8600123412341234", "   begona foydalanuvchi kartani o'zgartira olmaydi")
    await dp.feed_update(tbot, _cb(OWNER, "pay:adm_card"))
    await dp.feed_update(tbot, _msg(OWNER, "9860 1111 2222 3333"))
    check(runtime.card_number() == "9860111122223333", "   owner kartani o'zgartiradi (bazada saqlanadi)")
    await dp.feed_update(tbot, _cb(OWNER, "pay:adm_owner"))
    await dp.feed_update(tbot, _msg(OWNER, "YANGI EGA"))
    check(runtime.card_owner() == "YANGI EGA", "   owner karta egasini o'zgartiradi")
    SENT.clear()
    await dp.feed_update(tbot, _cb(OWNER, "pay:adm_diag"))
    check(any("Diagnostika" in x for _, x in SENT), "   owner diagnostikani ko'ra oladi")
    SENT.clear()
    await dp.feed_update(tbot, _cb(777, "pay:adm_diag"))
    check(not any("Diagnostika" in x for _, x in SENT), "   begona diagnostikani ko'ra olmaydi")
    check(not cardbridge.enabled(), "   TG_SESSION yo'q bo'lsa CardXabar ko'prigi o'chiq (bot ishlashda davom etadi)")

    # ── 13. Server qayta ishga tushganda buyurtmalar yo'qolmaydi ──
    oR = await new_order(cust, 60_000)
    await engine.dispose()
    async with SessionMaker() as s:
        paid_n = await s.scalar(select(func.count()).select_from(TopupOrder).where(TopupOrder.status == "paid"))
        pend = await topup.get_order(s, oR.id)
        pays = await s.scalar(select(func.count()).select_from(Payment))
        credits = await s.scalar(select(func.count()).select_from(BankCredit))
    check(paid_n >= 5 and pend and pend.status == "pending" and pays >= 5 and credits >= 3,
          "13. qayta ishga tushgandan keyin pending va paid buyurtmalar bazada saqlanib qoladi")
    async with SessionMaker() as s:
        clicks = await s.scalar(select(func.count()).select_from(ClickTransaction))
    check(clicks == 1, "   Click tranzaksiya ID unique")
    print("\nHammasi joyida ✅")


def timedelta_ok(o: TopupOrder) -> bool:
    return abs((o.expires_at - o.created_at).total_seconds() - 1800) < 1


asyncio.run(main())
