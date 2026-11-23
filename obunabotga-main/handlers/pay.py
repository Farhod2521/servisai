"""Avtomatik to'lov: mijoz buyurtmasi (/topup) va to'lov administratori (faqat Telegram ID = TELEGRAM_OWNER_ID).

Admin huquqi username bilan EMAS, faqat raqamli ID bilan tekshiriladi. Mijoz callback tugmalarida
buyurtma shu mijozniki ekani tekshiriladi.
"""
from __future__ import annotations

import html
import logging
from datetime import timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Payment, TopupOrder, User
from locales.texts import money
from services import paynotify, runtime, topup
from services.paynotify import is_owner

router = Router(name="pay")
log = logging.getLogger(__name__)

AMOUNTS = [20_000, 50_000, 100_000, 200_000]


class PayFlow(StatesGroup):
    amount = State()


class AdminPay(StatesGroup):
    card = State()
    owner = State()
    parse = State()


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])


# ─────────────────────────── Mijoz ───────────────────────────

def _amounts_kb() -> InlineKeyboardMarkup:
    rows = [[(f"{a:,}".replace(",", " ") + " so'm", f"pay:amt:{a}") for a in AMOUNTS[i:i + 2]] for i in range(0, len(AMOUNTS), 2)]
    rows.append([("✏️ Boshqa summa", "pay:custom"), ("📊 Mening hisobim", "pay:me")])
    return _kb(rows)


def _not_available() -> str:
    return "⚠️ Avtomatik to'lov hozircha sozlanmagan. «Yordam» orqali administratorga yozing."


async def _start_order(message: Message, user: User, session: AsyncSession, amount: int) -> None:
    if not (paynotify.card_enabled() or paynotify.payme_enabled() or paynotify.click_enabled()):
        return await message.answer(_not_available())
    try:
        order = await topup.create_order(session, user, amount, "card", chat_id=message.chat.id)
    except topup.OrderError as ex:
        return await message.answer(f"❌ {html.escape(str(ex))}")
    await paynotify.send_order(message.bot, order)


@router.message(Command("topup", "tolov"))
async def cmd_topup(message: Message, user: User, state: FSMContext):
    await state.clear()
    await message.answer("💳 <b>Hamyonni to'ldirish</b>\n\nSummani tanlang:", reply_markup=_amounts_kb())


@router.callback_query(F.data == "pay:menu")
async def cb_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("💳 <b>Hamyonni to'ldirish</b>\n\nSummani tanlang:", reply_markup=_amounts_kb())
    await call.answer()


@router.callback_query(F.data.startswith("pay:amt:"))
async def cb_amount(call: CallbackQuery, user: User, session: AsyncSession):
    try:
        amount = int(call.data.split(":")[2])
    except ValueError:
        return await call.answer()
    if amount not in AMOUNTS:                      # tugmada yo'q summani yuborib bo'lmaydi
        return await call.answer("🚫", show_alert=True)
    await call.answer()
    await _start_order(call.message, user, session, amount)


@router.callback_query(F.data == "pay:custom")
async def cb_custom(call: CallbackQuery, state: FSMContext):
    await state.set_state(PayFlow.amount)
    await call.message.answer(f"✏️ Summani so'mda yozing (kamida {topup.MIN_AMOUNT:,} so'm). Masalan: <code>75000</code>".replace(",", " "))
    await call.answer()


@router.message(PayFlow.amount)
async def msg_custom(message: Message, user: User, session: AsyncSession, state: FSMContext):
    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit():
        return await message.answer("❌ Faqat raqam yozing. Masalan: <code>75000</code>")
    await state.clear()
    await _start_order(message, user, session, int(raw))


async def _own_order(session: AsyncSession, user: User, oid: int) -> TopupOrder | None:
    order = await topup.get_order(session, oid)
    return order if order and order.user_id == user.id else None     # begona buyurtmaga tegib bo'lmaydi


@router.callback_query(F.data.startswith("pay:check:"))
async def cb_check(call: CallbackQuery, user: User, session: AsyncSession):
    order = await _own_order(session, user, int(call.data.split(":")[2]))
    if not order:
        return await call.answer("🚫 Bu buyurtma sizniki emas.", show_alert=True)
    if order.status == "paid":
        return await call.answer("✅ To'lov allaqachon qabul qilingan.", show_alert=True)
    if order.status in ("cancelled", "expired") or not topup.is_active(order):
        return await call.answer("⌛ Buyurtma muddati tugagan yoki bekor qilingan. /topup bilan yangisini oching.", show_alert=True)
    out = await topup.recheck_order(session, order)
    if out.kind == "matched" and out.order:
        await call.answer("✅ To'lov topildi!")
        return await paynotify.report_paid(call.bot, out.order, out.result.balance if out.result else None, "tekshirish")
    await call.answer("⏳ To'lov hali tushmadi. Aniq summani yuborganingizni tekshiring — tushishi bilan o'zi tasdiqlanadi "
                      "(odatda 1–2 daqiqa).", show_alert=True)


