"""To'lov webhooklari: SMS, Payme (JSON-RPC), Click (prepare/complete).

Hammasi `topup.confirm_order` ga keladi (atomar, idempotent). Mini App initData'siz ishlaydi — himoya:
SMS — secret (constant-time) + rate limit; Payme — Basic Authorization; Click — MD5 imzo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from collections import defaultdict, deque

from aiohttp import web
from sqlalchemy import select

from config import settings
from database.db import SessionMaker
from database.models import ClickTransaction, PaymeTransaction, TopupOrder
from services import paynotify, topup

log = logging.getLogger("uzshop.payhooks")

SMS_MAX_LEN = 1000
SMS_RATE = 20            # bitta IP dan daqiqasiga
SMS_RATE_GLOBAL = 120
_hits: dict[str, deque] = defaultdict(deque)


def _rate_ok(key: str, limit: int) -> bool:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _ip(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.remote or "?")[:64]


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode(), (b or "").encode())


# ─────────────────────────── SMS ───────────────────────────

_TEXT_KEYS = ("text", "message", "body", "sms", "msg", "content")
_SECRET_KEYS = ("secret", "key", "token")


async def _sms_fields(request: web.Request) -> tuple[str, object]:
    """SMS-yuboruvchi ilovalar har xil: kalit va matn JSON, forma, havola (?secret=…&text=…) yoki sarlavhada bo'lishi mumkin."""
    data: dict = {}
    ctype = request.content_type or ""
    try:
        if "json" in ctype:
            body = await request.json()
            data = body if isinstance(body, dict) else {}
        elif "form" in ctype:
            data = dict(await request.post())
        else:
            raw = (await request.text()).strip()
            if raw.startswith("{"):
                import json as _json
                body = _json.loads(raw)
                data = body if isinstance(body, dict) else {}
            elif raw:
                data = {"text": raw}                  # oddiy matn (text/plain): butun tana — SMS matni
    except Exception:  # noqa: BLE001
        data = {}
    q = request.query
    given = next((str(v) for k in _SECRET_KEYS for v in (data.get(k), q.get(k)) if v), "") or request.headers.get("X-Secret", "")
    text = next((v for k in _TEXT_KEYS for v in (data.get(k), q.get(k)) if v), None)
    return given, text


async def sms(request: web.Request) -> web.Response:
    """POST (yoki GET) /api/payments/sms — kalit: secret / key / token (JSON, forma, ?havola yoki X-Secret sarlavha),
    matn: text / message / body / sms."""
    secret = settings.sms_webhook_secret
    if not _rate_ok("sms:" + _ip(request), SMS_RATE) or not _rate_ok("sms:*", SMS_RATE_GLOBAL):
        return web.json_response({"ok": False, "error": "rate_limited"}, status=429)
    given, text = await _sms_fields(request)
    if not secret or not _eq(given, secret):          # secret sozlanmagan bo'lsa ham yopiq
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    if not isinstance(text, str) or not text.strip() or len(text) > SMS_MAX_LEN:
        return web.json_response({"ok": False, "error": "bad_text"}, status=400)
    msg_id = hashlib.sha256(f"{text}|{int(time.time() // 60)}".encode()).hexdigest()[:32]
    out = await paynotify.process_incoming(request.app["bot"], "sms", msg_id, text, "card")
    return web.json_response({"ok": True, "result": out.kind})


# ─────────────────────────── Payme ───────────────────────────

PAYME_TIMEOUT_MS = 12 * 3600 * 1000


def _pe(code: int, ru: str, uz: str, en: str, rid, data=None) -> web.Response:
    err = {"code": code, "message": {"ru": ru, "uz": uz, "en": en}}
    if data is not None:
        err["data"] = data
    return web.json_response({"jsonrpc": "2.0", "id": rid, "error": err})


def _pok(result: dict, rid) -> web.Response:
    return web.json_response({"jsonrpc": "2.0", "id": rid, "result": result})


