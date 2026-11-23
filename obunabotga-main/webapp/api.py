"""Mini App uchun JSON API.

Har bir so'rov `Authorization: tma <initData>` sarlavhasi bilan keladi.
Middleware: imzoni tekshiradi → foydalanuvchini topadi → ban va majburiy
obunani tekshiradi → handlerga `request["user"]` va `request["session"]` beradi.
"""
from __future__ import annotations

import logging

from datetime import timedelta

from aiohttp import web
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from config import settings
from database.db import SessionMaker
from database.models import DeliveryType, Product
from services import canboso, fulfillment, overrides, paynotify, repo, runtime
from services import topup as topup_core
from services.guides import guide_of, has_video, warranty_hours, warranty_note, warranty_public
from services.notify import notify_admins_order, notify_admins_payment, order_success_text
from services.payments import MIN_TOPUP, PROVIDERS
from services.subscription import missing_channels
from webapp.auth import AuthError, validate_init_data

log = logging.getLogger("uzshop.api")

MAX_TOPUP = 50_000_000
MAX_LINES = 20
MAX_QTY = 50


def _err(status: int, code: str, message: str, **extra) -> web.Response:
    return web.json_response({"error": code, "message": message, **extra}, status=status)


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None  # bazada UTC saqlanadi


# ─────────────────────────── Middleware ───────────────────────────

@web.middleware
async def api_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/") or request.path.startswith("/api/payments/"):
        return await handler(request)          # to'lov webhooklari initData'siz: o'z imzo/secret tekshiruvi bor
    try:
        return await _authorized(request, handler)
    except web.HTTPException:
        raise
    except Exception:  # noqa: BLE001 — Mini App "noma'lum xato" o'rniga aniq javob olsin
        log.exception("API xatosi: %s %s", request.method, request.path)
        return _err(500, "server_error", "Serverda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")


async def _authorized(request: web.Request, handler):

    header = request.headers.get("Authorization", "")
    init_data = header[4:] if header.lower().startswith("tma ") else ""
    try:
        tg_user = validate_init_data(init_data, settings.bot_token)
    except AuthError as ex:
        return _err(401, "unauthorized", "Ilovani Telegram orqali qayta oching.", detail=str(ex))

    async with SessionMaker() as session:
        user = await repo.get_or_create_user(
            session, int(tg_user["id"]), tg_user.get("username"),
            " ".join(filter(None, [tg_user.get("first_name"), tg_user.get("last_name")])),
        )
        if user.is_banned:
            return _err(403, "banned", "Siz bloklangansiz.")

        missing = await missing_channels(request.app["bot"], user.tg_id)
        if missing:
            return _err(
                403, "subscription_required", "Avval kanalga obuna bo'ling.",
                channels=[{"title": c.title, "url": c.url} for c in missing],
            )

        request["user"] = user
        request["session"] = session
        request["tg_user"] = tg_user
        return await handler(request)


# ─────────────────────────── Serializers ───────────────────────────

def _product(p, sold: dict[int, int]) -> dict:
    supplier = canboso.is_supplier_product(p)
    meta = canboso.product_meta(p) if supplier else {}
    # Ta'minotchi yozgan tayyor tavsif («Turi/Kafolat/Buyurtma qo'lda…») mijozga ko'rsatilmaydi:
    # faqat admin o'zi yozgan tavsif chiqadi. Tushuntirish kartasi (X nima?) info.js dan keladi.
    desc = (p.description or "") if (not supplier or "description" in overrides.locked(p)) else ""
    return {
        "brand": p.brand,
        "logo": p.logo,                      # logotip olinadigan sayt domeni
        "warranty": warranty_public(p) or None,    # xariddan oldin faqat havola/kod mahsulotlarida; login-parol kafolati — xariddan keyin
        "need": meta.get("need"),            # "email" | "accounts" | None
        "ptype": meta.get("type"),           # "account" | "slot" | "upgrade_account" — qanday olinishi
        "fixed_qty": meta.get("fixed_qty"),
        "id": p.id,
        "category_id": p.category_id,
        "name": p.name,
        "emoji": p.emoji,
        "description": desc,
        "guide": guide_of(p),                # admin yozgan, bo'lmasa mahsulot turiga mos tayyor qo'llanma
        "video": has_video(p),               # video qo'llanma yuklangan
        "price": p.price,
        "old_price": p.old_price,
        "stock": repo.stock_of(p),          # None = cheksiz
        "manual": p.delivery_type == DeliveryType.MANUAL,
        "image_url": p.image_url,
        "sold": sold.get(p.id, 0),
    }