@router.callback_query(F.data.startswith("pay:cancel:"))
async def cb_cancel(call: CallbackQuery, user: User, session: AsyncSession):
    oid = int(call.data.split(":")[2])
    if not await _own_order(session, user, oid):
        return await call.answer("🚫 Bu buyurtma sizniki emas.", show_alert=True)
    ok = await topup.cancel_order(session, oid, user.id)
    await call.answer("❌ Buyurtma bekor qilindi." if ok else "Buyurtma allaqachon yopilgan.", show_alert=True)
    if ok:
        try:
            await call.message.edit_text(f"❌ Buyurtma #{oid} bekor qilindi.")
        except Exception:  # noqa: BLE001
            pass


async def _me_text(session: AsyncSession, user: User) -> str:
    await topup.sweep_expired(session)
    pending = list(await session.scalars(select(TopupOrder).where(
        TopupOrder.user_id == user.id, TopupOrder.status == "pending").order_by(TopupOrder.id.desc())))
    last = list(await session.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc()).limit(5)))
    lines = ["📊 <b>Mening hisobim</b>", f"💰 Balans: <b>{money(user.balance)}</b>"]
    if pending:
        lines += ["", "⏳ Kutilayotgan to'lovlar:"] + [
            f"• #{o.id} · {money(o.payment_amount)} · {topup.to_tashkent_time(o.expires_at)} gacha" for o in pending]
    if last:
        lines += ["", "🧾 Oxirgi to'lovlar:"] + [
            f"• {topup.to_tashkent(p.paid_at or p.created_at)} · +{money(p.amount)} · {p.status.value}" for p in last]
    return "\n".join(lines)


@router.callback_query(F.data == "pay:me")
async def cb_me(call: CallbackQuery, user: User, session: AsyncSession):
    await call.message.answer(await _me_text(session, user), reply_markup=_kb([[("💳 To'ldirish", "pay:menu")]]))
    await call.answer()


@router.message(Command("hisob"))
async def cmd_me(message: Message, user: User, session: AsyncSession):
    await message.answer(await _me_text(session, user), reply_markup=_kb([[("💳 To'ldirish", "pay:menu")]]))


# ─────────────────────────── Administrator (faqat owner ID) ───────────────────────────

async def _deny(call: CallbackQuery) -> None:
    await call.answer("🚫", show_alert=True)


def _admin_kb() -> InlineKeyboardMarkup:
    auto = "🤖 Avto-tasdiq: " + ("yoqiq ✅" if runtime.autoconfirm_enabled() else "o‘chiq 🚫")
    return _kb([
        [("📋 Kutilayotgan to'lovlar", "pay:adm_list"), ("📊 To'lov statistikasi", "pay:adm_stats")],
        [("💳 Kartani o'zgartirish", "pay:adm_card"), ("👤 Karta egasini o'zgartirish", "pay:adm_owner")],
        [(auto, "pay:adm_auto")],
        [("🔎 Diagnostika", "pay:adm_diag"), ("🧪 Xabarni tekshirish", "pay:adm_parse")],
        [("⬅️ Orqaga", "a:home")],
    ])


def _admin_text() -> str:
    return ("💳 <b>To'lov tizimi</b>\n\n"
            f"Karta: <code>{paynotify.mask_card(runtime.card_number()) if runtime.card_number() else 'o‘rnatilmagan'}</code>\n"
            f"Karta egasi: <b>{html.escape(runtime.card_owner() or 'o‘rnatilmagan')}</b>\n"
            f"Payme: {'✅' if paynotify.payme_enabled() else '—'} · Click: {'✅' if paynotify.click_enabled() else '—'}\n"
            f"CardXabar: {'✅ sozlangan' if settings.tg_session else '—'} · SMS webhook: {'✅' if settings.sms_webhook_secret else '—'}")


@router.callback_query(F.data == "a:pay")
async def adm_menu(call: CallbackQuery, user: User, state: FSMContext):
    if not is_owner(user.tg_id):
        return await _deny(call)
    await state.clear()
    await call.message.edit_text(_admin_text(), reply_markup=_admin_kb())
    await call.answer()