E_AUTH = (-32504, "Недостаточно привилегий", "Ruxsat yo'q", "Insufficient privilege")
E_ORDER = (-31050, "Заказ не найден", "Buyurtma topilmadi", "Order not found")
E_AMOUNT = (-31001, "Неверная сумма", "Noto'g'ri summa", "Incorrect amount")
E_CANT = (-31008, "Невозможно выполнить операцию", "Amalni bajarib bo'lmaydi", "Unable to perform operation")
E_TXN = (-31003, "Транзакция не найдена", "Tranzaksiya topilmadi", "Transaction not found")
E_BUSY = (-31099, "Заказ уже оплачивается", "Buyurtma boshqa tranzaksiyada", "Order has another active transaction")
E_NOCANCEL = (-31007, "Заказ выполнен, отмена невозможна", "Buyurtma bajarilgan, bekor qilib bo'lmaydi", "Cannot cancel")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _payme_auth_ok(request: web.Request) -> bool:
    key = settings.payme_auth_key
    if not key:
        return False                                   # PAYME_KEY yo'q — integratsiya yopiq
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode()
    except Exception:  # noqa: BLE001
        return False
    return _eq(raw, f"Paycom:{key}")


def _txn_result(t: PaymeTransaction) -> dict:
    return {"create_time": t.create_time, "perform_time": t.perform_time or 0, "cancel_time": t.cancel_time or 0,
            "transaction": str(t.id), "state": t.state, "reason": t.reason}


async def _check_perform(s, params: dict, rid):
    """(order, None) yoki (None, javob). Buyurtma, summa, holat va muddat tekshiriladi."""
    acc = params.get("account") or {}
    try:
        order_id = int(acc.get("order_id"))
        amount = int(params.get("amount"))
    except (TypeError, ValueError):
        return None, _pe(*E_ORDER, rid, "order_id")
    order = await topup.get_order(s, order_id)
    if not order:
        return None, _pe(*E_ORDER, rid, "order_id")
    if amount != order.payment_amount * 100:
        return None, _pe(*E_AMOUNT, rid, "amount")
    if not topup.is_active(order):                     # to'langan / bekor / muddati tugagan
        return None, _pe(*E_CANT, rid)
    return order, None


async def payme(request: web.Request) -> web.Response:
    """POST /api/payments/payme — Payme Merchant API (JSON-RPC 2.0)."""
    try:
        body = await request.json()
        rid, method, params = body.get("id"), body.get("method"), body.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError
    except Exception:  # noqa: BLE001
        return _pe(-32700, "Ошибка парсинга", "Parsing xatosi", "Parse error", None)
    if not _payme_auth_ok(request):
        return _pe(*E_AUTH, rid)
    try:
        async with SessionMaker() as s:
            if method == "CheckPerformTransaction":
                order, err = await _check_perform(s, params, rid)
                return err if err is not None else _pok({"allow": True}, rid)

            if method == "CreateTransaction":
                pid = str(params.get("id") or "")
                if not pid:
                    return _pe(-32602, "Неверные параметры", "Noto'g'ri parametr", "Invalid params", rid, "id")
                t = await s.scalar(select(PaymeTransaction).where(PaymeTransaction.payme_id == pid))
                if t:
                    if t.state != 1:
                        return _pe(*E_CANT, rid)
                    if _now_ms() - t.create_time > PAYME_TIMEOUT_MS:
                        t.state, t.reason, t.cancel_time = -1, 4, _now_ms()
                        await s.commit()
                        return _pe(*E_CANT, rid)
                    return _pok({"create_time": t.create_time, "transaction": str(t.id), "state": 1}, rid)
                order, err = await _check_perform(s, params, rid)
                if err is not None:
                    return err
                other = await s.scalar(select(PaymeTransaction.id).where(
                    PaymeTransaction.order_id == order.id, PaymeTransaction.state == 1))
                if other is not None:
                    return _pe(*E_BUSY, rid, "order_id")
                try:
                    ct = int(params.get("time") or _now_ms())
                except (TypeError, ValueError):
                    ct = _now_ms()
                t = PaymeTransaction(payme_id=pid, order_id=order.id, amount_tiyin=order.payment_amount * 100,
                                     state=1, create_time=ct)
                s.add(t)
                await topup.log_event(s, order.id, "payme_create", "payme", pid)
                await s.commit()
                return _pok({"create_time": t.create_time, "transaction": str(t.id), "state": 1}, rid)

            if method in ("PerformTransaction", "CancelTransaction", "CheckTransaction"):
                pid = str(params.get("id") or "")
                t = await s.scalar(select(PaymeTransaction).where(PaymeTransaction.payme_id == pid)) if pid else None
                if not t:
                    return _pe(*E_TXN, rid)
                if method == "CheckTransaction":
                    return _pok(_txn_result(t), rid)

                if method == "PerformTransaction":
                    if t.state == 2:
                        return _pok({"transaction": str(t.id), "perform_time": t.perform_time, "state": 2}, rid)
                    if t.state != 1:
                        return _pe(*E_CANT, rid)
                    if _now_ms() - t.create_time > PAYME_TIMEOUT_MS:
                        t.state, t.reason, t.cancel_time = -1, 4, _now_ms()
                        await s.commit()
                        return _pe(*E_CANT, rid)
                    res = await topup.confirm_order(s, t.order_id, "payme", pid)
                    if not (res.ok or (res.status == "already_paid" and res.order and res.order.provider == "payme"
                                       and res.order.provider_txn_id == pid)):
                        return _pe(*E_CANT, rid)
                    t = await s.get(PaymeTransaction, t.id, populate_existing=True)
                    t.state, t.perform_time = 2, _now_ms()
                    await s.commit()
                    if res.ok and res.order:
                        await paynotify.report_paid(request.app["bot"], res.order, res.balance, "payme")
                    return _pok({"transaction": str(t.id), "perform_time": t.perform_time, "state": 2}, rid)

                # CancelTransaction
                reason = params.get("reason")
                if t.state in (-1, -2):
                    return _pok({"transaction": str(t.id), "cancel_time": t.cancel_time, "state": t.state}, rid)
                if t.state == 1:
                    t.state, t.cancel_time, t.reason = -1, _now_ms(), reason
                    await s.commit()
                    return _pok({"transaction": str(t.id), "cancel_time": t.cancel_time, "state": -1}, rid)
                if not await topup.reverse_order(s, t.order_id):          # to'langan: faqat mablag' yetarli bo'lsa
                    return _pe(*E_NOCANCEL, rid)
                t = await s.get(PaymeTransaction, t.id, populate_existing=True)
                t.state, t.cancel_time, t.reason = -2, _now_ms(), reason
                await s.commit()
                return _pok({"transaction": str(t.id), "cancel_time": t.cancel_time, "state": -2}, rid)

            return _pe(-32601, "Метод не найден", "Metod topilmadi", "Method not found", rid, method)
    except Exception:  # noqa: BLE001
        log.exception("Payme xatosi")
        return _pe(-32400, "Системная ошибка", "Tizim xatosi", "System error", rid)


