"""Yangi mahsulot qo'shilganda avtomatik e'lon yuborish."""
from __future__ import annotations

import asyncio
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.db import SessionMaker
from database.models import Product, ProductImage, User
from keyboards.user_kb import buy_kb, channel_kb
from locales.texts import money, t
from services import brand_emoji, repo, runtime
from services.emoji import e, premiumize

log = logging.getLogger(__name__)


async def announce_product(
    bot: Bot, session: AsyncSession, product: Product, force: bool = False
) -> int:
    """Kanalga va/yoki barcha foydalanuvchilarga e'lon yuboradi.

    Bir mahsulot ikki marta e'lon qilinmaydi (product.announced bayrog'i),
    `force=True` bo'lsa qayta yuboriladi.
    """
    if product.announced and not force:
        return 0

    stock = await repo.stock_count(session, product)
    if stock <= 0 and not product.unlimited:
        return 0

    me = await bot.get_me()
    text = t(
        "uz", "announce_new",
        emoji=product_emoji(product),
        name=product.name,
        description=product.description or "—",
        price=money(product.price),
        stock="♾ Cheksiz" if product.unlimited else str(stock),
    )
    kb = channel_kb(me.username, product.id)

    sent = 0
    # 1) Kanal
    if settings.announce_chat:
        sent += int(await post_to_channel(bot, text, me.username, product.id))

    # 2) Foydalanuvchilar (faqat ANNOUNCE_TO_USERS=true bo'lsa)
    for uid in (await repo.all_user_ids(session) if settings.announce_to_users else []):
        try:
            await bot.send_message(uid, text, reply_markup=kb)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    product.announced = True
    await session.commit()
    return sent


# ─────────────────── Yangi obuna / zaxira xabarnomalari ───────────────────

DIGEST_FROM = 4          # bir sinxronlashda shuncha va undan ko'p hodisa bo'lsa — bitta umumiy xabar
DIGEST_LINES = 12
SEND_DELAY = 0.04        # ~25 xabar/soniya (Telegram chegarasidan past)


LANG = "uz"              # xabarnomalar faqat o'zbekcha

# Oxirgi kanal posti natijasi (admin: /kanal)
CHANNEL = {"mode": "", "error": "", "at": ""}


def _stamp(mode: str, error: str = "") -> None:
    from datetime import datetime
    CHANNEL.update(mode=mode, error=error, at=datetime.utcnow().strftime("%d.%m %H:%M UTC"))


async def post_to_channel(bot: Bot, text: str, bot_username: str, product_id: int | None = None,
                          photo: str | None = None) -> bool:
    """Kanalga post. Avval bot egasining Premium akkaunti (TG_SESSION) nomidan — premium emojilar kanalda ALBATTA ko'rinadi,
    «Sotib olish» havolasi botdagi shu obunaga olib boradi. Akkaunt kanalda admin bo'lmasa yoki ulanmagan bo'lsa —
    bot orqali (yashil «Sotib olish» tugmasi bilan) yuboriladi."""
    chat = settings.announce_chat
    if not chat:
        return False
    err = ""
    if settings.announce_via_user:
        from services import cardbridge
        client = cardbridge.CLIENT
        if client is not None:
            try:
                link = f"https://t.me/{bot_username}?start=p{product_id or ''}"
                text = premiumize(text) or text         # akkaunt yo'li botning chiquvchi middleware'idan o'tmaydi — ➕ 💵 📦 shu yerda almashtiriladi
                if photo:
                    import io
                    buf = io.BytesIO()
                    await bot.download(photo, destination=buf)
                    buf.name = "photo.jpg"
                    buf.seek(0)
                    msg = await client.send_file(chat, buf, caption=text.rstrip(), parse_mode="html")
                else:
                    msg = await client.send_message(chat, text.rstrip(), parse_mode="html", link_preview=False)
                mode = "user"
                # Akkaunt postiga tugma qo'ya olmaydi — botning o'zi (kanalda admin) postga yashil «Sotib olish» tugmasini qo'shadi
                try:
                    await bot.edit_message_reply_markup(chat_id=chat, message_id=msg.id, reply_markup=channel_kb(bot_username, product_id))
                except Exception as ex:  # noqa: BLE001 — botda «boshqalar xabarini tahrirlash» huquqi yo'q: matnli havola qo'shamiz
                    mode, err = "user", f"Tugma qo'yilmadi: {type(ex).__name__}: {ex}"[:200]
                    body = text.rstrip() + f'\n\n{e("🛒", runtime.CART_EMOJI)} <a href="{link}"><b>Sotib olish</b></a>'
                    try:
                        await client.edit_message(chat, msg.id, body, parse_mode="html", link_preview=False)
                    except Exception:  # noqa: BLE001
                        log.warning("Postga havola qo'shib bo'lmadi", exc_info=True)
                _stamp(mode, err)
                return True
            except Exception as ex:  # noqa: BLE001 — admin emas / yopiq kanal va h.k.: bot orqali yuboramiz
                log.warning("Kanalga akkaunt nomidan yuborib bo'lmadi (%s: %s) — bot orqali yuboriladi", type(ex).__name__, ex)
                err = f"{type(ex).__name__}: {ex}"[:200]
        else:
            err = "TG_SESSION ulanmagan"
    ok = await _send(bot, chat, text, channel_kb(bot_username, product_id), photo)
    _stamp("bot" if ok else "xato", err)
    return ok