@router.callback_query(F.data == "pay:adm_auto")
async def adm_auto(call: CallbackQuery, user: User):
    if not is_owner(user.tg_id):
        return await _deny(call)
    await runtime.set_value("pay_auto", "0" if runtime.autoconfirm_enabled() else "1")
    await call.message.edit_text(_admin_text(), reply_markup=_admin_kb())
    await call.answer("Avto-tasdiq " + ("yoqildi" if runtime.autoconfirm_enabled() else "o'chirildi"))


@router.callback_query(F.data == "pay:adm_card")
async def adm_card(call: CallbackQuery, user: User, state: FSMContext):
    if not is_owner(user.tg_id):
        return await _deny(call)
    await state.set_state(AdminPay.card)
    await call.message.edit_text("💳 Yangi karta raqamini yuboring (16 raqam).\nXabar xavfsizlik uchun yuborilgach o'chiriladi.",
                                 reply_markup=_kb([[("⬅️ Orqaga", "a:pay")]]))
    await call.answer()


@router.message(AdminPay.card)
async def adm_card_save(message: Message, user: User, state: FSMContext):
    if not is_owner(user.tg_id):
        return
    digits = "".join(c for c in (message.text or "") if c.isdigit())
    if len(digits) != 16:
        return await message.answer("❌ Karta raqami 16 ta raqam bo'lishi kerak.")
    await runtime.set_value("pay_card", digits)
    await state.clear()
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await message.answer("✅ Karta saqlandi.\n\n" + _admin_text(), reply_markup=_admin_kb())


@router.callback_query(F.data == "pay:adm_owner")
async def adm_owner(call: CallbackQuery, user: User, state: FSMContext):
    if not is_owner(user.tg_id):
        return await _deny(call)
    await state.set_state(AdminPay.owner)
    await call.message.edit_text("👤 Karta egasining ism-familiyasini yuboring (masalan: <code>ALI VALIYEV</code>).",
                                 reply_markup=_kb([[("⬅️ Orqaga", "a:pay")]]))
    await call.answer()


@router.message(AdminPay.owner)
async def adm_owner_save(message: Message, user: User, state: FSMContext):
    if not is_owner(user.tg_id):
        return
    name = (message.text or "").strip()
    if not 3 <= len(name) <= 60:
        return await message.answer("❌ 3–60 belgi yozing.")
    await runtime.set_value("pay_owner", name)
    await state.clear()
    await message.answer("✅ Karta egasi saqlandi.\n\n" + _admin_text(), reply_markup=_admin_kb())


@router.callback_query(F.data == "pay:adm_list")
async def adm_list(call: CallbackQuery, user: User, session: AsyncSession):
    if not is_owner(user.tg_id):
        return await _deny(call)
    await topup.sweep_expired(session)
    rows = list(await session.scalars(select(TopupOrder).where(TopupOrder.status == "pending").order_by(TopupOrder.id.desc()).limit(15)))
    late = list(await session.scalars(select(TopupOrder).where(
        TopupOrder.status == "expired", TopupOrder.expires_at >= topup.utcnow() - timedelta(hours=24))
        .order_by(TopupOrder.id.desc()).limit(10)))
    kb: list[list[tuple[str, str]]] = []
    lines = []
    for o in rows:
        lines.append(paynotify._order_line(o))
        kb.append([(f"✅ #{o.id}", f"pay:adm_ok:{o.id}"), (f"❌ #{o.id}", f"pay:adm_no:{o.id}")])
    if late:
        lines += ["", "⌛ <b>Muddati tugagan (24 soat)</b> — to'lov kech tushgan bo'lsa qo'lda tasdiqlang:"]
        for o in late:
            lines.append(paynotify._order_line(o))
            kb.append([(f"✅ #{o.id} (kech)", f"pay:adm_ok:{o.id}"), (f"❌ #{o.id}", f"pay:adm_no:{o.id}")])
    kb.append([("⬅️ Orqaga", "a:pay")])
    await call.message.edit_text("📋 <b>Kutilayotgan to'lovlar</b>\n\n" + ("\n".join(lines) if lines else "Yo'q."),
                                 reply_markup=_kb(kb))
    await call.answer()


