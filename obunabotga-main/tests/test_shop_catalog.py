"""API (ta'minotchi) dan kelgan mahsulotlar do'konda ko'rinishini boshidan oxirigacha tekshiradi:
ta'minotchi formatidagi ro'yxat -> sinxronlash -> baza -> «Obunalar» tugmalari (10 ta brend) -> admin paneldagi «Katalog» holati.

Ishga tushirish:  python tests/test_shop_catalog.py   (internet va kalit shart emas)
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
    CANBOSO_API_KEY="test-key",
    USD_TO_UZS="12500",
)

from config import settings  # noqa: E402
from database.db import SessionMaker, init_db  # noqa: E402
from handlers.shop import availability, brand_products, services_kb, shop_brands  # noqa: E402
from services import canboso, catalog_sync, panel  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("✅ " if cond else "❌ ") + label)
    if not cond:
        raise SystemExit(1)


def raw(pid: int, name: str, usd: float, available: int) -> dict:
    """Ta'minotchi (canboso) API javobidagi bitta mahsulot."""
    return {"productId": str(pid), "name": name, "price": {"amount": usd, "currency": "USD"},
            "availability": {"available": available}, "productType": "account", "purchaseRequirements": {}}


NAMES = {
    "ChatGPT": "ChatGPT Plus 1 Month 30 Days Warranty", "Claude": "Claude Pro 1 Month 30 Days Warranty", "ElevenLabs": "ElevenLabs Creator 1 Month 30 Days Warranty",
    "CapCut": "CapCut Pro 1 Month 30 Days Warranty", "Runway": "Runway Standard 1 Month 30 Days Warranty", "Cursor": "Cursor Pro 1 Month 30 Days Warranty",
    "Seedance": "Seedance Pro 1 Month 30 Days Warranty", "Notion": "Notion Plus 1 Month 30 Days Warranty", "Gemini": "Gemini Pro 1 Month 30 Days Warranty",
    "Kling": "Kling Standard 1 Month 30 Days Warranty",
}
SERVICES = list(NAMES)          # testdagi 10 ta brend (menyudagi 32 tadan)


def shop_catalog_menu() -> list[str]:
    from services import curation
    return curation.BASE_BRANDS


async def svc(s, brand: str) -> str:
    """Brend tugmasining callback'i: menyudagi (mahsuloti bor brendlar) tartib bo'yicha."""
    return f"svc:{(await shop_brands(s)).index(brand)}"


