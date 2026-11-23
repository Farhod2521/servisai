"""Yangi obuna / zaxira xabarnomalari, qo'llanma va tavsif yashirish (internet va token shart emas).

Ishga tushirish:  python tests/test_notify.py
"""
from __future__ import annotations

import asyncio
import json
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
    EXTRA_ADMIN_IDS="7330213371",
    TELEGRAM_OWNER_ID="7330213371",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db",
    CANBOSO_API_KEY="test-key",
    USD_TO_UZS="12000",
    CATALOG_MARKUP_PERCENT="25",
)

from aiogram.exceptions import TelegramForbiddenError  # noqa: E402
from sqlalchemy import select  # noqa: E402

from database.db import SessionMaker, init_db  # noqa: E402
from database.models import Product, User  # noqa: E402
from services import announce, canboso, overrides, runtime  # noqa: E402
from services.notify import order_success_text  # noqa: E402
from webapp import api  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def items(n: int, avail: dict[int, int] | None = None, extra: list[dict] | None = None) -> list[dict]:
    avail = avail or {}
    base = [
        {"productId": str(i), "name": f"CapCut Pro {i} Month 30 Days Warranty", "price": {"amount": 3.5},
         "availability": {"available": avail.get(i, 5)}, "productType": "account"}
        for i in range(1, n + 1)
    ]
    return base + (extra or [])


async def run_sync(raw, auto=True):
    async with SessionMaker() as s:
        return await canboso.sync(s, raw, auto=auto)


class FakeBot:
    async def send_photo(self, chat_id, photo, caption=None, reply_markup=None, **kw):
        self.sent.append((chat_id, caption or "", reply_markup))
        self.photos.append((chat_id, photo))

    def __init__(self, forbidden: set[int] = frozenset()):
        self.photos = []
        self.edits = []
        self.sent: list[tuple[int, str, object]] = []
        self.forbidden = forbidden

    async def get_me(self):
        class Me:
            username = "obunalar_bot"
        return Me()

    async def edit_message_reply_markup(self, chat_id=None, message_id=None, reply_markup=None, **kw):
        if getattr(self, "edit_fail", None):
            raise self.edit_fail
        self.edits.append((chat_id, message_id, reply_markup))

    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        if chat_id in self.forbidden:
            raise TelegramForbiddenError(method=None, message="blocked")
        self.sent.append((chat_id, text, reply_markup))


async def _vid(bot, chat_id, vid, caption):
    bot.sent.append((chat_id, caption or "", vid))


async def add_users() -> None:
    async with SessionMaker() as s:
        s.add_all([User(tg_id=101, full_name="A", lang="uz"), User(tg_id=102, full_name="B", lang="ru"),
                   User(tg_id=103, full_name="C", lang="uz", notify=False),
                   User(tg_id=104, full_name="D", lang="uz", is_banned=True),
                   User(tg_id=105, full_name="E", lang="en")])
        await s.commit()