@router.callback_query(F.data == "pay:adm_stats")
async def adm_stats(call: CallbackQuery, user: User, session: AsyncSession):
    if not is_owner(user.tg_id):
        return await _deny(call)
    now = topup.utcnow()

    async def paid(since):
        q = select(func.count(), func.coalesce(func.sum(TopupOrder.payment_amount), 0)).where(TopupOrder.status == "paid")
        if since:
            q = q.where(TopupOrder.paid_at >= since)
        n, total = (await session.execute(q)).one()
        return n, total

    d1, d7, allp = await paid(now - timedelta(days=1)), await paid(now - timedelta(days=7)), await paid(None)
    by_status = dict((await session.execute(select(TopupOrder.status, func.count()).group_by(TopupOrder.status))).all())
    by_prov = (await session.execute(select(TopupOrder.provider, func.count(), func.coalesce(func.sum(TopupOrder.payment_amount), 0))
                                      .where(TopupOrder.status == "paid").group_by(TopupOrder.provider))).all()
    text = ("📊 <b>To'lov statistikasi</b>\n\n"
            f"24 soat: <b>{d1[0]}</b> ta · {money(d1[1])}\n7 kun: <b>{d7[0]}</b> ta · {money(d7[1])}\n"
            f"Jami: <b>{allp[0]}</b> ta · {money(allp[1])}\n\n"
            f"Holatlar: " + ", ".join(f"{k} {v}" for k, v in sorted(by_status.items())) + "\n"
            + "".join(f"• {p}: {n} ta · {money(t)}\n" for p, n, t in by_prov))
    await call.message.edit_text(text, reply_markup=_kb([[("⬅️ Orqaga", "a:pay")]]))
    await call.answer()


@router.callback_query(F.data.startswith("pay:adm_ok:"))
async def adm_ok(call: CallbackQuery, user: User, session: AsyncSession):
    if not is_owner(user.tg_id):
        return await _deny(call)
    parts = call.data.split(":")
    oid = int(parts[2])
    res = await topup.confirm_order(session, oid, "card", f"manual:{user.tg_id}:{oid}", force=True)
    if res.ok and res.order:
        if len(parts) > 3:
            from database.models import BankCredit
            c = await session.get(BankCredit, int(parts[3]))
            if c:
                c.status, c.order_id = "matched", oid
                await session.commit()
        await paynotify.report_paid(call.bot, res.order, res.balance, "qo'lda (admin)")
        text = f"✅ #{oid} tasdiqlandi."
    else:
        text = {"already_paid": "ℹ️ Allaqachon to'langan.", "cancelled": "ℹ️ Buyurtma bekor qilingan.",
                "duplicate_txn": "ℹ️ Bu tranzaksiya allaqachon ishlatilgan.", "not_found": "🚫 Topilmadi."}.get(res.status, "❌ Bajarilmadi.")
    try:
        await call.message.edit_text(text)
    except Exception:  # noqa: BLE001
        pass
    await call.answer(text, show_alert=True)


@router.callback_query(F.data.startswith("pay:adm_no:"))
async def adm_no(call: CallbackQuery, user: User, session: AsyncSession):
    if not is_owner(user.tg_id):
        return await _deny(call)
    oid = int(call.data.split(":")[2])
    order = await topup.get_order(session, oid)
    ok = False
    if order and order.status in ("pending", "expired"):
        order.status = "cancelled"
        await topup.log_event(session, oid, "rejected", None, f"admin {user.tg_id}")
        await session.commit()
        ok = True
        try:
            await call.bot.send_message(order.telegram_chat_id, f"❌ To'lov #{oid} rad etildi. Savol bo'lsa «Yordam»ga yozing.")
        except Exception:  # noqa: BLE001
            pass
    text = f"❌ #{oid} rad etildi." if ok else "ℹ️ Bu buyurtmani rad etib bo'lmaydi."
    try:
        await call.message.edit_text(text)
    except Exception:  # noqa: BLE001
        pass
    await call.answer(text, show_alert=True)


# ─────────────────────────── Diagnostika ───────────────────────────