# ─────────────────────────── Click ───────────────────────────

def _click_resp(params: dict, error: int, note: str, **extra) -> web.Response:
    data = {"click_trans_id": params.get("click_trans_id"), "merchant_trans_id": params.get("merchant_trans_id"),
            "error": error, "error_note": note, **extra}
    return web.json_response(data)


def _click_sign(params: dict, complete: bool) -> str:
    parts = [params.get("click_trans_id", ""), params.get("service_id", ""), settings.click_secret_key,
             params.get("merchant_trans_id", "")]
    if complete:
        parts.append(params.get("merchant_prepare_id", ""))
    parts += [params.get("amount", ""), params.get("action", ""), params.get("sign_time", "")]
    return hashlib.md5("".join(str(x) for x in parts).encode()).hexdigest()


async def _click_common(request: web.Request, complete: bool):
    """(params, javob) — imzo, service_id va majburiy maydonlar tekshiriladi."""
    if not (settings.click_secret_key and settings.click_service_id):
        return None, web.json_response({"error": -1, "error_note": "Integration disabled"}, status=403)
    try:
        form = await request.post()
        params = {k: str(v) for k, v in form.items()}
    except Exception:  # noqa: BLE001
        return None, web.json_response({"error": -8, "error_note": "Error in request from click"})
    need = ["click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time", "sign_string"]
    if complete:
        need.append("merchant_prepare_id")
    if any(k not in params or params[k] == "" for k in need):
        return params, _click_resp(params, -8, "Error in request from click")
    if not _eq(_click_sign(params, complete).lower(), params["sign_string"].lower()):
        return params, _click_resp(params, -1, "SIGN CHECK FAILED!")
    if not _eq(params["service_id"], str(settings.click_service_id)):
        return params, _click_resp(params, -1, "SIGN CHECK FAILED!")
    if params["action"] != ("1" if complete else "0"):
        return params, _click_resp(params, -3, "Action not found")
    try:
        float(params["amount"])
        int(params["merchant_trans_id"])
    except ValueError:
        return params, _click_resp(params, -8, "Error in request from click")
    return params, None


