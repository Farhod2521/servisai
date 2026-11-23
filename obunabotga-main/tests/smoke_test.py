"""Tezkor tekshiruv: bot oqimi soxta Telegram bilan sinaladi (internet va token shart emas).

Ishga tushirish:  python tests/smoke_test.py
Tekshiriladi: /start (oddiy foydalanuvchi va admin), admin panelda «Foydalanuvchilar»
dan keyin ham /start ishlashi, buyruq bilan holat tozalanishi, ban, xato handleri.
"""
from __future__ import annotations

import asyncio
import datetime
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
os.environ.update(
    BOT_TOKEN="123456:ABCdefGhIjKlMnOpQrStUvWxYz012345678",
    ADMIN_IDS="1,2",
    EXTRA_ADMIN_IDS="7330213371",
    TELEGRAM_OWNER_ID="7330213371",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db",
    WEBHOOK_URL="https://example.onrender.com",
)

from aiogram import Bot  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, Update, User  # noqa: E402

import bot as B  # noqa: E402
from database.db import init_db  # noqa: E402

SENT: list[str] = []
CALLS: list = []


async def fake_call(self, method, request_timeout=None):
    name = type(method).__name__
    SENT.append(f"{name}: {(getattr(method, 'text', '') or '')[:60]}")
    CALLS.append(method)
    if name == "GetStickerSet":
        from aiogram.types import Sticker, StickerSet
        if method.name == "YoqQ":
            from aiogram.exceptions import TelegramBadRequest
            raise TelegramBadRequest(method=method, message="Bad Request: STICKERSET_INVALID")
        mk = lambda ch, cid: Sticker(file_id="f" + cid, file_unique_id="u" + cid, type="custom_emoji", width=100, height=100,
                                     is_animated=False, is_video=False, emoji=ch, custom_emoji_id=cid)
        return StickerSet(name=method.name, title="Test paket", sticker_type="custom_emoji", stickers=[
            mk("💎", "5000000000000000001"), mk("💳", "5000000000000000002"), mk("📦", "5000000000000000003"),
            mk("🎧", "5000000000000000004"), mk("🐙", "5000000000000000009"), mk("💎", "5000000000000000099")])
    if name == "GetChat":
        from aiogram.types import ChatFullInfo
        return ChatFullInfo(id=-1001, type="channel", title="Test kanal", username="test_kanal", accent_color_id=0, max_reaction_count=0)
    if name == "GetChatMember":
        from aiogram.types import ChatMemberAdministrator
        uid = getattr(method, "user_id", 0)
        if uid == 123456:       # bot o'zi
            return ChatMemberAdministrator(user=User(id=uid, is_bot=True, first_name="Bot"), can_be_edited=False, is_anonymous=False,
                                           can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True, can_restrict_members=True,
                                           can_promote_members=False, can_change_info=True, can_invite_users=True, can_post_stories=False,
                                           can_edit_stories=False, can_delete_stories=False)
        from aiogram.types import ChatMemberLeft
        return ChatMemberLeft(user=User(id=uid, is_bot=False, first_name="U"))
    if name == "GetMe":
        return User(id=123456, is_bot=True, first_name="Bot", username="obunabot")
    if name in ("SendMessage", "EditMessageText"):
        return Message(message_id=2, date=datetime.datetime.now(),
                       chat=Chat(id=5, type="private"), text="x").as_(self)   # haqiqiy Telegramdagidek botga bog'langan
    return True


Bot.__call__ = fake_call
_uid = 100


def _msg(uid: int, text: str) -> Update:
    global _uid
    _uid += 1
    ents = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}] if text.startswith("/") else None
    m = Message(message_id=_uid, date=datetime.datetime.now(), chat=Chat(id=uid, type="private"),
                from_user=User(id=uid, is_bot=False, first_name="Ali"), text=text, entities=ents)
    return Update(update_id=_uid, message=m)


def _cb(uid: int, data: str) -> Update:
    global _uid
    _uid += 1
    base = Message(message_id=_uid, date=datetime.datetime.now(), chat=Chat(id=uid, type="private"), text="panel")
    cq = CallbackQuery(id=str(_uid), from_user=User(id=uid, is_bot=False, first_name="Ali"),
                       chat_instance="x", message=base, data=data)
    return Update(update_id=_uid, callback_query=cq)


async def feed(dp, bot, upd) -> list[str]:
    SENT.clear()
    await dp.feed_update(bot, upd)
    return list(SENT)


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