@router.callback_query(F.data == "pay:adm_diag")
async def adm_diag(call: CallbackQuery, user: User, session: AsyncSession):
    if not is_owner(user.tg_id):
        return await _deny(call)
    from database.models import BankCredit
    from services import cardbridge
    st = cardbridge.STATE
    ok = lambda v: "✅" if v else "❌"  # noqa: E731
    credits = list(await session.scalars(select(BankCredit).order_by(BankCredit.id.desc()).limit(5)))
    pend = await session.scalar(select(func.count()).select_from(TopupOrder).where(
        TopupOrder.status == "pending", TopupOrder.expires_at > topup.utcnow())) or 0
    lines = [
        "🔎 <b>Diagnostika</b>", "",
        f"{ok(settings.tg_api_id)} TG_API_ID · {ok(settings.tg_api_hash)} TG_API_HASH · {ok(settings.tg_session)} TG_SESSION",
        f"Manba: {', '.join('@' + x for x in settings.card_source_list) or '—'}",
        f"{ok(st['connected'])} Ko'prik: " + ("ulangan" if st["connected"] else "ULANMAGAN"),
        f"Ulangan vaqt: {topup.to_tashkent(st['connected_at'])}",
        f"Kelgan xabarlar: {st['events']} · oxirgisi: {topup.to_tashkent(st['last_event'])} ({html.escape(st['last_kind'] or '—')})",
    ]
    if st["last_error"]:
        lines.append(f"⚠️ Oxirgi xato: {html.escape(st['last_error'])}")
    if not settings.tg_session:
        lines.append("\n➡️ TG_SESSION Render Environment'da yo'q — ko'prik ishga tushmaydi.")
    elif not st["connected"] and st["started"] is not None:
        lines.append("\n➡️ Ko'prik ulanmagan: TG_API_ID/HASH/SESSION to'g'riligini va Render Logs'ni tekshiring.")
    elif st["started"] is None:
        lines.append("\n➡️ Ko'prik hali ishga tushmagan (bot yangi ishga tushdi, 10–20 soniya kuting).")
    lines += ["", f"{ok(runtime.autoconfirm_enabled())} Avto-tasdiq · ⏳ faol buyurtmalar: {pend}",
              f"{ok(paynotify.card_enabled())} Karta kiritilgan"]
    if credits:
        lines += ["", "🧾 Oxirgi kirimlar:"] + [
            f"• {topup.to_tashkent(c.received_at)} · {money(c.amount)} · {c.status}" for c in credits]
    await call.message.edit_text("\n".join(lines), reply_markup=_kb([[("🔄 Yangilash", "pay:adm_diag")], [("⬅️ Orqaga", "a:pay")]]))
    await call.answer()


@router.callback_query(F.data == "pay:adm_parse")
async def adm_parse(call: CallbackQuery, user: User, state: FSMContext):
    if not is_owner(user.tg_id):
        return await _deny(call)
    await state.set_state(AdminPay.parse)
    await call.message.edit_text("🧪 CardXabarBot (yoki bank) xabarini shu yerga <b>nusxalab yuboring</b> — kirim yoki chiqim deb "
                                 "tushunilishini va qaysi buyurtmaga mosligini ko'rsataman (hech narsa tasdiqlanmaydi).",
                                 reply_markup=_kb([[("⬅️ Orqaga", "a:pay")]]))
    await call.answer()


@router.message(AdminPay.parse)
async def adm_parse_do(message: Message, user: User, session: AsyncSession):
    if not is_owner(user.tg_id):
        return
    p = topup.parse_credit(message.text or "")
    rows: list[list[tuple[str, str]]] = []
    if p.kind == "credit":
        orders = list(await session.scalars(select(TopupOrder).where(
            TopupOrder.payment_amount == p.amount,
            TopupOrder.status.in_(["pending", "expired"]),
            TopupOrder.expires_at >= topup.utcnow() - timedelta(hours=24))))
        for o in orders:
            rows.append([(f"✅ Tasdiqlash #{o.id}" + (" (kech)" if o.status == "expired" else ""), f"pay:adm_ok:{o.id}")])
        match = ("Mos buyurtma: " + ", ".join(f"#{o.id} ({o.status})" for o in orders)) if orders else "Mos buyurtma yo'q."
        text = "✅ <b>KIRIM</b>: " + money(p.amount) + "\n" + match
    elif p.kind == "debit":
        text = f"➖ <b>CHIQIM</b> ({html.escape(p.reason)}) — to'lov hisoblanmaydi."
    else:
        text = f"❓ <b>Tushunilmadi</b> ({html.escape(p.reason)}). Xabar matnini menga yuboring, formatni moslab beraman."
    rows.append([("⬅️ Orqaga", "a:pay")])
    await message.answer(text, reply_markup=_kb(rows))


@router.message(Command("zaxira"))
async def cmd_backup(message: Message, user: User):
    """Owner: bazaning zaxirasini hoziroq yuboradi (pinlangan xabar yangilanadi)."""
    if not is_owner(user.tg_id):
        return
    from services import backup
    res = await backup.backup_now(message.bot, force=True)
    await message.answer({"ok": "✅ Zaxira yangilandi (shu chatda pinlangan fayl).", "empty": "ℹ️ Baza bo'sh — zaxira yozilmadi.",
                          "error": f"⚠️ Zaxira yuborilmadi ({backup.STATE['last_error']})."}.get(res, "ℹ️ O'zgarish yo'q."))