async def _extras(s, orders) -> dict[int, dict]:
    """Buyurtmadagi mahsulotlar uchun: {product_id: {guide, note (kafolat matni), video}}."""
    ids = {i.product_id for o in orders for i in o.items if i.product_id}
    if not ids:
        return {}
    rows = await s.scalars(select(Product).where(Product.id.in_(ids)))
    return {p.id: {"guide": guide_of(p), "note": warranty_note(p), "video": has_video(p), "hours": warranty_hours(p)} for p in rows}


def _warranty_until(order, extra) -> str | None:
    """Kafolat tugash vaqti: buyurtma vaqti + kafolat muddati (muddat noma'lum bo'lsa None)."""
    h = (extra or {}).get("hours")
    return _iso(order.created_at + timedelta(hours=h)) if h and order.created_at else None


def _order(o, extras: dict[int, dict] | None = None) -> dict:
    extras = extras or {}
    return {
        "id": o.id,
        "total": o.total,
        "status": o.status.value,
        "created_at": _iso(o.created_at),
        "items": [
            {"name": i.product_name, "qty": i.qty, "price": i.price, "product_id": i.product_id,
             "content": i.delivered_content, "status": i.status,
             "guide": (extras.get(i.product_id) or {}).get("guide", "") if i.status != "failed" else "",
             "warranty": (extras.get(i.product_id) or {}).get("note", "") if i.status != "failed" else "",
             "warranty_until": _warranty_until(o, extras.get(i.product_id)) if i.status != "failed" else None,
             "video": bool((extras.get(i.product_id) or {}).get("video")) and i.status != "failed"}
            for i in o.items
        ],
    }


def _payment(p) -> dict:
    return {
        "id": p.id,
        "amount": p.amount,
        "provider": p.provider,
        "status": p.status.value,
        "created_at": _iso(p.created_at),
    }


# ─────────────────────────── Handlers ───────────────────────────

async def bootstrap(request: web.Request) -> web.Response:
    s, user = request["session"], request["user"]
    cats = await repo.active_categories(s)
    products = await repo.storefront_products(s)
    sold = await repo.sales_by_product(s)
    return web.json_response({
        "user": {
            "id": user.tg_id,
            "name": user.full_name,
            "username": user.username,
            "photo_url": request["tg_user"].get("photo_url"),
            "balance": user.balance,
            "is_admin": user.tg_id in settings.admins,
            "lang": user.lang,
        },
        "categories": [
            {"id": c.id, "name": c.name(user.lang), "emoji": c.emoji} for c in cats
        ],
        "products": [_product(p, sold) for p in products],
        "config": {
            "support": runtime.support_username(),
            "min_topup": MIN_TOPUP,
            "card_last4": "".join(c for c in runtime.card_number() if c.isdigit())[-4:] if paynotify.card_enabled() else "",
            "providers": [
                {"code": "card", "configured": paynotify.card_enabled()},
                {"code": "payme", "configured": paynotify.payme_enabled()},
                {"code": "click", "configured": paynotify.click_enabled()},
                {"code": "manual", "configured": True},
            ],
        },
    })


async def me(request: web.Request) -> web.Response:
    return web.json_response({"balance": request["user"].balance})


async def orders(request: web.Request) -> web.Response:
    items = await repo.user_orders(request["session"], request["user"], limit=30)
    extras = await _extras(request["session"], items)
    return web.json_response({"orders": [_order(o, extras) for o in items]})


async def payments(request: web.Request) -> web.Response:
    items = await repo.user_payments(request["session"], request["user"])
    return web.json_response({"payments": [_payment(p) for p in items]})