async def main() -> None:
    announce.SEND_DELAY = 0
    await init_db()
    await runtime.load()
    check(runtime.notify_enabled() is False, "sukut bo'yicha mijozlarga «yangi mahsulot» xabarlari O'CHIQ (mahsulotlar jimgina qo'shiladi)")
    await runtime.set_value("notify_on", "1")          # quyidagi sinovlar uchun admin xabarnomani yoqqan

    r = await run_sync(items(6))
    check(r.created == 6 and r.events == [], "birinchi yuklashda hech kimga «yangi» xabari bormaydi")

    r = await run_sync(items(6, avail={2: 7}))
    check(r.events == [], "zaxira 2 taga oshdi (< 5) — xabar yo'q")
    r = await run_sync(items(6, avail={2: 12}))
    check(len(r.events) == 1 and r.events[0]["kind"] == "restock" and r.events[0]["added"] == 5
          and r.events[0]["stock"] == 12, "zaxira 5 taga oshdi — «Zaxira to'ldirildi»")
    r = await run_sync(items(6, avail={2: 30}))
    check(r.events == [], "30 daqiqalik cooldown: shu mahsulotga ketma-ket ikkinchi xabar yo'q")

    r = await run_sync(items(6, avail={3: 0}))
    check(r.events == [], "zaxira tugadi — xabar yo'q")
    r = await run_sync(items(6, avail={3: 2}))
    check(len(r.events) == 1 and r.events[0]["added"] == 2, "0 dan qaytganda (2 ta) — har doim xabar")

    api_item = {"productId": "900", "name": "OpenAI API Credits $20", "price": {"amount": 20},
                "availability": {"available": 50}, "productType": "account"}
    r = await run_sync(items(6, avail={3: 2}, extra=[
        {"productId": "50", "name": "CapCut Pro 50 Month 30 Days Warranty", "price": {"amount": 3.5},
         "availability": {"available": 9}, "productType": "account"}, api_item]))
    kinds = [e["kind"] for e in r.events]
    check(kinds == ["new"], "yangi mahsulot — «new» (API/kredit mahsulotlar xabarsiz)")

    await runtime.set_value("notify_on", "0")
    r = await run_sync(items(6, avail={1: 40, 3: 2}, extra=[]))
    check(r.events == [], "admin xabarnomani o'chirsa — hodisa yo'q")
    await runtime.set_value("notify_on", "1")

    r = await run_sync(items(6, avail={4: 40}), auto=False)
    check(r.events == [], "qo'lda /sync mijozlarga xabar yubormaydi")

    # ── Yuborish ──
    await add_users()
    async with SessionMaker() as s:
        pid = (await s.scalar(select(Product).where(Product.external_id == "cb:2"))).id
    from config import settings
    settings.announce_channel_id = ""
    settings.announce_to_users = True          # shaxsiy xabar rejimi (sukut o'chiq) — mijoz filtrlari shu rejimda tekshiriladi
    bot = FakeBot(forbidden={102})
    n = await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 10, "stock": 11}])
    got = {c: (txt, kb) for c, txt, kb in bot.sent}
    check(set(got) == {101, 105} and n == 2, "faqat yoqilgan va bloklanmagan mijozlarga boradi (notify=False, ban, bloklagan — yo'q)")
    txt, kb = got[101]
    check("Qo'shildi: <b>10</b>" in txt and "Hozirgi zaxira: <b>11</b>" in txt and "so'm" in txt
          and "Yangi obuna" not in txt and "/xabar" not in txt and "afolat" not in txt,
          "matn (ta'minotchi botidagidek): nom, qo'shildi, zaxira, bizning narx — kafolat va «xabarni o'chirish» qatori yo'q")
    check("Added" not in got[105][0] and "Qo'shildi" in got[105][0] and "Qo'shildi" in got[102][0] if 102 in got else
          "Qo'shildi" in got[105][0], "hamma mijozga faqat o'zbekcha (ruscha/inglizcha mijozga ham)")
    btn = kb.inline_keyboard[0][0] if kb else None
    check(btn is not None and (btn.web_app is not None or btn.url), "«Sotib olish» tugmasi bor")
    check(btn.model_extra.get("style") == "success", "«Sotib olish» tugmasi yashil (style=success)")

    # ── Brend premium emojisi ──
    from handlers.admin_shop import _lines_with_emoji
    from aiogram.types import Message, Chat, MessageEntity
    import datetime
    text = "CapCut ✂️\nChatGPT 🤖 x\nBoshqa"
    # "✂️" = 2 ta UTF-16 birlik (✂ + VS16), "🤖" = 2 birlik
    ents = [MessageEntity(type="custom_emoji", offset=7, length=2, custom_emoji_id="111"),
            MessageEntity(type="custom_emoji", offset=18, length=2, custom_emoji_id="222")]
    m = Message(message_id=1, date=datetime.datetime.now(), chat=Chat(id=1, type="private"), text=text, entities=ents)
    rows = _lines_with_emoji(m)
    check(len(rows) == 2 and rows[0] == ("CapCut", "111", "✂️") and rows[1][1:] == ("222", "🤖")
          and rows[1][0].startswith("ChatGPT"), "admin xabaridan «brend + premium emoji» qatorlari ajratiladi")
    import json as _json
    await runtime.set_value("brand_emoji", _json.dumps({"CapCut": {"id": "999", "char": "✂️"}}))
    bot = FakeBot()
    await announce.announce_events(bot, [{"id": pid, "kind": "new", "added": 3, "stock": 3}], only_to=[1])
    check('<tg-emoji emoji-id="999">✂️</tg-emoji>' in bot.sent[0][1] and "Yangi obuna" in bot.sent[0][1],
          "xabarda mahsulot brendining premium emojisi chiqadi (yangi mahsulotda «Yangi obuna» sarlavhasi)")
    await runtime.set_value("brand_emoji", None)

    from services import brand_emoji
    check(brand_emoji.emoji_id("CapCut")[0] == "5246889012668426695", "tayyor ro'yxat: CapCut premium emojisi")
    check(brand_emoji.emoji_id("ChatGPT", "API Codex $10")[0] == brand_emoji.CODEX_API
          and brand_emoji.emoji_id("ChatGPT", "ChatGPT Plus")[0] == "5246801734638002426", "ChatGPT (API ham, oddiysi ham): bitta OpenAI logotipi")
    bot = FakeBot()
    await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 5, "stock": 9}], only_to=[1])
    b = bot.sent[0][2].inline_keyboard[0][0]
    check('emoji-id="5246889012668426695"' in bot.sent[0][1], "xabarda brendning tayyor premium emojisi (CapCut)")
    check(b.model_extra.get("icon_custom_emoji_id") == "5312361253610475399" and b.text == "Sotib olish",
          "«Sotib olish» tugmasida brend logosi emas, premium savatcha ikonkasi (matnda oddiy 🛒 yo'q)")
    from services.emoji import premiumize
    pm = premiumize("➕ Qo'shildi 💵 Narxi 🛍 👋 🔥")
    check(all(x in pm for x in ("5393194986252542669", "5413653337117571378", "5235588635885054955", "5472354553527541051"))
          and "<tg-emoji emoji-id=\"5393194986252542669\">➕</tg-emoji>" in pm and pm.endswith("🔥"),
          "tayyor xarita: ➕ 💵 🛍 👋 avtomatik premium, 🔥 oddiy qoladi")

    bot = FakeBot()
    evs = [{"id": pid, "kind": "restock", "added": 5, "stock": 9}] * 4
    n = await announce.announce_events(bot, evs)
    check(n == 3 and len({c for c, *_ in bot.sent}) == 3, "4 ta hodisa — har mijozga bitta umumiy xabar (spam yo'q)")
    check("Servis AI'da yangiliklar" in bot.sent[0][1], "umumiy xabar sarlavhasi")

    bot = FakeBot()
    n = await announce.announce_events(bot, [{"id": pid, "kind": "new", "added": 3, "stock": 3}], only_to=[1])
    check([c for c, *_ in bot.sent] == [1], "sinov xabari faqat adminga")

    from services.emoji import parse_emoji_pairs
    pairs = parse_emoji_pairs("📦 5312361253610475399\n➕ = 5393194986252542669, 💵: [5413653337117571378]\nabc 5393194986252542669")
    check(pairs == {"📦": "5312361253610475399", "➕": "5393194986252542669", "💵": "5413653337117571378"}, "admin: «emoji + ID» matnidan juftliklar ajratiladi")

    from config import settings as _st
    check(7330213371 in _st.admins and not ({6418750920, 5436773404} & set(_st.admins)), "adminlar: faqat sozlamadagi ID lar (eski egasining ID'lari yo'q)")

    # ── Buyurtma xabarida kafolat va murojaat yo'li ──
    from types import SimpleNamespace as NS
    o = NS(id=7, total=5000, items=[NS(product_name="CapCut Pro 7 kun", status="delivered", delivered_content="a@b.c | pass", product_id=11)])
    txt = order_success_text("uz", o, 1000, {}, {11: "24 soat ichida kirishda muammo chiqsa «Yordam»ga yozing"})
    check("🛡" in txt and "24 soat ichida" in txt and "«Yordam» bo'limi" in txt, "chatdagi buyurtma xabarida kafolat matni va murojaat yo'li")
    check("🛡" not in order_success_text("uz", o, 1000, {}, {}), "kafolat yo'q bo'lsa — blok chiqmaydi")
    check(runtime.support_username() == "Servisaiuz", "Yordam markazi: @Servisaiuz (standart)")
    check("@Servisaiuz ga yozing" in order_success_text("uz", o, 1000, {11: "1) a\n2) b"}, {}, "Servisaiuz"),
          "xariddan keyingi xabarda: qo'llanmaga tushunmasangiz @Servisaiuz ga yozing")
    await runtime.set_value("support", "@Yangi_Yordam")
    check(runtime.support_username() == "Yangi_Yordam", "admin yordam markazini o'zgartirsa — darhol kuchga kiradi")
    await runtime.set_value("support", None)
    check(runtime.support_username() == "Servisaiuz", "«-» — standartga qaytadi")

    # ── Sukut: mijozlarga shaxsiy xabar yo'q, hammasi kanalga ──
    settings.announce_to_users = False
    settings.announce_channel_id = "@OBUNALARKANAL"
    check(settings.announce_chat == "@OBUNALARKANAL", "sukut kanal: @OBUNALARKANAL")
    bot = FakeBot()
    n = await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 10, "stock": 11}])
    check([c for c, *_ in bot.sent] == ["@OBUNALARKANAL"] and n == 1, "yangi obuna xabari faqat kanalga ketadi, mijozlarga botdan emas")
    ch_btn = bot.sent[0][2].inline_keyboard[0][0]
    check("Qo'shildi: <b>10</b>" in bot.sent[0][1] and ch_btn.url and ch_btn.web_app is None, "kanal xabari: matn va botga havola (web_app emas)")
    check(ch_btn.model_extra.get("style") == "success" and "Sotib olish" in ch_btn.text, "kanal tugmasi botdagidek yashil «Sotib olish»")
    check("<tg-emoji" in bot.sent[0][1], "kanal xabarida brend premium emojisi (botdagi bilan bir xil matn)")
    bot = FakeBot()
    await announce.announce_events(bot, evs)
    check([c for c, *_ in bot.sent] == ["@OBUNALARKANAL"] and "Servis AI'da yangiliklar" in bot.sent[0][1], "ko'p hodisa — kanalga bitta umumiy xabar")
    bot = FakeBot()
    await announce.announce_events(bot, [{"id": pid, "kind": "new", "added": 3, "stock": 3}], only_to=[1])
    check([c for c, *_ in bot.sent] == [1], "sinov xabari kanalga chiqmaydi, faqat adminga")
    # Premium akkaunt (TG_SESSION) nomidan: premium emoji kanalda albatta ko'rinadi, «Sotib olish» — botdagi obunaga havola
    from services import cardbridge

    class FakeUser:
        def __init__(self, fail=None):
            self.sent, self.edited, self.fail = [], [], fail

        async def send_message(self, chat, body, parse_mode=None, link_preview=None):
            if self.fail:
                raise self.fail
            self.sent.append((chat, body))
            from types import SimpleNamespace as NS2
            return NS2(id=500 + len(self.sent))

        async def edit_message(self, chat, mid, body, parse_mode=None, link_preview=None):
            self.edited.append((chat, mid, body))

    fu = FakeUser()
    cardbridge.CLIENT = fu
    bot = FakeBot()
    n = await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 10, "stock": 11}])
    check(n == 1 and not bot.sent and len(fu.sent) == 1 and fu.sent[0][0] == "@OBUNALARKANAL", "kanalga Premium akkaunt nomidan yuboriladi (bot emas)")
    check('<tg-emoji emoji-id="5393194986252542669">➕</tg-emoji>' in fu.sent[0][1] and '<tg-emoji emoji-id="5413653337117571378">💵</tg-emoji>' in fu.sent[0][1],
          "akkaunt posti: ➕ va 💵 premium emojiga almashtiriladi (botning middleware'idan o'tmasa ham)")
    check("📦" in fu.sent[0][1] and "emoji-id=\"" in fu.sent[0][1], "post matnida premium emoji bor")
    # admin 📦 uchun ID saqlasa — 📦 ham premium bo'ladi
    await runtime.set_value("emoji_map", json.dumps({"📦": "5312361253610475399"}))
    fu_b = FakeUser(); cardbridge.CLIENT = fu_b
    await announce.announce_events(FakeBot(), [{"id": pid, "kind": "restock", "added": 10, "stock": 11}])
    check('<tg-emoji emoji-id="5312361253610475399">📦</tg-emoji>' in fu_b.sent[0][1], "admin saqlagan 📦 ID si kanal postida premium bo'ladi")
    await runtime.set_value("emoji_map", None)
    cardbridge.CLIENT = fu
    check(len(bot.edits) == 1 and bot.edits[0][1] == 501 and bot.edits[0][0] == "@OBUNALARKANAL", "bot shu postga tugma qo'shadi (xabar id si bilan)")
    ebtn = bot.edits[0][2].inline_keyboard[0][0]
    check(ebtn.model_extra.get("style") == "success" and f"start=p{pid}" in ebtn.url and "Sotib olish" in ebtn.text,
          "tugma: yashil «Sotib olish», botdagi shu obunaga olib boradi")
    check(not fu.edited and announce.CHANNEL["mode"] == "user" and not announce.CHANNEL["error"], "tugma qo'yilgach matnli havola kerak emas")
    # botda tahrirlash huquqi yo'q — matnga havola qo'shiladi
    fu3 = FakeUser()
    cardbridge.CLIENT = fu3
    bot = FakeBot()
    bot.edit_fail = PermissionError("not enough rights")
    await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 10, "stock": 11}])
    check(fu3.edited and f"https://t.me/obunalar_bot?start=p{pid}" in fu3.edited[0][2] and "Sotib olish" in fu3.edited[0][2]
          and "Tugma qo'yilmadi" in announce.CHANNEL["error"], "tugma qo'yib bo'lmasa — matnli «Sotib olish» havolasi, sabab saqlanadi")
    fu2 = FakeUser(fail=PermissionError("ChatAdminRequired"))
    cardbridge.CLIENT = fu2
    bot = FakeBot()
    n = await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 10, "stock": 11}])
    check(n == 1 and [c for c, *_ in bot.sent] == ["@OBUNALARKANAL"] and announce.CHANNEL["mode"] == "bot" and "ChatAdminRequired" in announce.CHANNEL["error"],
          "akkaunt kanalda admin bo'lmasa — avtomatik bot orqali yuboriladi, sabab saqlanadi")
    cardbridge.CLIENT = None

    settings.announce_channel_id = ""
    bot = FakeBot()
    check(await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 5, "stock": 9}]) == 0 and not bot.sent, "kanal bo'sh bo'lsa hech kimga yuborilmaydi")
    settings.announce_channel_id = "@OBUNALARKANAL"

    # ── Tavsif yashiriladi, qo'llanma chiqadi ──
    async with SessionMaker() as s:
        p = await s.get(Product, pid)
        check(bool(p.description), "ta'minotchi tavsifi bazada saqlanadi (admin ko'ra oladi)")
        d = api._product(p, {})
        check(d["description"] == "" and "parol" in d["guide"].lower() and "Kafolat" not in d["description"],
              "Mini App'ga ta'minotchining eski tavsifi YUBORILMAYDI; admin qo'llanma yozmagan bo'lsa tayyor qo'llanma chiqadi")
        p.guide = "1) Saytga kiring\n2) Emailni kiriting"
        overrides.lock(p, "description")
        p.description = "Admin yozgan tavsif"
        await s.commit()
        d = api._product(p, {})
        check(d["description"] == "Admin yozgan tavsif" and d["guide"].startswith("1)"),
              "admin yozgan tavsif va qo'llanma Mini App'ga boradi")

    # ── Narx o'zgarishi jurnali va adminga ogohlantirish ──
    from database.models import PriceChange, ProductImage
    r = await run_sync([{**items(6)[0], "price": {"amount": 5.0}}] + items(6)[1:], auto=True)
    check(len(r.price_changes) == 1 and r.price_changes[0]["new"] > r.price_changes[0]["old"], "ta'minotchi narxi o'zgarsa — jurnalga yoziladi")
    async with SessionMaker() as s:
        rows = list(await s.scalars(select(PriceChange)))
        check(len(rows) == 1 and rows[0].source == "sync" and rows[0].new_price > rows[0].old_price, "PriceChange qatori: eski → yangi narx")
    bot = FakeBot()
    await announce.alert_price_changes(bot, r.price_changes)
    check(bot.sent and bot.sent[0][0] == 1 and "→" in bot.sent[0][1] and "🔺" in bot.sent[0][1], "admin narx o'zgargan obuna haqida xabar oladi (mijoz emas)")
    await runtime.set_value("price_alert", "0")
    bot = FakeBot()
    await announce.alert_price_changes(bot, r.price_changes)
    check(not bot.sent, "ogohlantirish o'chirilsa — xabar yo'q")
    await runtime.set_value("price_alert", None)
    r = await run_sync([{**items(6)[0], "price": {"amount": 5.0}}] + items(6)[1:], auto=True)
    check(r.price_changes == [], "narx o'zgarmasa — jurnal toza")

    # ── Admin yuklagan rasm: bazada, /media/p/ orqali, xabarnomaga qo'shiladi ──
    from handlers.admin_shop import _save_image
    from aiohttp.test_utils import TestClient, TestServer
    from aiohttp import web as _web
    from webapp.server import setup_webapp
    async with SessionMaker() as s:
        p = await s.get(Product, pid)
        await _save_image(s, p, b"\xff\xd8\xff\xe0FAKEJPEG", "image/jpeg", "AgACfileid")
        await s.commit()
        check(p.image_url.startswith("/media/p/") and "image" in overrides.locked(p), "rasm saqlandi, mahsulotga bog'landi va sinxronlashdan himoyalandi")
        check(api._product(p, {})["image_url"] == p.image_url, "Mini App ma'lumotida image_url bor")
    app = _web.Application()
    setup_webapp(app, FakeBot())
    async with TestClient(TestServer(app)) as cl:
        resp = await cl.get(f"/media/p/{pid}")
        body = await resp.read()
        check(resp.status == 200 and body.endswith(b"FAKEJPEG") and resp.headers["Content-Type"] == "image/jpeg", "/media/p/ID rasmni qaytaradi")
        check((await cl.get("/media/p/99999")).status == 404, "rasmi yo'q mahsulot — 404")
    bot = FakeBot()
    await announce.announce_events(bot, [{"id": pid, "kind": "restock", "added": 5, "stock": 9}], only_to=[1])
    check(bot.photos == [(1, "AgACfileid")] and "Qo'shildi" in bot.sent[-1][1], "xabarnoma rasm bilan (caption) yuboriladi")
    r = await run_sync(items(6), auto=True)
    async with SessionMaker() as s:
        check((await s.get(Product, pid)).image_url.startswith("/media/p/"), "katalog yangilanishi admin rasmini o'chirmaydi")
        await s.delete(await s.get(ProductImage, pid))
        await s.commit()

    # ── Kafolat matni (buyurtma tanlanganda) va video qo'llanma ──
    from services.guides import warranty_note, default_guide
    async with SessionMaker() as s:
        p = await s.get(Product, pid)
        p.warranty_note = None
        p.supplier_data = '{"type": "account", "warranty": "12 soat kafolat"}'
        check(warranty_note(p) == "12 soat ichida login va parollarni almashtirib olasiz, hech qanday muammo bo'lmaydi.",
              "kafolat matni ta'minotchi muddatidan: «12 soat ichida login va parollarni almashtirib olasiz…»")
        p.supplier_data = '{"type": "account", "warranty": "kafolatsiz"}'
        check(warranty_note(p) == "", "kafolatsiz mahsulotda kafolat matni chiqmaydi")
        p.supplier_data = '{"type": "account", "warranty": "30 kun kafolat"}'
        check("Kafolat" not in default_guide(p), "tayyor qo'llanmada kafolat qatori yo'q (u buyurtmada ko'rsatiladi)")
        p.warranty_note = "Admin yozgan kafolat"
        p.guide_video = "tg:FILEID"
        await s.commit()
        d = api._product(p, {})
        check("warranty" not in d["description"].lower() and d["video"] is True, "mahsulot ma'lumotida video belgisi bor")
        ex = await api._extras(s, [type("O", (), {"items": [type("I", (), {"product_id": pid})()]})()])
        check(ex[pid]["note"] == "Admin yozgan kafolat" and ex[pid]["video"], "buyurtma uchun admin yozgan kafolat matni ustun")
        o = api._order(type("O", (), {"id": 1, "total": 5, "status": type("S", (), {"value": "delivered"})(), "created_at": None,
                                      "items": [type("I", (), {"product_name": "x", "qty": 1, "price": 5, "product_id": pid,
                                                              "delivered_content": "l:p", "status": "ok"})()]})(), ex)
        check(o["items"][0]["warranty"] == "Admin yozgan kafolat" and o["items"][0]["video"], "buyurtma elementida kafolat va video bor")
    bot = FakeBot()
    bot.send_video = lambda chat_id, vid, caption=None: _vid(bot, chat_id, vid, caption)
    check(await api._deliver_video(bot, 7, "tg:FILEID", "CapCut") is True and bot.sent[-1][0] == 7, "yuklangan video chatga yuboriladi")
    check(await api._deliver_video(bot, 7, "https://youtu.be/x", "CapCut") is False, "havola botga video sifatida yuborilmaydi (Mini App ochadi)")
    async with SessionMaker() as s:
        p = await s.get(Product, pid)
        p.warranty_note = None; p.guide_video = None
        await s.commit()

    # ── Qo'llanma buyurtma xabarida ──
    class It:
        product_id, product_name, status, delivered_content = pid, "CapCut", "ok", "login:pass"

    class Order:
        id, total, items = 7, 1000, [It()]

    text = order_success_text("uz", Order(), 5000, {pid: "1) Saytga kiring <b>\n2) Emailni kiriting"})
    check("Qanday foydalaniladi" in text and "1) Saytga kiring &lt;b&gt;" in text and "2) Emailni kiriting" in text and "login:pass" in text,
          "xarid xabarida qo'llanma (HTML xavfsiz) kodlar bilan birga")
    check("Qanday foydalaniladi" not in order_success_text("uz", Order(), 5000), "qo'llanma yo'q bo'lsa — qo'shilmaydi")
    check(api._order.__defaults__ is not None, "_order guides parametri ixtiyoriy")

    print("\nHammasi joyida ✅")


asyncio.run(main())
