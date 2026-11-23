"""Telegram Business ko'prigi: faqat owner'ning ulanishidagi @HUMOcardbot xabarlari avto-to'lovga boradi.

Ishga tushirish:  python tests/test_business.py
"""
from __future__ import annotations

import asyncio
import datetime
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678", ADMIN_IDS="1", TELEGRAM_OWNER_ID="777",
                  DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db")

from aiogram.types import BusinessConnection, Chat, Message, User  # noqa: E402

from database.db import init_db  # noqa: E402
from handlers import business  # noqa: E402
from services import cardbridge, paynotify, runtime  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def msg(conn_id, sender_id, username, text, mid=1):
    return Message(message_id=mid, date=datetime.datetime.now(), chat=Chat(id=777, type="private"),
                   from_user=User(id=sender_id, is_bot=True, first_name="x", username=username), text=text,
                   business_connection_id=conn_id)


class FakeBot:
    def __init__(self):
        self.conns = {"bc-owner": 777, "bc-other": 999}

    async def get_business_connection(self, cid):
        return NS(user=NS(id=self.conns[cid]))


async def main() -> None:
    await init_db()
    calls, notes = [], []

    async def fake_on_message(bot, **kw):
        calls.append(kw)
        return True

    async def fake_notify(bot, text, *a, **k):
        notes.append(text)

    cardbridge.on_message = fake_on_message
    paynotify.notify_owner = fake_notify
    bot = FakeBot()

    await business.on_business_message(msg("bc-owner", 100, "HUMOcardbot", "➕ Пополнение 50 013 UZS", 5), bot)
    check(len(calls) == 1 and calls[0]["sender_username"] == "HUMOcardbot" and calls[0]["text"].endswith("UZS") and calls[0]["msg_id"] == 5,
          "owner ulanishidagi @HUMOcardbot xabari avto-to'lov oqimiga berildi")
    check(any("Business ko'prigi ishlayapti" in n for n in notes) and any("Business orqali xabar keldi" in n and "HUMOcardbot" in n for n in notes),
          "ownerga «xabar keldi» va «ishlayapti» xabarlari")
    check(calls[0]["any_bot"] is True, "bot yuboruvchi (HUMO) manbalar ro'yxatiga qaramay qabul qilinadi")
    n0 = len(calls)
    await business.on_business_message(msg("bc-owner", 100, "NomaIum_bot", "➕ 1 000 UZS", 20), bot)
    check(len(calls) == n0 + 1, "boshqa nomli BOT xabari ham o'tkaziladi (nom o'zgargan bo'lsa ham)")
    human = Message(message_id=21, date=datetime.datetime.now(), chat=Chat(id=777, type="private"),
                    from_user=User(id=555, is_bot=False, first_name="Odam", username="odam1"), text="+1 000 UZS", business_connection_id="bc-owner")
    await business.on_business_message(human, bot)
    check(calls[-1]["any_bot"] is False and any("odam" in n and "e'tiborsiz" in n for n in notes), "odam yuborgan xabar kirim hisoblanmaydi (any_bot=False)")
    n0 = len(notes)

    c0 = len(calls)
    await business.on_business_message(msg("bc-other", 100, "HUMOcardbot", "➕ 1 000 UZS", 6), bot)
    check(len(calls) == c0, "begona akkauntning business ulanishidan kelgan xabar e'tiborsiz")
    await business.on_business_message(msg("bc-owner", 777, "owner_nick", "salom", 7), bot)
    check(len(calls) == c0, "owner'ning o'z (chiquvchi) xabari kirim emas")
    await business.on_business_message(msg(None, 100, "HUMOcardbot", "➕ 1 000 UZS", 8), bot)
    check(len(calls) == c0, "business ulanishisiz xabar e'tiborsiz")

    conn = BusinessConnection(id="bc-new", user=User(id=999, is_bot=False, first_name="Boshqa"), user_chat_id=999,
                              date=datetime.datetime.now(), can_reply=False, is_enabled=True)
    await business.on_connection(conn, bot)
    check(business._OWNER_CONN["bc-new"] is False and len(notes) == n0, "begona akkaunt botni ulasa — qabul qilinmaydi, ownerga xabar yo'q")
    mine = BusinessConnection(id="bc-mine", user=User(id=777, is_bot=False, first_name="Owner"), user_chat_id=777,
                              date=datetime.datetime.now(), can_reply=False, is_enabled=True)
    await business.on_connection(mine, bot)
    check(business._OWNER_CONN["bc-mine"] and business.STATE["connected"] and "Business ulandi" in notes[-1], "owner ulasa — «Business ulandi» xabari")
    check(any("ruxsatlar" in n and "yoqing" in n for n in notes), "ruxsatlar o'chiq ulansa — ownerga «barcha ruxsatlarni yoqing» ogohlantirishi")
    # bot qayta ishga tushsa (xotira bo'sh) va Telegram ulanishni qaytarmasa ham — saqlangan owner ulanishi taniladi
    class BrokenBot(FakeBot):
        async def get_business_connection(self, cid):
            raise RuntimeError("tarmoq")
    await runtime.load()
    business._OWNER_CONN.clear()
    c1 = len(calls)
    await business.on_business_message(msg("bc-mine", 100, "HUMOcardbot", "➕ 1 063 UZS", 30), BrokenBot())
    check(len(calls) == c1 + 1, "qayta ishga tushgandan keyin ham owner ulanishi bazadan taniladi (xabar o'tkazildi)")
    business._OWNER_CONN.clear()
    await business.on_business_message(msg("bc-yangi", 100, "HUMOcardbot", "➕ 1 063 UZS", 31), BrokenBot())
    check(len(calls) == c1 + 1 and any("tekshirib bo'lmadi" in n for n in notes), "ulanishni tekshirib bo'lmasa — xabar e'tiborsiz, ownerga sabab aytiladi")

    # HUMO botning haqiqiy xabari (💰 belgisi oldidan summa, «To'ldirish») kirim sifatida taniladi; qoldiq — yo'q
    from services import topup
    real = "🎉 To'ldirish\n💰 1.063,00 UZS\n📍 PAYNET P2P UZC2HUM>S\n💳 HUMOCARD *0495\n🕒 14:14 04.11.2026"
    p = topup.parse_credit(real)
    check(p.kind == "credit" and p.amount == 1063, "HUMO xabari «To'ldirish 💰 1.063,00 UZS» → kirim 1063 so'm")
    check(topup.parse_credit("➕ Пополнение 1 068.00 UZS\n💵 1 020 074.01 UZS").amount == 1068, "CardXabarBot: kirim 1068 (qoldiq emas)")
    check(topup.parse_credit("💵 Баланс: 1 020 074.01 UZS").kind != "credit", "qoldiq xabari kirim emas")
    print("\nHAMMASI JOYIDA")


asyncio.run(main())