async def checkout(request: web.Request) -> web.Response:
    s, user = request["session"], request["user"]
    try:
        body = await request.json()
        raw = body["items"]
        wanted: dict[int, int] = {}
        given: dict[int, dict] = {}
        for row in raw[:MAX_LINES]:
            pid, qty = int(row["product_id"]), int(row["qty"])
            if not 1 <= qty <= MAX_QTY:
                raise ValueError
            wanted[pid] = wanted.get(pid, 0) + qty
            given[pid] = {"email": row.get("email"), "accounts": row.get("accounts")}
        if not wanted:
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        return _err(400, "bad_request", "So'rov noto'g'ri.")

    lines = []
    extras: dict[int, dict] = {}
    for pid, qty in wanted.items():
        product = await repo.get_product(s, pid)
        if not product or not product.is_active:
            return _err(404, "not_found", "Mahsulot topilmadi yoki sotuvdan olingan.")
        try:   # email / akkaunt so'raydigan mahsulotlar uchun ma'lumotni oldindan tekshiramiz
            extras[pid] = fulfillment.clean_extras(
                product, qty, given[pid]["email"], given[pid]["accounts"]
            )
        except ValueError as ex:
            return _err(400, "bad_input", str(ex), product=product.name)
        lines.append((product, qty))

    # Katalog har 3 daqiqada yangilanadi: mijoz ko'rgan narx o'zgargan bo'lsa, pulni yechmasdan oldin ogohlantiramiz
    try:
        expected = int(body["total"]) if body.get("total") is not None else None
    except (ValueError, TypeError):
        expected = None
    actual = sum(p.price * q for p, q in lines)
    if expected is not None and expected != actual:
        return _err(409, "price_changed", "Narx yangilandi. Yangi narxni ko'rib chiqing.", total=actual)

    try:
        order = await repo.create_order(s, user, lines)
    except repo.NotEnoughBalance as ex:
        return _err(402, "not_enough_balance", "Hisobda mablag' yetarli emas.",
                    need=ex.need, have=ex.have)
    except repo.OutOfStock as ex:
        return _err(409, "out_of_stock", f"{ex.product_name} zaxirasi tugab qoldi.",
                    product=ex.product_name)

    bot = request.app["bot"]
    rep = await fulfillment.fulfill(s, user, order, extras)   # ta'minotchidan xarid
    extras = await _extras(s, [order])
    guides = {pid: e["guide"] for pid, e in extras.items() if e["guide"]}
    warranties = {pid: e["note"] for pid, e in extras.items() if e["note"]}
    if order.status.value == "cancelled":
        await fulfillment.alert_admins(bot, user, order, rep)
        return _err(502, "supplier_failed",
                    "Buyurtma bajarilmadi, mablag' hisobingizga qaytarildi. Birozdan so'ng urinib ko'ring.",
                    balance=user.balance)
    try:  # kodlar chatda ham saqlanib qoladi
        sup = runtime.support_username()
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"💬 @{sup} ga yozish", url=f"https://t.me/{sup}")]]) if sup else None
        await bot.send_message(user.tg_id, order_success_text(user.lang, order, user.balance, guides, warranties, sup), reply_markup=kb)
    except Exception:  # noqa: BLE001 — foydalanuvchi botni bloklagan bo'lishi mumkin
        log.info("Buyurtma xabarini chatga yuborib bo'lmadi: %s", user.tg_id)
    await _send_videos(bot, user, order, extras)
    await notify_admins_order(bot, user, order)
    await fulfillment.alert_admins(bot, user, order, rep)

    return web.json_response({"order": _order(order, extras), "balance": user.balance,
                              "refunded": rep.refunded})


def _topup_payload(order, provider: str) -> dict:
    out = {
        "id": order.id, "amount": order.payment_amount, "base_amount": order.base_amount,
        "status": order.status, "expires_at": _iso(order.expires_at), "provider": provider,
    }
    if provider == "card":
        out.update(card=paynotify.fmt_card(runtime.card_number()), owner=runtime.card_owner())
    elif provider == "payme":
        out["url"] = paynotify.payme_url(order)
    elif provider == "click":
        out["url"] = paynotify.click_url(order)
    return out


async def topup(request: web.Request) -> web.Response:
    s, user = request["session"], request["user"]
    try:
        body = await request.json()
        amount = int(body["amount"])
        provider_code = str(body.get("provider", "manual"))
    except (ValueError, KeyError, TypeError):
        return _err(400, "bad_request", "So'rov noto'g'ri.")
    if not MIN_TOPUP <= amount <= MAX_TOPUP:
        return _err(400, "bad_amount", f"Summa {MIN_TOPUP} dan {MAX_TOPUP} gacha bo'lishi kerak.")

    if provider_code in ("card", "payme", "click"):
        enabled = {"card": paynotify.card_enabled(), "payme": paynotify.payme_enabled(), "click": paynotify.click_enabled()}
        if not enabled[provider_code]:
            return _err(400, "provider_off", "Bu to'lov usuli hozircha mavjud emas.")
        try:
            order = await topup_core.create_order(s, user, amount, provider_code, chat_id=user.tg_id)
        except topup_core.OrderError as ex:
            return _err(400, "order_error", str(ex))
        try:   # bot chatida ham yo'riqnoma va tugmalar qoladi
            await paynotify.send_order(request.app["bot"], order)
        except Exception:  # noqa: BLE001 — foydalanuvchi botni bloklagan bo'lishi mumkin
            log.info("To'lov yo'riqnomasini chatga yuborib bo'lmadi: %s", user.tg_id)
        return web.json_response({"order": _topup_payload(order, provider_code), "manual": False})

    try:
        provider = PROVIDERS[provider_code]
    except KeyError:
        return _err(400, "bad_request", "So'rov noto'g'ri.")
    payment = await repo.create_payment(s, user, amount, provider_code)
    await notify_admins_payment(request.app["bot"], user, payment, provider)
    return web.json_response({"payment": _payment(payment), "url": None, "manual": True})