def product_emoji(p: Product) -> str:
    """Mahsulot belgisi: brend uchun admin saqlagan premium emoji, bo'lmasa mahsulotniki."""
    from services import canboso
    cid, char = brand_emoji.emoji_id(p.brand, canboso.plain_name(p))
    if cid:
        return e(char or p.emoji, cid)
    return e(p.emoji, p.custom_emoji_id)


def event_text(lang: str, ev: dict, p: Product) -> str:
    """Bitta mahsulot xabari (ta'minotchi botidagidek): belgi + nom, qo'shildi, hozirgi zaxira, narx (BIZNING narx)."""
    lines = [t(lang, "ev_new"), ""] if ev["kind"] == "new" else []
    lines += [
        f"{product_emoji(p)} <b>{html.escape(p.name)}</b>", "",
        t(lang, "ev_added", n=ev["added"]),
        t(lang, "ev_stock", n=ev["stock"]),
        t(lang, "ev_price", price=money(p.price)),
    ]
    return "\n".join(lines)


def digest_text(lang: str, rows: list[tuple[dict, Product]]) -> str:
    lines = [t(lang, "ev_digest"), ""]
    for ev, p in rows[:DIGEST_LINES]:
        lines.append(f"{product_emoji(p)} <b>{html.escape(p.name)}</b> — {money(p.price)}"
                     f" · {t(lang, 'ev_added', n=ev['added'])}")
    if len(rows) > DIGEST_LINES:
        lines.append(f"… +{len(rows) - DIGEST_LINES}")
    return "\n".join(lines)


async def _send(bot: Bot, uid: int, text: str, kb, photo: str | None = None) -> bool:
    for _ in range(2):
        try:
            if photo:
                try:
                    await bot.send_photo(uid, photo, caption=text, reply_markup=kb)
                    return True
                except TelegramForbiddenError:
                    return False
                except TelegramRetryAfter:
                    raise
                except Exception:  # noqa: BLE001 — rasm yaroqsiz bo'lsa oddiy matn bilan yuboramiz
                    pass
            await bot.send_message(uid, text, reply_markup=kb)
            return True
        except TelegramRetryAfter as ex:
            await asyncio.sleep(ex.retry_after + 1)
        except TelegramForbiddenError:
            return False            # foydalanuvchi botni bloklagan
        except Exception as ex:  # noqa: BLE001
            log.info("Xabarnoma yuborilmadi (%s): %s", uid, ex)
            return False
    return False


