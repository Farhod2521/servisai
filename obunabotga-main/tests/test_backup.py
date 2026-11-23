"""Baza zaxirasi va tiklash testlari (Render deployda hisoblar yo'qolmasligi).

Ishga tushirish:  python tests/test_backup.py
"""
from __future__ import annotations

import asyncio
import datetime
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(
    BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678",
    ADMIN_IDS="1",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db",
    BACKUP_DIR=f"{_tmp}/zaxira",
)

from sqlalchemy import delete, select  # noqa: E402

from database.db import SessionMaker, init_db  # noqa: E402
from database.models import (  # noqa: E402
    Base, Category, DeliveryType, Order, OrderItem, OrderStatus, Payment, PaymentStatus, Product, ProductImage,
    Setting, TopupOrder, User,
)
from services import backup  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


class FakeBot:
    def __init__(self):
        self.pinned = None
        self.files: dict[str, bytes] = {}
        self.calls: list[str] = []
        self.messages: list[str] = []
        self._last = None

    async def get_chat(self, cid):
        return SimpleNamespace(pinned_message=self.pinned)

    async def send_document(self, chat_id, document, caption=None, disable_notification=None):
        mid = len(self.files) + 1
        fid = f"file{mid}"
        self.files[fid] = document.data
        self._last = SimpleNamespace(message_id=mid, document=SimpleNamespace(file_name=document.filename, file_id=fid))
        self.calls.append("send")
        return self._last

    async def pin_chat_message(self, chat_id, message_id, disable_notification=None):
        self.pinned = self._last
        self.calls.append("pin")

    async def edit_message_media(self, chat_id, message_id, media):
        fid = self.pinned.document.file_id
        self.files[fid] = media.media.data
        self.calls.append("edit")

    async def delete_message(self, chat_id, message_id):
        self.calls.append("delete")

    async def download(self, file_id, destination):
        destination.write(self.files[file_id])

    async def send_message(self, chat_id, text, **kw):
        self.messages.append(text)


async def wipe() -> None:
    async with SessionMaker() as s:
        for t in reversed(Base.metadata.sorted_tables):
            await s.execute(delete(t))
        await s.commit()