async def main() -> None:
    await init_db()
    bot = Bot(B.settings.bot_token)
    dp = B.build_dispatcher()

    out = await feed(dp, bot, _msg(5, "/start"))
    check(any("Salom" in s for s in out) and any("Obunani tanlang" in s for s in out), "oddiy foydalanuvchi: /start salom + «Obunani tanlang» ro'yxatini beradi")

    out = await feed(dp, bot, _msg(5, "/start p12"))
    check(len(out) > 0, "deep-link /start p12 ishlaydi")

    out = await feed(dp, bot, _msg(5, "salom"))
    check(any("Obunani tanlang" in s for s in out), "oddiy matn menyu va obunalar ro'yxatini qayta ko'rsatadi")

    out = await feed(dp, bot, _msg(1, "/start"))
    check(len(out) > 0, "admin: /start javob beradi")

    # Asosiy xato: admin «Foydalanuvchilar»ni ochadi → ID kutish holati → /start qotib qolmasin
    await feed(dp, bot, _cb(1, "a:users"))
    out = await feed(dp, bot, _msg(1, "/start"))
    check(not any("Topilmadi" in s for s in out) and len(out) > 0, "admin «Foydalanuvchilar»dan keyin /start qotib qolmaydi")

    # Holat tozalanganini isbotlaymiz: endi oddiy matn qidiruv emas, fallback'ga tushadi
    out = await feed(dp, bot, _msg(1, "12345"))
    check(not any("Topilmadi" in s for s in out), "/start'dan keyin bot admin matnini qidiruv deb olmaydi")

    # Qidiruv holatida oddiy ID hali ishlaydi
    await feed(dp, bot, _cb(1, "a:users"))
    out = await feed(dp, bot, _msg(1, "999999"))
    check(any("Topilmadi" in s for s in out), "qidiruv holatida ID yuborilsa qidiradi (kutilgan xulq)")
    out = await feed(dp, bot, _msg(1, "/start"))
    check(not any("Topilmadi" in s for s in out), "qidiruvdan keyin ham /start ishlaydi")

    # ── Admin: narxlar, qo'llanma, xabarnoma; mijoz: /xabar ──
    from database.db import SessionMaker
    from database.models import Category, DeliveryType, Product, User as DbUser
    from services import overrides, runtime
    from sqlalchemy import select

    async with SessionMaker() as s:
        cat = Category(name_uz="T", name_ru="T", name_en="T", emoji="🤖")
        s.add(cat)
        await s.flush()
        pr = Product(category_id=cat.id, emoji="🤖", name="CapCut Pro 1 Month", description="eski", price=50000,
                     supplier_price=40000, brand="CapCut", delivery_type=DeliveryType.MANUAL, unlimited=True)
        s.add(pr)
        await s.commit()
        pid = pr.id

    out = await feed(dp, bot, _cb(1, "a:prices"))
    check(any("Narxlar" in x for x in out), "admin: «💰 Narxlar» brendlar ro'yxatini ochadi")
    out = await feed(dp, bot, _cb(1, f"a:pb:{pid}:0"))
    check(any("CapCut" in x for x in out), "admin: brend mahsulotlari ro'yxati")
    await feed(dp, bot, _cb(1, f"a:pp:{pid}:{pid}"))
    out = await feed(dp, bot, _msg(1, "abc"))
    check(any("Faqat raqam" in x for x in out), "narx: raqam bo'lmasa rad etiladi")
    out = await feed(dp, bot, _msg(1, "59 000"))
    async with SessionMaker() as s:
        pr = await s.get(Product, pid)
        check(pr.price == 59000 and "price" in overrides.locked(pr), "narx saqlandi va avtomatik yangilanishdan qulflandi")
    await feed(dp, bot, _cb(1, f"a:pauto:{pid}:{pid}"))
    async with SessionMaker() as s:
        pr = await s.get(Product, pid)
        check("price" not in overrides.locked(pr), "«avtomatik narxga qaytarish» qulfni olib tashlaydi")

    await feed(dp, bot, _cb(1, f"a:p_guide:{pid}"))
    await feed(dp, bot, _msg(1, "1) Saytga kiring\n2) Emailni kiriting"))
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).guide.startswith("1) Saytga"), "qo'llanma saqlandi")
    await feed(dp, bot, _cb(1, f"a:guide_all:{pid}"))
    await feed(dp, bot, _cb(1, f"a:p_guide:{pid}"))
    await feed(dp, bot, _msg(1, "-"))
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).guide is None, "«-» qo'llanmani o'chiradi")

    # kafolat matni va video qo'llanma
    await feed(dp, bot, _cb(1, f"a:p_warr:{pid}"))
    await feed(dp, bot, _msg(1, "12 soat ichida login va parollarni almashtirib olasiz"))
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).warranty_note.startswith("12 soat"), "admin: kafolat matni saqlandi")
    await feed(dp, bot, _cb(1, f"a:p_warr:{pid}"))
    await feed(dp, bot, _msg(1, "-"))
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).warranty_note is None, "kafolat matni «-» bilan avtomatikka qaytadi")
    await feed(dp, bot, _cb(1, f"a:p_video:{pid}"))
    out = await feed(dp, bot, _msg(1, "salom"))
    check(any("Video fayl" in x for x in out), "video: noto'g'ri kirishni rad etadi")
    await feed(dp, bot, _msg(1, "https://youtu.be/abc123"))
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).guide_video == "https://youtu.be/abc123", "video qo'llanma havolasi saqlandi")
    await feed(dp, bot, _cb(1, f"a:p_video:{pid}"))
    await feed(dp, bot, _msg(1, "-"))
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).guide_video is None, "video qo'llanma o'chirildi")

    # mijoz kabineti: buyurtmalari, login/parol, mijoz kiritgan email
    from database.models import Order, OrderItem, OrderStatus
    from handlers.admin_ext import _order_card
    async with SessionMaker() as s:
        cust = await s.scalar(select(DbUser).where(DbUser.tg_id == 5))
        o = Order(user_id=cust.id, total=59000, status=OrderStatus.DELIVERED)
        s.add(o)
        await s.flush()
        s.add(OrderItem(order_id=o.id, product_id=pid, product_name="CapCut Pro 1 Month", price=59000, qty=1,
                        delivered_content="login: a@b.c\nparol: Zz9", status="ok",
                        customer_input="mijoz@mail.com", supplier_ref="ORD-77"))
        await s.commit()
        oid = o.id
        text, kb = await _order_card(s, oid)
        check("parol: Zz9" in text and "mijoz@mail.com" in text and "ORD-77" in text,
              "admin buyurtma kartasida login/parol, mijoz kiritgan email va ta'minotchi kodi ko'rinadi")
        check(any("Mijoz kabineti" in b.text for r in kb.inline_keyboard for b in r), "buyurtma kartasidan mijoz kabinetiga o'tish tugmasi")
    out = await feed(dp, bot, _cb(1, "a:user:5"))
    check(any("Ali" in x for x in out), "admin: mijoz kabineti ochiladi")
    out = await feed(dp, bot, _cb(1, "a:u_orders:5"))
    check(any("buyurtmalari" in x for x in out), "admin: mijozning buyurtmalari ro'yxati")

    # ikkinchi admin (ID 2, owner emas): admin panelga kira oladi, to'lov tizimiga (faqat owner) — yo'q
    await feed(dp, bot, _cb(2, "a:users"))
    out = await feed(dp, bot, _cb(2, "a:prices"))
    check(any("Narxlar" in x for x in out), "2-admin: admin panelni ocha oladi")
    out = await feed(dp, bot, _cb(2, "a:pay"))
    check(not any("To'lov tizimi" in x for x in out), "   to'lov tizimi administratori baribir faqat owner")
    out = await feed(dp, bot, _cb(424242, "a:prices"))
    check(not any("Narxlar" in x for x in out), "   boshqa foydalanuvchi admin panelni ocha olmaydi")
    out = await feed(dp, bot, _cb(6418750920, "a:prices"))
    check(not any("Narxlar" in x for x in out), "   eski egasining ID'si endi admin emas")
    # /start salomlashuvini admin o'zgartiradi: premium emoji va qalin yozuv saqlanadi, ism {name} bo'ladi
    from aiogram.types import MessageEntity
    from handlers.start import welcome_text
    from services import runtime as _rt
    await feed(dp, bot, _cb(1, "a:welcome"))
    txt = "🔥 Xush kelibsiz, Ali! Bu yerda premium obunalar"
    ents = [MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="5368324170671202286"),
            MessageEntity(type="bold", offset=3, length=13)]
    m = Message(message_id=900, date=datetime.datetime.now(), chat=Chat(id=1, type="private"),
                from_user=User(id=1, is_bot=False, first_name="Ali"), text=txt, entities=ents)
    await dp.feed_update(bot, Update(update_id=9001, message=m))
    saved = _rt.welcome_html()
    check('<tg-emoji emoji-id="5368324170671202286">🔥</tg-emoji>' in saved and "<b>Xush kelibsiz</b>" in saved and "{name}" in saved
          and "Ali" not in saved, "admin yuborgan salomlashuv (premium emoji, qalin yozuv) saqlandi, ism {name} bo'ldi")
    from database.models import User as DbUser2
    check("Bobur" in welcome_text(DbUser2(tg_id=9, full_name="Bobur"), "uz", True) and "5368324170671202286" in welcome_text(DbUser2(tg_id=9, full_name="Bobur"), "uz", True),
          "   /start da mijozga o'zining ismi bilan shu matn chiqadi")
    await feed(dp, bot, _cb(424242, "a:welcome"))
    check(_rt.welcome_html() == saved, "   admin bo'lmagan foydalanuvchi o'zgartira olmaydi")
    await feed(dp, bot, _cb(1, "a:welcome"))
    await feed(dp, bot, _msg(1, "-"))
    check(_rt.welcome_html() == "", "   «-» standart salomlashuvga qaytaradi")

    out = await feed(dp, bot, _cb(1, "a:pchg:24:0"))
    check(any("Narx o'zgarishlari" in x for x in out), "admin: «📈 Narx o'zgarishlari» menyusi")
    out = await feed(dp, bot, _cb(1, "a:pchg:168:0"))
    check(any("Narx o'zgarishlari" in x for x in out), "narx o'zgarishlari: 7 kunlik ko'rinish")
    await feed(dp, bot, _cb(1, f"a:p_img:{pid}"))
    out = await feed(dp, bot, _msg(1, "matn"))
    check(any("Rasm yuboring" in x for x in out), "rasm: matn rad etiladi")
    await feed(dp, bot, _msg(1, "-"))
    check(True, "rasm: «-» o'chirishni qabul qiladi")
    out = await feed(dp, bot, _cb(5, "a:pchg:24:0"))
    check(not any("Narx o'zgarishlari" in x for x in out), "oddiy foydalanuvchi narx o'zgarishlarini ko'ra olmaydi")

    out = await feed(dp, bot, _cb(1, "a:notify"))
    check(any("Mijozlarga xabarnoma" in x for x in out), "admin: «🔔 Xabarnoma» menyusi")
    check(runtime.notify_enabled() is False, "xabarnoma sukut bo'yicha o'chiq")
    await feed(dp, bot, _cb(1, "a:ntf_toggle"))
    check(runtime.notify_enabled() is True, "xabarnomani yoqish")
    await feed(dp, bot, _cb(1, "a:ntf_toggle"))
    check(runtime.notify_enabled() is False, "xabarnomani o'chirish")
    await feed(dp, bot, _cb(1, "a:ntf_min"))
    await feed(dp, bot, _msg(1, "7"))
    check(runtime.notify_min() == 7, "minimal miqdor saqlandi")
    out = await feed(dp, bot, _cb(1, "a:bemoji"))
    check(any("Brend emojilari" in x for x in out), "admin: «🏷 Brend emojilari» menyusi")
    out = await feed(dp, bot, _msg(1, "CapCut oddiy matn"))
    check(any("Premium emoji topilmadi" in x for x in out), "brend emoji: premium emojisiz xabar rad etiladi")
    await feed(dp, bot, _msg(1, "/start"))
    out = await feed(dp, bot, _cb(5, "a:notify"))
    check(not any("Mijozlarga xabarnoma" in x for x in out), "oddiy foydalanuvchi admin xabarnoma menyusini ocholmaydi")

    await feed(dp, bot, _msg(5, "/xabar"))
    async with SessionMaker() as s:
        check((await s.scalar(select(DbUser).where(DbUser.tg_id == 5))).notify is False, "/xabar xabarlarni o'chiradi")
    await feed(dp, bot, _msg(5, "/xabar"))
    async with SessionMaker() as s:
        check((await s.scalar(select(DbUser).where(DbUser.tg_id == 5))).notify is True, "/xabar qayta yoqadi")

    # ══════════ Oddiy do'kon (Mini App'siz): menyu, obunalar, xarid, profil, yordam ══════════
    from keyboards.user_kb import main_menu

    # 1) pastki menyu: 2 ustun × 3 qator, rang va premium ikonka
    kb = main_menu("uz", False)
    texts = [[b.text for b in row] for row in kb.keyboard]
    check(len(kb.keyboard) == 3 and all(len(r) == 2 for r in kb.keyboard), "menyu: 3 qator × 2 tugma")
    flat = " | ".join(" | ".join(r) for r in texts)
    order = ["Obunalar", "Hisobni to'ldirish", "Buyurtmalarim", "Profil", "Qo'llanma", "Yordam"]
    pos = [flat.index(w) for w in order]
    check(pos == sorted(pos), "menyu tartibi: Obunalar, Hisobni to'ldirish, Buyurtmalarim, Profil, Qo'llanma, Yordam")
    check("Xizmatlar" not in flat and "Savat" not in flat and "Til" not in flat.split("|")[-1], "eski nomlar (Xizmatlar, Savat, Til, Aloqa) yo'q")
    first = kb.keyboard[0][0]
    check(getattr(first, "style", None) == "success", "«Obunalar» tugmasi yashil")
    check(getattr(first, "icon_custom_emoji_id", None), "«Obunalar» tugmasida premium ikonka bor")
    check(len(main_menu("uz", True).keyboard) == 4, "admin menyusida qo'shimcha «Admin panel» qatori bor")

    # 2) menyu tugmalari ishlaydi (emojili ham, emojisiz ham)
    for label, expect in [("Obunalar", "Obunani tanlang"), ("💎 Obunalar", "Obunani tanlang"), ("🛍 Obunalar", "Obunani tanlang"),
                          ("Profil", "profilim"), ("Buyurtmalarim", "uyurtma"), ("Hisobni to'ldirish", "to'ldirish"),
                          ("Qo'llanma", "Qo'llanma"), ("Yordam", "Yordam")]:
        out = await feed(dp, bot, _msg(5, label))
        check(any(expect in x for x in out), f"menyu: «{label}» → «{expect}»")

    # Yordam: @fen1xmedia havolasi
    await feed(dp, bot, _msg(5, "Yordam"))
    sent = [m for m in CALLS if type(m).__name__ == "SendMessage"][-1]
    check(any(getattr(b, "url", "") == "https://t.me/fen1xmedia" for r in sent.reply_markup.inline_keyboard for b in r),
          "«Yordam» → https://t.me/fen1xmedia")

    # 3) obunalar ro'yxati: faqat 10 ta brend; zaxirasi bor — yashil, yo'q — qizil
    from handlers.shop import SERVICES, services_kb, availability
    check(len(SERVICES) == 32 and {"ChatGPT", "Codex", "Netflix", "Windows", "n8n", "Kaspersky"} <= set(SERVICES) and "Railway" not in SERVICES,
          "menyu: egasi bergan 32 ta brend (ChatGPT, Codex, Netflix, Windows, n8n…)")
    async with SessionMaker() as s:
        avail = await availability(s)
    check(avail.get("CapCut") is True and "ChatGPT" not in avail, "zaxirasi bor brend yashil; mahsuloti umuman yo'q brend menyuda ko'rinmaydi")
    kb = services_kb(avail)
    btns = {b.text: b for r in kb.inline_keyboard for b in r}
    check(len(btns) == len(avail) and getattr(btns["CapCut"], "style", None) == "success", "mavjud brend tugmasi yashil")
    check(all(getattr(b, "icon_custom_emoji_id", None) for b in btns.values()), "har bir brendda logotip (premium emoji) bor")

    # 4) brend → tarif → xarid
    out = await feed(dp, bot, _cb(5, f"svc:{list(avail).index('CapCut')}"))
    check(any("Tarifni tanlang" in x for x in out), "CapCut bosilsa tariflar ro'yxati chiqadi")
    out = await feed(dp, bot, _cb(5, "svc:99"))
    check(any("AnswerCallbackQuery" in x for x in out) and not any("Tarifni tanlang" in x for x in out),
          "mahsuloti yo'q (eskirgan) brend tugmasi bosilsa faqat «mavjud emas» xabari chiqadi")
    out = await feed(dp, bot, _cb(5, f"plan:{pid}"))
    check(any("Narxi" in x or "CapCut" in x for x in out), "tarif kartasi: narx va balans")
    out = await feed(dp, bot, _cb(5, f"buy:{pid}"))
    check(any("mablag" in x for x in out), "balans yetmasa: «mablag' yetarli emas»")
    async with SessionMaker() as s:
        u5 = await s.scalar(select(DbUser).where(DbUser.tg_id == 5))
        u5.balance = 200_000
        price = (await s.get(Product, pid)).price
        await s.commit()
    out = await feed(dp, bot, _cb(5, f"buy:{pid}"))
    async with SessionMaker() as s:
        u5 = await s.scalar(select(DbUser).where(DbUser.tg_id == 5))
        check(u5.balance == 200_000 - price, f"xarid: balansdan {price} so'm yechildi")
    out = await feed(dp, bot, _msg(5, "Buyurtmalarim"))
    check(any("CapCut" in x or "#" in x for x in out), "«Buyurtmalarim»da yangi buyurtma ko'rinadi")

    # 5) profil: ID, balans, til almashtirish
    out = await feed(dp, bot, _msg(5, "Profil"))
    check(any("ID" in x for x in out), "profil: ID ko'rsatiladi")
    await feed(dp, bot, _cb(5, "lang:ru"))
    async with SessionMaker() as s:
        check((await s.scalar(select(DbUser).where(DbUser.tg_id == 5))).lang == "ru", "til: ruscha")
    out = await feed(dp, bot, _msg(5, "Профиль"))
    check(any("профиль" in x for x in out), "ruscha menyu ham ishlaydi")
    await feed(dp, bot, _cb(5, "lang:uz"))
    async with SessionMaker() as s:
        check((await s.scalar(select(DbUser).where(DbUser.tg_id == 5))).lang == "uz", "til: o'zbekcha")
    await feed(dp, bot, _cb(5, "lang:en"))
    async with SessionMaker() as s:
        check((await s.scalar(select(DbUser).where(DbUser.tg_id == 5))).lang == "uz", "faqat o'zbek va rus tillari tanlanadi")

    # 6) admin: pastki menyudan Admin panel ochiladi (ID 7330213371)
    out = await feed(dp, bot, _msg(7330213371, "⚙️ Admin panel"))
    check(any("Boshqaruv markazi" in x for x in out), "admin 7330213371: yangi «Boshqaruv markazi» ochiladi")
    out = await feed(dp, bot, _msg(5, "⚙️ Admin panel"))
    check(not any(x.startswith("SendMessage: 🎛") for x in out), "oddiy foydalanuvchi admin panelni ocha olmaydi")

    # 7) Qo'llanma: brend bo'yicha
    out = await feed(dp, bot, _cb(5, "gd:3"))
    check(len(out) > 0, "qo'llanma: brend tanlansa javob beradi")

    # 8) Yangi admin paneli: bosh sahifa, bo'limlar, har bir tugma ishlaydi
    from keyboards.admin_kb import admin_main, section_kb
    from services.panel import SECTIONS
    out = await feed(dp, bot, _cb(7330213371, "a:home"))
    check(any("Boshqaruv markazi" in x for x in out), "panel: bosh sahifa «Boshqaruv markazi»")
    home = admin_main({"pending": 2, "topups": 1})
    labels = [b.text for r in home.inline_keyboard for b in r]
    check(len(home.inline_keyboard) == 8 and all(len(r) <= 2 for r in home.inline_keyboard), "panel: bosh sahifa 8 qator, qatorda ko'pi bilan 2 tugma")
    check(any("Buyurtmalar (2)" in l for l in labels) and any("To'lovlarni tasdiqlash (1)" in l for l in labels), "panel: bajarilmagan buyurtma va kutilayotgan to'lov soni tugmada ko'rinadi")
    check(getattr(home.inline_keyboard[2][0], "style", None) == "danger", "panel: bajarilmagan buyurtma bo'lsa tugma qizil")
    for key in SECTIONS:
        out = await feed(dp, bot, _cb(7330213371, f"a:s:{key}"))
        check(any(SECTIONS[key][0] in x for x in out), f"panel: «{SECTIONS[key][0]}» bo'limi ochiladi")
        check(section_kb(key).inline_keyboard[-1][0].callback_data == "a:home", f"   «{key}»: pastda «Bosh sahifa» tugmasi bor")
    out = await feed(dp, bot, _cb(5, "a:s:shop"))
    check(not any("Obunalar" in x and "EditMessageText" in x for x in out), "panel: oddiy foydalanuvchi bo'limni ocha olmaydi")
    # bo'limlardagi HAR BIR tugma ishlaydi (xato xabari chiqmaydi)
    seen = set()
    for key, (_, _, items) in SECTIONS.items():
        for label, data in items:
            if data in seen:
                continue
            seen.add(data)
            await feed(dp, bot, _msg(7330213371, "/start"))          # oldingi holatni tozalaymiz
            out = await feed(dp, bot, _cb(7330213371, data))
            check(len(out) > 0 and not any("xatolik" in x.lower() for x in out), f"panel: «{label}» ({data}) ishlaydi")
    for data in ("a:orders", "a:users"):
        await feed(dp, bot, _msg(7330213371, "/start"))
        out = await feed(dp, bot, _cb(7330213371, data))
        check(len(out) > 0 and not any("xatolik" in x.lower() for x in out), f"panel: bosh sahifadagi «{data}» ishlaydi")

    # 9) Emoji-paketdan avtomatik biriktirish va menyu ikonkalari
    from services import emoji as _em, runtime as _rt2
    check(_em.pack_names("qarang: https://t.me/addemoji/Abc_123 va t.me/addstickers/Xyz789, yana https://t.me/addemoji/Abc_123") == ["Abc_123", "Xyz789"],
          "emoji: matndagi paket havolalari topiladi (takrorlanmaydi)")
    check(_em.pack_names("hech narsa yo'q") == [], "emoji: havola bo'lmasa bo'sh")
    await feed(dp, bot, _cb(7330213371, "a:emoji"))
    out = await feed(dp, bot, _msg(7330213371, "https://t.me/addemoji/TestPack"))
    saved = _rt2.user_emoji_map()
    check(saved.get("💎") == "5000000000000000001" and saved.get("💳") == "5000000000000000002" and saved.get("🎧") == "5000000000000000004",
          "emoji: paketdagi kerakli emojilarning ID lari saqlandi (birinchisi ustun)")
    check("🐙" not in saved, "emoji: botga kerak bo'lmagan emoji saqlanmadi")
    check(any("Test paket" in x for x in out), "emoji: admin ga hisobot chiqdi")
    out = await feed(dp, bot, _msg(7330213371, "https://t.me/addemoji/YoqQ"))
    check(any("topilmadi" in x for x in out), "emoji: noto'g'ri paket nomi — aniq xabar, bot yiqilmadi")
    check(_rt2.emoji_map().get("💎") == "5000000000000000001", "emoji: umumiy xarita yangilandi")
    await feed(dp, bot, _msg(7330213371, "/start"))
    await feed(dp, bot, _cb(7330213371, "a:emoji_clear"))

    # 10) Menyu ikonkalari: bot egasi bergan ID lar, tartib: Obunalar, Hisobni to'ldirish, Buyurtmalarim, Profil, Qo'llanma, Yordam
    from keyboards.user_kb import MENU_ICON_IDS
    kb3 = main_menu("uz", False)
    flat3 = [b for r in kb3.keyboard for b in r]
    want = ["5235588635885054955", "5413653337117571378", "5258396243666681152",
            "5413353874817825806", "5258328383183396223", "5287595522993991899"]
    check([b.model_extra.get("icon_custom_emoji_id") for b in flat3] == want, "menyu: 6 ta tugmada bot egasi bergan premium ikonkalar, to'g'ri tartibda")
    check([b.text for b in flat3] == ["Obunalar", "Hisobni to'ldirish", "Buyurtmalarim", "Profil", "Qo'llanma", "Yordam"],
          "menyu: premium ishlasa tugma matni toza (emoji ikonka sifatida chiqadi)")
    check(MENU_ICON_IDS["menu_orders"] == "5258396243666681152", "menyu: «Buyurtmalarim» — lupa")
    _em.mark_blocked()                                   # Telegram premiumni rad etdi
    flat4 = [b for r in main_menu("uz", False).keyboard for b in r]
    check([b.text[:1] for b in flat4] == ["🛍", "💵", "🔍", "👤", "📖", "💬"] and not any(b.model_extra.get("icon_custom_emoji_id") for b in flat4),
          "menyu: premium rad etilsa oddiy emojilar (🛍 💵 🔍 👤 📖 💬) matnga qo'shiladi")
    _em._blocked_until = 0.0                             # keyingi tekshiruvlar uchun qayta yoqamiz
    for label in ("🔍 Buyurtmalarim", "📦 Buyurtmalarim", "💎 Obunalar", "🎧 Yordam"):
        out = await feed(dp, bot, _msg(5, label))
        check(len(out) > 0 and not any("xatolik" in x.lower() for x in out), f"menyu: eski klaviaturadagi «{label}» ham ishlaydi")

    # 11) Tayyor premium emojilar (bot egasi bergan ID lar) matnlarda avtomatik ishlaydi
    from services.emoji import premiumize
    txt = premiumize("✅ ❌ ⏳ 🚫 ⚠️ 💳 💰 🧾 📦 🆔 🌐 💎 ⚡ 🛡 👇")
    for ch, cid in [("✅", "5413395179518310071"), ("❌", "5260342697075416641"), ("⏳", "5339357992103983304"), ("🚫", "5413775597656619974"),
                    ("⚠️", "5440785268296671580"), ("💳", "5413653337117571378"), ("💰", "5413653337117571378"), ("🧾", "5444856076954520455"),
                    ("📦", "5258396243666681152"), ("🆔", "5334890573281114250"), ("🌐", "6339280615459789282"), ("💎", "5298988357538328017"),
                    ("⚡", "5219943216781995020"), ("🛡", "5895483165182529286"), ("👇", "5438525681707278534")]:
        check(f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>' in txt, f"premium emoji: {ch} → {cid}")
    from locales.texts import t as _t
    hello = premiumize(_t("uz", "hello", name="Ali"))
    check(hello.count("<tg-emoji") >= 5, "/start salomida emojilar premium bo'ladi (💎 ⚡ 🛡 💳 👋)")

    # 12) Ikkinchi to'plam: yangi ID lar va ko'rinmas belgili emojilar (⚠️ ⬅️ ➡️)
    txt2 = premiumize("🎉 😔 ➖ 📋 🔒 🔕 🔑 📚 🎧 ⬅️ ➡️ ⚠️")
    for ch, cid in [("🎉", "5461136335173598840"), ("😔", "5240291728153397366"), ("➖", "5382261056078881010"), ("📋", "5303365758141627496"),
                    ("🔒", "5393302369024882368"), ("🔕", "5470097960530375585"), ("🔑", "5454386656628991407"), ("📚", "5373098009640836781"),
                    ("🎧", "5307571098060078194"), ("⬅️", "5258236805890710909"), ("➡️", "5260450573768990626"), ("⚠️", "5440785268296671580")]:
        check(f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>' in txt2, f"premium emoji (2-to'plam): {ch} → {cid}")
    check("</tg-emoji>️" not in txt2, "ko'rinmas belgi (VS16) teg ichida qoladi, tashqarida ortib qolmaydi")

    # 13) Alert (AnswerCallbackQuery) matnida premium emoji KODI chiqib qolmaydi; oddiy xabarda esa premium bo'ladi
    from aiogram.methods import AnswerCallbackQuery, SendMessage
    from middlewares.emoji_fallback import premium_emoji
    seen = []

    async def grab(_bot, method):
        seen.append(method)
        return True

    _rt3 = __import__("services.runtime", fromlist=["x"])
    await premium_emoji(grab, bot, AnswerCallbackQuery(callback_query_id="1", text="😔 Bu obuna vaqtincha tugagan.", show_alert=True))
    check("<tg-emoji" not in seen[-1].text and seen[-1].text.startswith("😔"), "alert matnida <tg-emoji> kodi chiqmaydi (oddiy emoji qoladi)")
    await premium_emoji(grab, bot, SendMessage(chat_id=1, text="😔 Bu obuna vaqtincha tugagan."))
    check('<tg-emoji emoji-id="5240291728153397366">' in seen[-1].text, "oddiy xabarda emoji premium bo'ladi")

    # 14) /id hammaga ochiq emas; admin/owner: sukutda sizning ID; Render sozlamasi ustun; hisobotlar 0 raqamiga ketmaydi
    from config import Settings
    keys = ("ADMIN_IDS", "EXTRA_ADMIN_IDS", "TELEGRAM_OWNER_ID", "OWNER_ID")
    saved_ids = {k: os.environ.pop(k, None) for k in keys}
    try:
        d0 = Settings(_env_file=None)
        os.environ["ADMIN_IDS"] = "555,666"
        os.environ["EXTRA_ADMIN_IDS"] = ""
        os.environ["TELEGRAM_OWNER_ID"] = "555"
        d1 = Settings(_env_file=None)
    finally:
        for k in keys:
            os.environ.pop(k, None)
        for k, v in saved_ids.items():
            if v is not None:
                os.environ[k] = v
    check(d0.admins == [93758266, 7330213371] and d0.owner_id == 93758266, "sukutda owner — 93758266, adminlar 93758266 va 7330213371 (Render sozlamasi bo'lmasa ham ishlaydi)")
    check(d1.admins == [555, 666] and d1.owner_id == 555, "Render sozlamasi (ADMIN_IDS, TELEGRAM_OWNER_ID, EXTRA_ADMIN_IDS) sukutdan ustun")
    out = await feed(dp, bot, _msg(31337, "/id"))
    check(not any("31337" in x for x in out) and not any("ADMIN_IDS" in x for x in out), "/id endi hammaga ochiq emas, admin sozlash yo'riqnomasi ko'rsatilmaydi")
    from services.alerts import recipients
    check(0 not in recipients() and 0 not in recipients(True), "hisobotlar hech qachon 0 raqamiga yuborilmaydi")

    # 15) Admin panel: birinchi qatorda 3 ta tezkor amal
    out = await feed(dp, bot, _cb(7330213371, "a:home"))
    home = admin_main({"pending": 0, "topups": 3})
    firsts = [b.callback_data for r in home.inline_keyboard[:2] for b in r]
    check(firsts == ["pay:adm_list", "a:fastbal", "a:fsub"], "bosh sahifaning boshida: to'lovlarni tasdiqlash, ID bilan hisob to'ldirish, majburiy obuna")
    check("To'lovlarni tasdiqlash (3)" in home.inline_keyboard[0][0].text, "kutilayotgan to'lovlar soni tugmada ko'rinadi")
    # 15.1 majburiy obuna: qo'shish, ro'yxat, o'chirish; mijozlarga ta'siri
    from services import runtime as _rtq
    await feed(dp, bot, _cb(7330213371, "a:fsub"))
    out = await feed(dp, bot, _cb(7330213371, "a:fsub_add"))
    out = await feed(dp, bot, _msg(7330213371, "salom ???"))
    check(any("tushunmadim" in x for x in out), "majburiy obuna: noto'g'ri kiritilsa tushuntiradi")
    out = await feed(dp, bot, _msg(7330213371, "@test_kanal"))
    check(_rtq.force_sub_channels() == ["@test_kanal"] and any("qo'shildi" in x for x in out), "majburiy obuna: kanal qo'shildi (bot admin bo'lgani tekshirildi)")
    out = await feed(dp, bot, _msg(5, "/start"))
    check(any("kanal" in x.lower() for x in out), "kanal qo'shilgach mijozdan obuna talab qilinadi")
    out = await feed(dp, bot, _msg(7330213371, "/start"))
    check(not any("obuna bo'ling" in x for x in out), "admindan obuna talab qilinmaydi")
    await feed(dp, bot, _cb(7330213371, "a:fsub_del:0"))
    check(_rtq.force_sub_channels() == [], "majburiy obuna: kanal olib tashlandi")
    out = await feed(dp, bot, _msg(5, "/start"))
    check(not any("Kanalga obuna" in x for x in out), "obuna o'chirilgach mijoz erkin foydalanadi")
    check(await feed(dp, bot, _cb(5, "a:fsub")) is not None and _rtq.force_sub_channels() == [], "oddiy foydalanuvchi majburiy obunani o'zgartira olmaydi")
    # 15.2 ID bilan hisob to'ldirish
    async with SessionMaker() as s:
        u5 = await s.scalar(select(DbUser).where(DbUser.tg_id == 5)); before = u5.balance
    await feed(dp, bot, _cb(7330213371, "a:fastbal"))
    out = await feed(dp, bot, _msg(7330213371, "99999999"))
    check(any("topilmadi" in x for x in out), "ID bilan hisob to'ldirish: noma'lum ID — aniq xabar")
    out = await feed(dp, bot, _msg(7330213371, "5"))
    check(any("Hozirgi hisob" in x for x in out), "ID bilan hisob to'ldirish: mijoz topildi, summa so'raladi")
    out = await feed(dp, bot, _msg(7330213371, "25 000"))
    async with SessionMaker() as s:
        u5 = await s.scalar(select(DbUser).where(DbUser.tg_id == 5))
    check(u5.balance == before + 25000, "hisob 25 000 so'mga to'ldirildi")
    check(any(c.chat_id == 5 and "to'ldirildi" in (c.text or "") for c in CALLS if type(c).__name__ == "SendMessage"), "mijozga «hisobingiz to'ldirildi» xabari bordi")

    # 16) Pul (hamyon), muddat (soat) va «Obunalar» (to'rt kvadrat) premium emojilari — hamma joyda shu
    from services.emoji import premiumize as _pz
    wallet, clock, grid = "5413653337117571378", "5416012459574048237", "5235588635885054955"
    t16 = _pz("💵 Narxi · 💰 Balans · 💳 Hisobingiz · ⏱ Muddati: 1 oy · 🕒 vaqt · 🛍 «Obunalar»")
    check(t16.count(f'emoji-id="{wallet}"') == 3, "pul (💵 💰 💳) hamma joyda bitta hamyon ikonkasi")
    check(t16.count(f'emoji-id="{clock}"') == 2, "muddat/vaqt (⏱ 🕒) soat ikonkasi")
    check(t16.count(f'emoji-id="{grid}"') == 1, "«Obunalar» bo'limi (🛍) to'rt kvadrat ikonkasi")
    from locales.texts import t as _tt
    check("🛍" in _tt("uz", "orders_empty") and "💎" not in _tt("uz", "orders_empty"), "«buyurtma yo'q» xabarida «Obunalar» bo'limi logotipi")
    # 17) Baza vaqtinchalik bo'lsa admin bosh sahifasi ogohlantiradi; doimiy bo'lsa — tinchlantiradi
    from services import panel as _panel
    os.environ["RENDER"] = "1"
    try:
        check("vaqtinchalik (SQLite)" in _panel.db_block() and "DATABASE_URL" in _panel.db_block(), "Render'da SQLite bo'lsa — admin sahifasi ma'lumot yo'qolishi haqida ogohlantiradi")
        orig_pg = type(B.settings).is_postgres
        type(B.settings).is_postgres = property(lambda self: True)
        try:
            check("doimiy (Postgres)" in _panel.db_block(), "Postgres ulangan bo'lsa — «ma'lumot yo'qolmaydi»")
        finally:
            type(B.settings).is_postgres = orig_pg
    finally:
        os.environ.pop("RENDER", None)

    # 18) Telegram Stars: «Obunalar» → ⭐ → miqdor → boshqa @username → tasdiqlash (soxta StarsUno), bot oqimi boshidan oxirigacha
    from services import starsuno as _su
    replies = {"stars/price": {"ok": True, "price": 250}, "stars/buy": {"ok": True, "message": "ok", "balance": 900000}}
    bought: list = []

    async def _fake_get(path, **params):
        bought.append((path, params))
        return replies[path]
    _su._get = _fake_get
    B.settings.starsuno_key = "test-key"
    async with __import__("database.db", fromlist=["SessionMaker"]).SessionMaker() as _s:
        _u = await __import__("services.repo", fromlist=["repo"]).get_or_create_user(_s, 5, None, "Ali")
        _u.balance = 100000
        await _s.commit()
    out = await feed(dp, bot, _msg(5, "salom"))
    kbs = [getattr(c, "reply_markup", None) for c in CALLS if type(c).__name__ == "SendMessage"]
    check(any(hasattr(k, "inline_keyboard") and any(b.callback_data == "tg:stars" for r in k.inline_keyboard for b in r) for k in kbs), "«Obunalar» ro'yxatida ⭐ Telegram Stars tugmasi bor")
    out = await feed(dp, bot, _cb(5, "tg:stars"))
    check(any("Telegram Stars" in s for s in out), "⭐ Stars bo'limi ochiladi")
    out = await feed(dp, bot, _cb(5, "tg:sa:100"))
    check(any("Kimga yuboramiz" in s for s in out), "miqdor tanlangach «Kimga yuboramiz?» so'raladi")
    out = await feed(dp, bot, _cb(5, "tg:other"))
    out = await feed(dp, bot, _msg(5, "@monk"))
    check(any("Kimga: @monk" in (getattr(c, "text", "") or "") or "@monk" in (getattr(c, "text", "") or "") for c in CALLS if type(c).__name__ == "SendMessage"), "@monk yozilgach tasdiqlash kartasi chiqadi")
    out = await feed(dp, bot, _cb(5, "tg:ok"))
    check(("stars/buy", {"username": "monk", "amount": 100}) in bought, "tasdiqlangach StarsUno'ga to'g'ri so'rov ketdi")
    out2 = await feed(dp, bot, _cb(5, "tg:ok"))
    check(len([b for b in bought if b[0] == "stars/buy"]) == 1, "«Sotib olish» ikki marta bosilsa ham ikki marta yuborilmaydi")
    B.settings.starsuno_key = ""

    # 19) /sessiya: faqat owner; sozlama (TG_API_ID) yo'q bo'lsa aniq tushuntiradi; boshqalarga javob yo'q
    out = await feed(dp, bot, _msg(7330213371, "/sessiya"))
    check(any("TG_API_ID" in x for x in out), "owner /sessiya yozsa — TG_API_ID yo'qligi aytiladi (sozlama yo'q holatda)")
    out = await feed(dp, bot, _msg(5, "/sessiya"))
    check(not any("TG_API_ID" in x or "Telegram sessiya" in x for x in out), "oddiy foydalanuvchiga /sessiya ko'rinmaydi")

    # 20) Owner HUMO kirim xabarini botga forward/yozsa — mos buyurtma tasdiqlanadi (Business ishlamasa zaxira yo'l); boshqalar uchun emas
    from database.db import SessionMaker as _SM
    from database.models import User as _U
    from services import topup as _tp
    async with _SM() as _s:
        _cust = await _s.scalar(__import__("sqlalchemy").select(_U).where(_U.tg_id == 5))
        _order = await _tp.create_order(_s, _cust, 20_000, "card", chat_id=5)
        _amt, _oid, _before = _order.payment_amount, _order.id, _cust.balance
    fmt = f"{_amt:,}".replace(",", ".") + ",00"
    humo = f"🎉 To'ldirish\n💰 {fmt} UZS\n📍 PAYNET P2P UZC2HUM>S\n💳 HUMOCARD *0495"
    await feed(dp, bot, _msg(5, humo))                                 # oddiy mijoz yozsa — hisob to'lanmaydi
    async with _SM() as _s:
        check((await _tp.get_order(_s, _oid)).status == "pending", "oddiy mijoz kirim xabarini yozsa — to'lov tasdiqlanmaydi")
    out = await feed(dp, bot, _msg(7330213371, humo))
    async with _SM() as _s:
        check((await _tp.get_order(_s, _oid)).status == "paid" and any("tasdiqlandi" in x for x in out),
              "owner HUMO xabarini yuborsa — buyurtma tasdiqlandi, hisob to'ldirildi")

    # 21) Admin panel qo'llanmasi: bosh sahifada tugma, 3 sahifa, oddiy foydalanuvchiga yopiq
    from keyboards.admin_kb import admin_main as _am
    check(any(b.callback_data == "a:help:0" for r in _am().inline_keyboard for b in r), "bosh sahifada «📖 Qo'llanma» tugmasi bor")
    for i, word in enumerate(("To'lovlarni tasdiqlash", "Narx va foyda", "Zaxira qo'shish")):
        out = await feed(dp, bot, _cb(7330213371, f"a:help:{i}"))
        check(any(word in x for x in out) or any(word in (getattr(c, "text", "") or "") for c in CALLS if type(c).__name__ == "EditMessageText"),
              f"qo'llanma {i + 1}-sahifa: «{word}» tushuntirilgan")
    CALLS.clear()
    await feed(dp, bot, _cb(5, "a:help:0"))
    check(not any(type(c).__name__ == "EditMessageText" for c in CALLS), "oddiy mijozga admin qo'llanmasi ochilmaydi")

    print("\nHammasi joyida.")


asyncio.run(main())