async def announce_events(bot: Bot, events: list[dict], only_to: list[int] | None = None) -> int:
    """Yangi mahsulot / zaxira hodisalarini mijozlarga yuboradi. Yuborilganlar soni qaytadi.

    4 tadan ko'p hodisa bitta umumiy xabarga jamlanadi. `only_to` — sinov uchun (faqat adminga).
    """
    if not events:
        return 0
    try:
        async with SessionMaker() as s:
            rows: list[tuple[dict, Product]] = []
            photos: dict[int, str] = {}      # admin yuklagan rasmi bor mahsulotlar: product_id -> Telegram file_id
            for ev in events:
                p = await s.get(Product, ev["id"])
                if p and p.is_active:
                    rows.append((ev, p))
                    img = await s.get(ProductImage, p.id)
                    if img and img.tg_file_id:
                        photos[p.id] = img.tg_file_id
            if not rows:
                return 0
            if only_to is not None:
                users = [(uid, "uz") for uid in only_to]
            elif settings.announce_to_users:
                users = [(u.tg_id, LANG) for u in await s.scalars(
                    select(User).where(User.is_banned.is_(False), User.notify.is_(True)))]
            else:
                users = []          # mijozlarga botdan shaxsiy xabar yuborilmaydi — hammasi kanalga
            me = await bot.get_me()
            digest = len(rows) >= DIGEST_FROM

            def build(lang: str):
                if digest:
                    return digest_text(lang, rows), buy_kb(lang, None, me.username)
                ev, p = rows[0]
                return event_text(lang, ev, p), buy_kb(lang, p.id, me.username)

            sent = 0
            for uid, lang in users:
                if digest:
                    text, kb = build(lang)
                    sent += await _send(bot, uid, text, kb)
                else:
                    for ev, p in rows:
                        sent += await _send(bot, uid, event_text(lang, ev, p), buy_kb(lang, p.id, me.username), photos.get(p.id))
                        await asyncio.sleep(SEND_DELAY)
                await asyncio.sleep(SEND_DELAY)

            if settings.announce_chat and only_to is None:
                if digest:
                    ok = await post_to_channel(bot, build("uz")[0].rstrip(), me.username)
                    sent += int(ok)
                else:
                    ok = True
                    for ev, p in rows:
                        one = await post_to_channel(bot, event_text("uz", ev, p), me.username, p.id, photos.get(p.id))
                        ok, sent = ok and one, sent + int(one)
                        await asyncio.sleep(SEND_DELAY)
                if not ok:
                    log.warning("Kanalga (%s) xabar yuborilmadi — bot kanalda admin ekanini tekshiring", settings.announce_chat)
            log.info("Xabarnoma: %d hodisa, %d ta xabar yuborildi", len(rows), sent)
            return sent
    except Exception:  # noqa: BLE001 — fon vazifasi: xato sinxronlashni buzmasin
        log.exception("Xabarnoma yuborishda xato")
        return 0


# ─────────────────── Adminga: narxi o'zgargan obunalar ───────────────────

ALERT_LINES = 10
ALERT_MASS = 30          # shuncha va undan ko'p narx birdan o'zgarsa (kurs yangilandi) — qisqa xabar


def price_line(name: str, old: int, new: int) -> str:
    pct = (new - old) / old * 100 if old else 0
    arrow = "🔺" if new > old else "🔻"
    return f"{arrow} <b>{html.escape(name)}</b>: {money(old)} → <b>{money(new)}</b> ({pct:+.0f}%)"


async def alert_price_changes(bot: Bot, changes: list[dict]) -> None:
    """Katalog yangilanganda narxi o'zgargan obunalar haqida adminlarga xabar (mijozlarga emas)."""
    if not changes or not runtime.price_alert_enabled():
        return
    if len(changes) >= ALERT_MASS:
        text = (f"📈 <b>{len(changes)} ta obuna narxi o'zgardi</b>\n"
                "Odatda bu USD kursi yoki ta'minotchi narxi yangilanganda bo'ladi.")
    else:
        lines = [price_line(c["name"], c["old"], c["new"]) for c in changes[:ALERT_LINES]]
        if len(changes) > ALERT_LINES:
            lines.append(f"… +{len(changes) - ALERT_LINES}")
        text = f"📈 <b>Narxi o'zgargan obunalar ({len(changes)})</b>\n\n" + "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📈 Hammasini ko'rish", callback_data="a:pchg:24:0")]])
    for admin_id in settings.admins:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception:  # noqa: BLE001 — admin botni bloklagan bo'lishi mumkin
            pass