async def main() -> None:
    await init_db()

    # 1) har bir obuna nomi to'g'ri brendga tushadi va hech biri bloklanmaydi (Gemini ham)
    for brand, name in NAMES.items():
        it = canboso.parse_item(raw(1, name, 5, 3))
        check(it["brand"] == brand and not it["blocked"], f"«{name}» → {brand}, do'konga qo'shiladi")

    # 2) sinxronlash: 10 ta obuna (bittasi zaxirasiz) + do'konga kerak bo'lmagan mahsulot
    items = [raw(i, NAMES[b], 4 + i, 0 if b == "Kling" else 5) for i, b in enumerate(SERVICES, 1)]
    items.append(raw(99, "Instagram followers 1000", 5, 9))
    async with SessionMaker() as s:
        res = await canboso.sync(s, items=items)
    check(res.created == 10 and res.skipped == 1, f"sinxronlash: 10 ta obuna qo'shildi, keraksizi tashlandi ({res.created}/{res.skipped})")

    async with SessionMaker() as s:
        avail = await availability(s)
        check(all(avail[b] for b in SERVICES if b != "Kling") and avail["Kling"] is False,
              "«Obunalar»: zaxirasi bor 9 tasi mavjud, zaxirasiz Kling — tugagan")
        kb = services_kb(avail)
        styles = {b.text: getattr(b, "style", None) for r in kb.inline_keyboard for b in r}
        check(styles["Gemini"] == "success" and styles["ChatGPT"] == "success" and styles["Kling"] == "danger",
              "tugmalar: mavjudlari yashil, tugagani qizil (Gemini yashil)")
        plans = await brand_products(s, "ChatGPT")
        check(len(plans) == 1 and plans[0].price > 0 and plans[0].stock_qty == 5, "brend ichida tarif narxi (so'mda) va zaxirasi bilan chiqadi")

    # 3) admin paneldagi «Katalog» holati
    catalog_sync.STATUS.update(last_try=None, last_ok=None, last_error="", seen=0)

    async def fake_fetch():
        return items
    orig = canboso.fetch_products, canboso.fetch_balance
    canboso.fetch_products = fake_fetch

    async def no_balance():
        return None
    canboso.fetch_balance = no_balance
    try:
        async with SessionMaker() as s:
            await catalog_sync.sync_catalog(s, auto=True)
            block = await panel.catalog_block(s)
    finally:
        canboso.fetch_products, canboso.fetch_balance = orig
    check(f"9/{len(shop_catalog_menu())}" in block and "Oxirgi yangilanish" in block and "Kling" in block, "admin paneli: «Katalog: 9/32 mavjud», oxirgi yangilanish va yo'q obuna ko'rinadi")

    async def broken():
        raise canboso.SupplierError("Ta'minotchi katalogni bermadi (401): Invalid API key")
    canboso.fetch_products = broken
    try:
        async with SessionMaker() as s:
            try:
                await catalog_sync.sync_catalog(s, auto=True)
            except catalog_sync.CatalogError:
                pass
            block = await panel.catalog_block(s)
    finally:
        canboso.fetch_products = orig[0]
    check("Invalid API key" in block, "kalit noto'g'ri bo'lsa — admin panelida aniq xato ko'rinadi")

    key = settings.canboso_api_key
    settings.canboso_api_key = ""
    try:
        async with SessionMaker() as s:
            block = await panel.catalog_block(s)
    finally:
        settings.canboso_api_key = key
    check("CANBOSO_API_KEY kiritilmagan" in block, "kalit kiritilmagan bo'lsa — admin panelida shu yoziladi")

    # 4) brend ichida mahsulotlar: hammasi tugagan bo'lsa ham ro'yxat chiqadi; mahsulot umuman yo'q bo'lsa — aniq xabar
    import handlers.shop as shop

    class Msg:
        def __init__(self):
            self.edits = []

        async def edit_text(self, text, reply_markup=None):
            self.edits.append((text, reply_markup))

    class Call:
        def __init__(self, data):
            self.data, self.message, self.answers = data, Msg(), []

        async def answer(self, text=None, show_alert=False):
            self.answers.append((text, show_alert))

    from types import SimpleNamespace as NS
    async with SessionMaker() as s:
        cl = Call(await svc(s, "Kling"))
        await shop.cb_brand(cl, s, "uz")
        text, kb = cl.message.edits[0]
        labels = [b.text for r in kb.inline_keyboard for b in r]
        styles = [getattr(b, "style", None) for r in kb.inline_keyboard for b in r]
        check("Kling" in text and "hammasi tugagan" in text and any("oy" in l and "so'm" in l for l in labels) and "danger" in styles,
              "Kling (hammasi tugagan): ro'yxat chiqadi, qizil tugma va «hammasi tugagan» yozuvi bor")
        async with SessionMaker() as s2:
            from database.models import Product
            from sqlalchemy import delete
            await s2.execute(delete(Product).where(Product.brand == "Gemini"))
            await s2.commit()
        check("Gemini" not in await shop.shop_brands(s), "mahsuloti umuman qolmagan brend menyudan yo'qoladi (qizil bo'lib turmaydi)")
        cr = Call("svc:99")
        await shop.cb_brand(cr, s, "uz")
        check(cr.answers and "yo'q" in (cr.answers[0][0] or "") and cr.answers[0][1] is True and not cr.message.edits,
              "eskirgan brend tugmasi: aniq «bo'limda obuna yo'q» xabari")

    # 4b) tugagan tarifni bosish — faqat «tugagan» xabari, sotib olib bo'lmaydi; admin yashirgan va ta'minotchidan chiqqan ko'rinmaydi
    from database.models import Product
    from services import overrides
    from sqlalchemy import select
    async with SessionMaker() as s:
        kl = (await brand_products(s, "Kling"))[0]
        cp = Call(f"plan:{kl.id}")
        await shop.cb_plan(cp, s, NS(balance=0, tg_id=1), "uz")
        check(cp.answers and cp.answers[0][1] is True and "tugagan" in cp.answers[0][0] and not cp.message.edits,
              "tugagan tarifni bosish: faqat «tugagan» xabari (sotib olishga o'tmaydi)")
        cb = Call(f"buy:{kl.id}")
        await shop.cb_buy(cb, s, NS(balance=10**9, tg_id=1), "uz", NS(clear=None))
        check(cb.answers and "tugagan" in cb.answers[0][0], "tugagan tarifni sotib olib bo'lmaydi")
        # admin yashirgan (stock>0 bo'lsa ham) — ro'yxatda yo'q va sotib olinmaydi
        ch = (await brand_products(s, "ChatGPT"))[0]
        ch.is_active = False
        overrides.lock(ch, "hidden")
        await s.commit()
        check(await brand_products(s, "ChatGPT") == [] and not shop.in_stock(ch), "admin yashirgan mahsulot ro'yxatda ko'rinmaydi va sotib olib bo'lmaydi")
    # ta'minotchi ro'yxatidan chiqib ketgan mahsulot (Kling endi yo'q) — ko'rinmaydi
    only_cursor = [raw(5, NAMES["Cursor"], 9, 5)]
    async with SessionMaker() as s:
        await canboso.sync(s, items=only_cursor)
        await canboso.sync(s, items=only_cursor)
        await canboso.sync(s, items=only_cursor)
        left = await brand_products(s, "Kling")
        pk = (await s.scalars(select(Product).where(Product.brand == "Kling"))).first()
        check(left == [] and pk.stock_qty is None, "ta'minotchidan chiqib ketgan mahsulot do'konda ko'rinmaydi (zaxirasi «noma'lum»)")

    # 6) Admin kurs yozsa — katalog shu zahoti yuklanadi (kutib o'tirish shart emas)
    from handlers import admin_ext
    from services import runtime
    from database.models import Product
    from sqlalchemy import delete
    async with SessionMaker() as s:
        await s.execute(delete(Product))
        await s.commit()
    canboso._rate_cache = (0.0, 0.0)
    orig_usd, settings.usd_to_uzs = settings.usd_to_uzs, 0.0          # test muhitidagi qo'lda kursni vaqtincha o'chiramiz
    orig_rates, orig_fetch = canboso.RATE_SOURCES, canboso.fetch_products

    async def dead(_http):
        raise ConnectionError("cbu.uz ochilmadi")
    canboso.RATE_SOURCES = [("CBU", dead)]
    await runtime.set_value("usd_rate", None)
    await runtime.set_value("usd_last", None)

    async def feed():
        return [raw(i, NAMES[b], 4 + i, 5) for i, b in enumerate(SERVICES, 1)]
    canboso.fetch_products = feed
    async with SessionMaker() as s:
        try:
            await catalog_sync.sync_catalog(s)
            blocked = False
        except catalog_sync.CatalogError as ex:
            blocked = "USD kursi" in str(ex)
    check(blocked, "kurs olinmasa katalog yuklanmaydi va xabar «USD kursi» ga yo'naltiradi (skrinshotdagi holat)")

    class Reply:
        def __init__(self):
            self.text, self.answers = "12 100", []

        async def answer(self, text, reply_markup=None):
            self.answers.append(text)

    class St:
        async def clear(self):
            pass
    msg = Reply()
    async with SessionMaker() as s:
        await admin_ext.rate_save(msg, NS(tg_id=1), St(), s)
        avail = await availability(s)
    canboso.RATE_SOURCES, canboso.fetch_products, settings.usd_to_uzs = orig_rates, orig_fetch, orig_usd
    check(msg.answers and "Katalog yuklandi" in msg.answers[0] and "+10" in msg.answers[0], "admin kurs yozdi → «Katalog yuklandi: +10 yangi»")
    check(all(avail[b] for b in SERVICES), "10 ta obunaning hammasi do'konda ko'rinadi (yashil)")

    # 7) har bir tarif tugmasi oldida brendning o'z premium logotipi; karta o'zbekcha va tushunarli
    from services import emoji as _emoji
    from services import overrides
    feed2 = [raw(11, "ChatGPT Go 1 Month 30 Days Warranty", 3.9, 5), raw(12, "API Codex Astra $100 1 Month 30 Days Warranty", 86, 5),
             raw(13, "ChatGPT Plus VIP 1 Month 20 Days Warranty", 11, 0), raw(14, "Claude Pro 1 Month Own Email 30 Days Warranty", 17, 5),
             raw(15, "Kling Standard 1 Month 660 Credits Full Warranty", 7, 5)]

    async def feed_two():
        return feed2
    canboso.fetch_products = feed_two
    async with SessionMaker() as s:
        await catalog_sync.sync_catalog(s)
        c1 = Call(await svc(s, "ChatGPT"))
        await shop.cb_brand(c1, s, "uz")
        btns = [b for r in c1.message.edits[0][1].inline_keyboard for b in r if (b.callback_data or "").startswith("plan:")]
        icons = [getattr(b, "icon_custom_emoji_id", None) for b in btns]
        styles = [getattr(b, "style", None) for b in btns]
        check(len(btns) == 2 and all(icons) and "danger" in styles and "success" in styles,
              "ChatGPT tariflari: HAR BIR tugma (yashil ham, qizil ham) oldida premium logotip bor")
        cx = Call(await svc(s, "Codex"))
        await shop.cb_brand(cx, s, "uz")
        codex = [b for r in cx.message.edits[0][1].inline_keyboard for b in r if (b.callback_data or "").startswith("plan:")][0]
        check(codex.icon_custom_emoji_id == "5246801734638002426", "Codex (alohida brend) tugmasida OpenAI/Codex logotipi")
        ck = Call(await svc(s, "Claude"))
        await shop.cb_brand(ck, s, "uz")
        cl_btn = [b for r in ck.message.edits[0][1].inline_keyboard for b in r if (b.callback_data or "").startswith("plan:")][0]
        check(cl_btn.icon_custom_emoji_id == "5417984549642601364", "Claude tarifida Claude logotipi (har brendniki o'zining)")

        user = NS(balance=250_000, tg_id=1)
        p_claude = (await shop.brand_products(s, "Claude"))[0]
        txt, _ = shop._plan_view(p_claude, user, "uz")
        check("Nima olasiz" in txt and "emailingizga" in txt and "Muddati:</b> 1 oy" in txt and "Narxi" in txt and "Hisobingiz" in txt
              and '<tg-emoji emoji-id="5417984549642601364">' in txt, "Claude kartasi: nima olasiz, muddat, narx, hisob; sarlavhada Claude logotipi")
        p_kling = (await shop.brand_products(s, "Kling"))[0]
        txt, _ = shop._plan_view(p_kling, user, "uz")
        check("660 kredit" in txt and "xizmat ichidagi hisob" in txt and "Kafolat:</b> to'liq" in txt, "Kling kartasi: kredit nima ekani va to'liq kafolat tushuntirilgan")
        p_codex = (await shop.brand_products(s, "Codex"))[0]
        txt, _ = shop._plan_view(p_codex, user, "uz")
        check("30 kun" in txt and "faollashtirish kodi" in txt and "vibi.top" in txt and "login va parol" not in txt,
              "Codex kartasi: faollashtirish kodi (vibi.top) beriladi, «30 kun» kafolat yozilgan")
        # admin tavsifni qo'lda yozgan bo'lsa — o'sha ko'rsatiladi
        overrides.lock(p_claude, "description")
        p_claude.description = "Admin yozgan tavsif"
        txt, _ = shop._plan_view(p_claude, user, "uz")
        check("Admin yozgan tavsif" in txt, "admin yozgan tavsif kartani almashtiradi")
        # premium ishlamasa — logotip tugmalardan tushadi, oddiy emoji qoladi
        _emoji.mark_blocked()
        c2 = Call(await svc(s, "ChatGPT"))
        await shop.cb_brand(c2, s, "uz")
        b2 = [b for r in c2.message.edits[0][1].inline_keyboard for b in r if (b.callback_data or "").startswith("plan:")]
        check(not any(getattr(b, "icon_custom_emoji_id", None) for b in b2) and "<tg-emoji" not in shop._plan_view(p_kling, user, "uz")[0],
              "premium rad etilsa — ikonka va teglar tushadi, oddiy ko'rinish qoladi")
        _emoji._blocked_until = 0.0

    # 5) o'zbekcha nomlar mijozga tushunarli
    for raw_name, must in [("ChatGPT Pro 1 Month Own Email", "o'z emailingizga"), ("Perplexity Pro 1 Year Redeem Code", "Redeem-kod"),
                           ("ChatGPT Plus 1 Month Private Account", "shaxsiy akkaunt"), ("Runway Pro 625 Credits Upgrade", "kredit")]:
        uz = canboso.uz_name(raw_name)[0]
        check(must in uz and "Own" not in uz and "Credits" not in uz and "Email Yangilash" not in uz, f"«{raw_name}» → «{uz}»")
    print("\n✅ Katalog → do'kon testlari o'tdi")


asyncio.run(main())