async def topup_check(request: web.Request) -> web.Response:
    """«To'lov qildim — tekshirish» va holatni so'rash (Mini App har 5 soniyada)."""
    s, user = request["session"], request["user"]
    try:
        oid = int((await request.json())["order_id"])
    except (ValueError, KeyError, TypeError):
        return _err(400, "bad_request", "So'rov noto'g'ri.")
    order = await topup_core.get_order(s, oid)
    if not order or order.user_id != user.id:               # begona buyurtma
        return _err(404, "not_found", "Buyurtma topilmadi.")
    if order.status == "pending" and order.expires_at <= topup_core.utcnow():
        await topup_core.sweep_expired(s)
        order = await topup_core.get_order(s, oid)
    if order.status == "pending":
        out = await topup_core.recheck_order(s, order)
        if out.kind == "matched" and out.order:
            await paynotify.report_paid(request.app["bot"], out.order, out.result.balance if out.result else None, "tekshirish")
            order = out.order
    fresh = await s.get(type(user), user.id, populate_existing=True)
    return web.json_response({"status": order.status, "balance": fresh.balance})


async def _send_videos(bot, user, order, extras: dict[int, dict]) -> None:
    """Xariddan keyin: video qo'llanmasi bor mahsulotlar uchun video chatga yuboriladi (har biri bir martadan)."""
    done: set[int] = set()
    for item in order.items:
        pid = item.product_id
        if not pid or pid in done or item.status == "failed" or not (extras.get(pid) or {}).get("video"):
            continue
        done.add(pid)
        await _deliver_video(bot, user.tg_id, await _product_video(pid), item.product_name)


async def _product_video(pid: int) -> str:
    async with SessionMaker() as s:
        p = await s.get(Product, pid)
        return (p.guide_video or "").strip() if p else ""


async def _deliver_video(bot, chat_id: int, ref: str, name: str) -> bool:
    if not ref.startswith("tg:"):
        return False
    try:
        await bot.send_video(chat_id, ref[3:], caption=f"🎬 {name} — video qo'llanma")
        return True
    except Exception:  # noqa: BLE001 — fayl o'chirilgan yoki foydalanuvchi botni bloklagan
        log.info("Video qo'llanma yuborilmadi: %s", chat_id)
        return False


async def guide_video(request: web.Request) -> web.Response:
    """Video qo'llanma: havola bo'lsa — havola qaytadi, yuklangan video bo'lsa — botga (chatga) yuboriladi."""
    s, user = request["session"], request["user"]
    try:
        pid = int((await request.json())["product_id"])
    except (ValueError, KeyError, TypeError):
        return _err(400, "bad_request", "So'rov noto'g'ri.")
    p = await repo.get_product(s, pid)
    ref = (p.guide_video or "").strip() if p else ""
    if not ref:
        return _err(404, "not_found", "Bu mahsulot uchun video qo'llanma yo'q.")
    if ref.startswith("http"):
        return web.json_response({"url": ref})
    if not await _deliver_video(request.app["bot"], user.tg_id, ref, p.name):
        return _err(502, "send_failed", "Videoni yuborib bo'lmadi. Avval botga /start bosing.")
    return web.json_response({"sent": True})


def add_routes(app: web.Application) -> None:
    app.router.add_get("/api/bootstrap", bootstrap)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/orders", orders)
    app.router.add_get("/api/payments", payments)
    app.router.add_post("/api/checkout", checkout)
    app.router.add_post("/api/guide_video", guide_video)
    app.router.add_post("/api/topup", topup)
    app.router.add_post("/api/topup/check", topup_check)