async def main() -> None:
    await init_db()
    check(await backup.is_empty(), "yangi baza bo'sh")
    bot = FakeBot()
    check(await backup.backup_now(bot) == "empty" and not bot.calls, "bo'sh bazani zaxiraga yozmaydi (yaxshi zaxirani o'chirib yubormaslik uchun)")

    now = datetime.datetime(2026, 10, 5, 12, 30, 15)
    async with SessionMaker() as s:
        cat = Category(name_uz="AI", emoji="🤖")
        s.add(cat)
        await s.flush()
        p = Product(category_id=cat.id, emoji="🤖", name="ChatGPT Plus 1 oy", price=250000, brand="ChatGPT",
                    delivery_type=DeliveryType.MANUAL, unlimited=True, synced_at=now)
        u = User(tg_id=777, full_name="Ali Valiyev", username="ali", balance=1_234_500)
        s.add_all([p, u])
        await s.flush()
        o = Order(user_id=u.id, total=250000, status=OrderStatus.DELIVERED)
        s.add(o)
        await s.flush()
        s.add_all([
            OrderItem(order_id=o.id, product_id=p.id, product_name=p.name, price=250000, qty=1,
                      delivered_content="login: a@b.c\nparol: Xk29-pQ71", status="ok"),
            Payment(user_id=u.id, amount=50000, provider="card", status=PaymentStatus.PAID, paid_at=now),
            TopupOrder(user_id=u.id, telegram_chat_id=777, base_amount=50000, payment_amount=50437, status="paid",
                       provider="card", provider_txn_id="cardxabarbot:1:5", created_at=now, expires_at=now, paid_at=now),
            ProductImage(product_id=p.id, data=b"\xff\xd8\xff\xe0JPEGDATA\x00\x01", mime="image/jpeg", tg_file_id="AgAC"),
            Setting(key="pay_card", value="8600000000000000"),
        ])
        await s.commit()

    check(not await backup.is_empty(), "ma'lumot bor — baza bo'sh emas")
    blob1, h1 = await backup.dump()
    blob1b, h1b = await backup.dump()
    check(h1 == h1b, "bir xil ma'lumot — bir xil xesh")
    async with SessionMaker() as s:
        pr = await s.scalar(select(Product))
        pr.synced_at = now + datetime.timedelta(minutes=3)
        await s.commit()
    check((await backup.dump())[1] == h1, "faqat synced_at o'zgarsa — zaxira «o'zgardi» deb hisoblanmaydi")
    async with SessionMaker() as s:
        usr = await s.scalar(select(User))
        usr.balance += 1000
        await s.commit()
    blob2, h2 = await backup.dump()
    check(h2 != h1, "balans o'zgarsa — xesh o'zgaradi")

    # ── Telegram'ga yuborish: birinchi marta yuboradi va pinlaydi, keyin tahrirlaydi ──
    hash_box = [None]
    res = await backup.backup_now(bot, last_hash=hash_box)
    check(res == "ok" and bot.calls == ["send", "pin"] and bot.pinned.document.file_name.startswith("obunalar-backup"),
          "zaxira ownerga yuborildi va pinlandi")
    check(await backup.backup_now(bot, last_hash=hash_box) == "same", "o'zgarish yo'q — qayta yuborilmaydi")
    async with SessionMaker() as s:
        usr = await s.scalar(select(User))
        usr.balance += 5000
        await s.commit()
    res = await backup.backup_now(bot, last_hash=hash_box)
    check(res == "ok" and bot.calls[-1] == "edit" and bot.calls.count("send") == 1, "o'zgarganda o'sha pinlangan xabar tahrirlanadi (chat to'lib ketmaydi)")
    expect_balance = 1_234_500 + 1000 + 5000

    # ── Deploy: baza o'chdi → zaxiradan tiklanadi ──
    await wipe()
    check(await backup.is_empty(), "deploy: baza o'chdi")
    ok = await backup.restore_if_empty(bot)
    check(ok and any("tiklandi" in m for m in bot.messages), "bot ishga tushganda zaxiradan tikladi va ownerga xabar berdi")
    async with SessionMaker() as s:
        usr = await s.scalar(select(User).where(User.tg_id == 777))
        pay = await s.scalar(select(Payment))
        top = await s.scalar(select(TopupOrder))
        item = await s.scalar(select(OrderItem))
        img = await s.scalar(select(ProductImage))
        prod = await s.scalar(select(Product))
        setting = await s.get(Setting, "pay_card")
        order = await s.scalar(select(Order))
    check(usr.balance == expect_balance and usr.full_name == "Ali Valiyev", "foydalanuvchi va uning HISOBIDAGI PUL tiklandi")
    check(pay.status == PaymentStatus.PAID and pay.paid_at == now, "to'lov (enum holati va vaqt) tiklandi")
    check(top.status == "paid" and top.payment_amount == 50437 and top.provider_txn_id == "cardxabarbot:1:5", "to'lov buyurtmasi va tranzaksiya ID tiklandi")
    check(item.delivered_content.startswith("login: a@b.c") and order.status == OrderStatus.DELIVERED, "buyurtma va yetkazilgan login/parol tiklandi")
    check(img.data == b"\xff\xd8\xff\xe0JPEGDATA\x00\x01" and prod.delivery_type == DeliveryType.MANUAL and prod.id == item.product_id,
          "mahsulot (ID o'zgarmadi), uning rasmi (baytlar) tiklandi")
    check(setting.value == "8600000000000000", "admin sozlamalari (karta) tiklandi")

    # ── Himoya: bo'sh bo'lmagan bazani qayta yozmaydi; zaxira topilmasa jim ──
    bot.messages.clear()
    check(await backup.restore_if_empty(bot) is False and not bot.messages, "baza to'la bo'lsa — tiklash ishlamaydi (ustiga yozmaydi)")
    await wipe()
    from config import settings as _st
    saved_dir, _st.backup_dir = _st.backup_dir, f"{_tmp}/bosh-papka"
    check(await backup.restore_if_empty(FakeBot()) is False, "zaxira yo'q (yangi o'rnatish) — jimgina davom etadi")
    _st.backup_dir = saved_dir

    # ── Sessiya hodisasi: balans o'zgarsa zaxira «muhim» deb belgilanadi ──
    await backup.restore_if_empty(bot)
    backup.install()
    backup._flags["critical"] = False
    async with SessionMaker() as s:
        usr = await s.scalar(select(User))
        usr.balance += 1
        await s.commit()
    check(backup._flags["critical"] is True, "balans o'zgarsa zaxira darhol yangilanishga belgilanadi")
    # admin tahriri (rasm, qo'llanma) darhol zaxiralanadi; ta'minotchi zaxirasi (stock) esa shoshilinch emas
    backup._flags["critical"] = False
    async with SessionMaker() as s:
        pr = await s.scalar(select(Product))
        pr.stock_qty = 77
        await s.commit()
    check(backup._flags["critical"] is False, "ta'minotchi zaxirasi (stock) o'zgarishi shoshilinch zaxira emas (har 3 daqiqada yuklanmaydi)")
    async with SessionMaker() as s:
        pr = await s.scalar(select(Product))
        pr.guide = "1) kiring"
        await s.commit()
    check(backup._flags["critical"] is True, "admin qo'llanma yozsa — zaxira darhol")
    backup._flags["critical"] = False
    async with SessionMaker() as s:
        img = await s.scalar(select(ProductImage))
        img.data = b"yangi rasm"
        await s.commit()
    check(backup._flags["critical"] is True, "admin rasm yuklasa — zaxira darhol")
    # ── Kompyuterdagi «zaxira» papkasi: internetsiz ham saqlanadi va bo'sh bazani o'zi tiklaydi ──
    d = backup.local_dir()
    files = sorted(d.glob("obunalar-zaxira-*.json.gz"))
    check(files, "zaxira papkaga ham yozildi (kompyuterda saqlanadi)")
    await backup.restore_if_empty(FakeBot())           # oldingi qadamda baza tozalangan edi — papkadan to'ldiramiz
    async with SessionMaker() as s:
        n_users = len(list(await s.scalars(select(User))))
    check(n_users > 0, "papkadagi zaxirada foydalanuvchilar bor")
    await wipe()
    check(await backup.is_empty(), "baza o'chirildi (fayl yo'qolgan holat)")
    nobot = FakeBot()                                   # Telegram'da zaxira yo'q — faqat papkadagisi
    ok = await backup.restore_if_empty(nobot)
    async with SessionMaker() as s:
        back = len(list(await s.scalars(select(User))))
    check(ok and back == n_users and any("papkasidan tiklandi" in m for m in nobot.messages),
          f"bot yonganda bazani papkadagi zaxiradan o'zi tikladi ({back} foydalanuvchi)")
    # eng yangi fayl buzilgan bo'lsa — oldingisi olinadi
    newest = sorted(d.glob("obunalar-zaxira-*.json.gz"))[-1]
    good = newest.read_bytes()
    (d / "obunalar-zaxira-99991231-235959.json.gz").write_bytes(b"buzilgan")
    await wipe()
    ok2 = await backup.restore_if_empty(FakeBot())
    async with SessionMaker() as s:
        back2 = len(list(await s.scalars(select(User))))
    check(ok2 and back2 == n_users, "eng yangi fayl buzilgan bo'lsa — oldingi butun zaxiradan tiklaydi")
    (d / "obunalar-zaxira-99991231-235959.json.gz").unlink()
    # eskilari tozalanadi: ko'pi bilan LOCAL_KEEP ta
    for i in range(backup.LOCAL_KEEP + 5):
        (d / f"obunalar-zaxira-20200101-{i:06d}.json.gz").write_bytes(good)
    backup.save_local(good)
    check(len(list(d.glob("obunalar-zaxira-*.json.gz"))) == backup.LOCAL_KEEP, f"papkada eng ko'pi {backup.LOCAL_KEEP} ta oxirgi nusxa qoladi")

    print("\nHammasi joyida ✅")


asyncio.run(main())