def _amount_ok(order: TopupOrder, amount: str) -> bool:
    return abs(float(amount) - order.payment_amount) < 0.01


async def click_prepare(request: web.Request) -> web.Response:
    params, err = await _click_common(request, complete=False)
    if err is not None:
        return err
    try:
        async with SessionMaker() as s:
            order = await topup.get_order(s, int(params["merchant_trans_id"]))
            if not order:
                return _click_resp(params, -5, "Order not found")
            if order.status == "paid":
                return _click_resp(params, -4, "Already paid")
            if not topup.is_active(order):
                return _click_resp(params, -9, "Transaction cancelled")
            if not _amount_ok(order, params["amount"]):
                return _click_resp(params, -2, "Incorrect parameter amount")
            t = await s.scalar(select(ClickTransaction).where(ClickTransaction.click_trans_id == params["click_trans_id"]))
            if not t:
                t = ClickTransaction(click_trans_id=params["click_trans_id"], order_id=order.id, amount=order.payment_amount)
                s.add(t)
                await topup.log_event(s, order.id, "click_prepare", "click", params["click_trans_id"])
                await s.commit()
            elif t.order_id != order.id or t.state == "cancelled":
                return _click_resp(params, -9, "Transaction cancelled")
            return _click_resp(params, 0, "Success", merchant_prepare_id=t.id)
    except Exception:  # noqa: BLE001
        log.exception("Click prepare xatosi")
        return _click_resp(params, -7, "Failed to update user")


async def click_complete(request: web.Request) -> web.Response:
    params, err = await _click_common(request, complete=True)
    if err is not None:
        return err
    try:
        click_error = int(str(params.get("error", "")).strip())      # error maydoni majburiy va haqiqiy son
    except ValueError:
        return _click_resp(params, -8, "Error in request from click")
    try:
        async with SessionMaker() as s:
            order = await topup.get_order(s, int(params["merchant_trans_id"]))
            if not order:
                return _click_resp(params, -5, "Order not found")
            try:
                prep_id = int(params["merchant_prepare_id"])
            except ValueError:
                return _click_resp(params, -8, "Error in request from click")
            t = await s.get(ClickTransaction, prep_id, populate_existing=True)
            if not t or t.click_trans_id != params["click_trans_id"] or t.order_id != order.id:
                return _click_resp(params, -6, "Transaction does not exist")
            if not _amount_ok(order, params["amount"]):
                return _click_resp(params, -2, "Incorrect parameter amount")
            if t.state == "completed":
                return _click_resp(params, -4, "Already paid", merchant_confirm_id=t.id)
            if t.state == "cancelled":
                return _click_resp(params, -9, "Transaction cancelled")
            if click_error < 0:                                   # Click o'zi bekor qildi
                t.state = "cancelled"
                await topup.log_event(s, order.id, "click_cancel", "click", str(click_error))
                await s.commit()
                return _click_resp(params, -9, "Transaction cancelled")
            res = await topup.confirm_order(s, order.id, "click", params["click_trans_id"])
            if res.status == "already_paid":
                return _click_resp(params, -4, "Already paid", merchant_confirm_id=t.id)
            if not res.ok:
                return _click_resp(params, -9, "Transaction cancelled")
            t = await s.get(ClickTransaction, prep_id, populate_existing=True)
            t.state = "completed"
            t.completed_at = topup.utcnow()
            await s.commit()
            await paynotify.report_paid(request.app["bot"], res.order, res.balance, "click")
            return _click_resp(params, 0, "Success", merchant_confirm_id=t.id)
    except Exception:  # noqa: BLE001
        log.exception("Click complete xatosi")
        return _click_resp(params, -7, "Failed to update user")


def add_routes(app: web.Application) -> None:
    app.router.add_post("/api/payments/sms", sms)
    app.router.add_get("/api/payments/sms", sms)       # ba'zi ilovalar faqat GET yubora oladi (?secret=…&text=…)
    app.router.add_post("/api/payments/payme", payme)
    app.router.add_post("/api/payments/click/prepare", click_prepare)
    app.router.add_post("/api/payments/click/complete", click_complete)
