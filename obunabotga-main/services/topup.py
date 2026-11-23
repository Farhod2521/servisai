"""Avtomatik to'lov yadrosi: noyob summali buyurtmalar, kirim xabarini tahlil qilish va atomar tasdiqlash.

Hamyon to'ldirish oqimi (karta / Payme / Click / SMS — hammasi shu yerdagi `confirm_order` ga keladi):
  1. Mijoz summa tanlaydi (baseAmount) → `create_order` unga kichik noyob qo'shimcha qo'shadi (paymentAmount, ~1%: 1 000 → 1001–1100);
  2. buyurtma 30 daqiqa amal qiladi;
  3. kirim xabari (CardXabarBot / SMS) summasi bitta faol buyurtmaga aniq mos kelsa → `confirm_order`;
  4. `confirm_order` BIR MARTA hamyonga paymentAmount ni qo'shadi (idempotent, bir nechta server bo'lsa ham).

Barcha vaqtlar bazada UTC (naive). Mijozga Asia/Tashkent (UTC+5) ko'rinishida ko'rsatiladi.
"""
from __future__ import annotations

import logging
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    BankCredit, Payment, PaymentLog, PaymentStatus, TopupOrder, User,
)

log = logging.getLogger("uzshop.topup")

ORDER_TTL = timedelta(minutes=30)
EXTRA_MIN, EXTRA_MAX = 1, 999


def extra_limit(base: int) -> int:
    """Noyob qo'shimcha yuqori chegarasi — adolatli: ~1% (kamida 100, ko'pi bilan 999 so'm).

    1 000 → 1001–1100; 20 000 → 20 001–20 200; 50 000 → 50 001–50 500; 100 000 va undan ko'p → 1–999.
    """
    return min(EXTRA_MAX, max(100, round(base * 0.01 / 10) * 10))
MAX_PENDING_PER_USER = 3
MIN_AMOUNT, MAX_AMOUNT = 1_000, 50_000_000
TASHKENT = timezone(timedelta(hours=5))


def utcnow() -> datetime:
    return datetime.utcnow()


def to_tashkent(dt: datetime | None) -> str:
    """UTC (naive) → «05.10.2026 18:30» (Asia/Tashkent)."""
    if not dt:
        return "—"
    return dt.replace(tzinfo=timezone.utc).astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M")


def to_tashkent_time(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.replace(tzinfo=timezone.utc).astimezone(TASHKENT).strftime("%H:%M")


async def log_event(s: AsyncSession, order_id: int | None, event: str, provider: str | None = None, detail: str = "") -> None:
    s.add(PaymentLog(order_id=order_id, event=event, provider=provider, detail=detail[:250]))


# ─────────────────────────── Buyurtma yaratish ───────────────────────────

class OrderError(Exception):
    """Mijozga ko'rsatiladigan xato (o'zbekcha)."""


async def sweep_expired(s: AsyncSession) -> int:
    """Muddati o'tgan pending buyurtmalarni expired qiladi (noyob summa bo'shaydi)."""
    res = await s.execute(
        update(TopupOrder).where(TopupOrder.status == "pending", TopupOrder.expires_at <= utcnow())
        .values(status="expired")
    )
    await s.commit()
    return res.rowcount or 0


async def create_order(
    s: AsyncSession, user: User, base_amount: int, provider: str = "card", chat_id: int | None = None
) -> TopupOrder:
    if not MIN_AMOUNT <= base_amount <= MAX_AMOUNT:
        raise OrderError(f"Summa {MIN_AMOUNT:,} dan {MAX_AMOUNT:,} so'mgacha bo'lishi kerak.".replace(",", " "))
    await sweep_expired(s)
    pending = await s.scalar(select(func.count()).select_from(TopupOrder).where(
        TopupOrder.user_id == user.id, TopupOrder.status == "pending")) or 0
    if pending >= MAX_PENDING_PER_USER:
        raise OrderError("Sizda ochiq to'lov buyurtmalari ko'p. Avval birini bekor qiling yoki muddati tugashini kuting.")

    for _ in range(8):      # poyga holatida (ikki mijoz bir vaqtda) bazaning unique indeksi to'xtatadi — qayta urinamiz
        used = set(await s.scalars(select(TopupOrder.payment_amount).where(
            TopupOrder.status == "pending",
            TopupOrder.payment_amount.between(base_amount + EXTRA_MIN, base_amount + extra_limit(base_amount)))))
        free = [base_amount + x for x in range(EXTRA_MIN, extra_limit(base_amount) + 1) if base_amount + x not in used]
        if not free:
            raise OrderError("Hozir bu summa band, boshqa summa tanlang.")
        now = utcnow()
        order = TopupOrder(
            user_id=user.id, telegram_chat_id=chat_id or user.tg_id, username=user.username,
            base_amount=base_amount, payment_amount=random.choice(free), provider=provider,
            created_at=now, expires_at=now + ORDER_TTL,
        )
        s.add(order)
        try:
            await s.flush()
            await log_event(s, order.id, "created", provider, f"{order.payment_amount}")
            await s.commit()
            return order
        except IntegrityError:
            await s.rollback()
    raise OrderError("Hozir buyurtma yaratib bo'lmadi. Birozdan so'ng urinib ko'ring.")


async def get_order(s: AsyncSession, order_id: int) -> TopupOrder | None:
    return await s.get(TopupOrder, order_id, populate_existing=True)


def is_active(order: TopupOrder) -> bool:
    return order.status == "pending" and order.expires_at > utcnow()


async def cancel_order(s: AsyncSession, order_id: int, user_id: int | None = None) -> bool:
    """Pending buyurtmani bekor qiladi (user_id berilsa — faqat uniki)."""
    conds = [TopupOrder.id == order_id, TopupOrder.status == "pending"]
    if user_id is not None:
        conds.append(TopupOrder.user_id == user_id)
    res = await s.execute(update(TopupOrder).where(*conds).values(status="cancelled"))
    if res.rowcount:
        await log_event(s, order_id, "cancelled")
    await s.commit()
    return bool(res.rowcount)


# ─────────────────────────── Tasdiqlash (atomar, idempotent) ───────────────────────────

@dataclass
class ConfirmResult:
    status: str            # ok | already_paid | expired | cancelled | not_found | duplicate_txn
    order: TopupOrder | None = None
    balance: int | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


async def confirm_order(
    s: AsyncSession, order_id: int, provider: str, provider_txn_id: str | None, *, force: bool = False
) -> ConfirmResult:
    """Buyurtmani to'langan qiladi va hamyonga paymentAmount ni BIR MARTA qo'shadi.

    Atomarlik: holat o'tishi bitta shartli `UPDATE ... WHERE status='pending' AND expires_at>now` — bir vaqtda
    ikki chaqiruv (yoki ikki server) bo'lsa faqat bittasi `rowcount=1` oladi. provider_txn_id unique indeks bilan
    himoyalangan. `force=True` — faqat admin qo'lda tasdiqlaganda (muddati o'tgan buyurtmani ham).
    """
    now = utcnow()
    order = await get_order(s, order_id)
    if not order:
        return ConfirmResult("not_found")
    if order.status == "paid":
        return ConfirmResult("already_paid", order)
    if order.status == "cancelled":
        return ConfirmResult("cancelled", order)
    if not force and (order.status == "expired" or order.expires_at <= now):
        await log_event(s, order.id, "late_payment", provider, "muddati tugagan")
        await s.commit()
        return ConfirmResult("expired", order)
    if provider_txn_id:
        dup = await s.scalar(select(TopupOrder.id).where(
            TopupOrder.provider == provider, TopupOrder.provider_txn_id == provider_txn_id))
        if dup is not None:
            return ConfirmResult("duplicate_txn", order)

    allowed = ["pending", "expired"] if force else ["pending"]
    conds = [TopupOrder.id == order.id, TopupOrder.status.in_(allowed)]
    if not force:
        conds.append(TopupOrder.expires_at > now)
    try:
        res = await s.execute(update(TopupOrder).where(*conds).values(
            status="paid", paid_at=now, provider=provider, provider_txn_id=provider_txn_id))
        if res.rowcount != 1:                      # boshqa chaqiruv oldinroq ulgurdi
            await s.rollback()
            fresh = await get_order(s, order_id)
            return ConfirmResult("already_paid" if fresh and fresh.status == "paid" else
                                 (fresh.status if fresh and fresh.status in ("cancelled", "expired") else "expired"), fresh)
        await s.execute(update(User).where(User.id == order.user_id).values(balance=User.balance + order.payment_amount))
        s.add(Payment(user_id=order.user_id, amount=order.payment_amount, provider=provider,
                      external_id=(provider_txn_id or f"order-{order.id}")[:128],
                      status=PaymentStatus.PAID, paid_at=now))
        await log_event(s, order.id, "paid", provider, f"{order.payment_amount} · txn {provider_txn_id or '-'}")
        await s.commit()
        from services import backup
        backup.mark_dirty(critical=True)           # hisob to'ldirildi — zaxira darhol yangilanadi
    except IntegrityError:
        await s.rollback()
        return ConfirmResult("duplicate_txn", await get_order(s, order_id))
    fresh = await get_order(s, order_id)
    user = await s.get(User, order.user_id, populate_existing=True)
    return ConfirmResult("ok", fresh, user.balance if user else None)


async def reverse_order(s: AsyncSession, order_id: int) -> bool:
    """Payme CancelTransaction (to'langan buyurtma): hamyondan qaytarib olinadi — faqat mablag' yetarli bo'lsa."""
    order = await get_order(s, order_id)
    if not order or order.status != "paid":
        return False
    res = await s.execute(update(User).where(User.id == order.user_id, User.balance >= order.payment_amount)
                          .values(balance=User.balance - order.payment_amount))
    if res.rowcount != 1:
        await s.rollback()
        return False
    await s.execute(update(TopupOrder).where(TopupOrder.id == order.id, TopupOrder.status == "paid").values(status="cancelled"))
    await log_event(s, order.id, "reversed", order.provider, str(order.payment_amount))
    await s.commit()
    from services import backup
    backup.mark_dirty(critical=True)
    return True


# ─────────────────────────── Kirim xabarini tahlil qilish ───────────────────────────

_DEBIT = re.compile(
    r"➖|оплата|оплач|yechildi|yechib|yechilib|yechish|xarid|purchase|withdraw|списани|снят|снятие|chiqim|"
    r"расход|debit|spisan|oplata|to['’‘`ʻ]?lov qildingiz|payment for|buy\b|sotib olindi", re.I)
_CREDIT = re.compile(
    r"➕|пополнени|popolnen|kirim|tushdi|tushum|поступлени|зачислени|credit|received|kartangizga|"
    r"to['’‘`ʻ]?ldirildi|to['’‘`ʻ]?ldirish|incoming|deposit|получен", re.I)
_BALANCE_EMOJI = re.compile(r"[💰💵💲]")
_BALANCE_CTX = re.compile(r"баланс|balans|qoldiq|остаток|balance|доступно|mavjud|available|limit", re.I)
_CUR = r"(?:uzs|сум|сўм|so['’‘`ʻ]?m|som|sum)"
_NUM = r"\d{1,3}(?:[  .,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_AMOUNT = re.compile(
    rf"(?P<sign>[+\-−–➕➖]?)\s*(?P<num>{_NUM})\s*(?P<cur>{_CUR})?(?![\w])", re.I)


@dataclass
class Parsed:
    kind: str                 # credit | debit | unknown
    amount: int | None = None
    reason: str = ""


def _num_to_int(num: str) -> tuple[int, bool]:
    """«49 437.00» → (49437, True); kasr qismi nol bo'lmasa (…​.50) — butun emas → ikkinchi qiymat False."""
    n = num.replace(" ", " ").strip()
    m = re.search(r"[.,](\d{1,2})$", n)
    frac_ok = True
    if m and not re.fullmatch(r"\d{1,3}[.,]\d{3}", n):          # «49.437» — minglik ajratgich, kasr emas
        frac_ok = set(m.group(1)) <= {"0"}
        n = n[:m.start()]
    digits = re.sub(r"[ .,]", "", n)
    return (int(digits) if digits else 0), frac_ok


def parse_credit(text: str) -> Parsed:
    """Xabar hamyonga KIRIM ekanini va summasini aniqlaydi. Chiqim / noaniq xabar hech qachon credit bo'lmaydi.

    Bir xabarda bir nechta summa bo'lishi mumkin (kirim + qoldiq, masalan «➕ 1 068.00 UZS … 💵 1 020 074.01 UZS»):
    ishorali (+ / ➕) yoki «Пополнение/kirim» so'zi yonidagi summa kirim; qoldiq (баланс, 💵/💰) hisobga olinmaydi.
    """
    t = unicodedata.normalize("NFKC", text or "").replace("\u00a0", " ")
    if not t.strip():
        return Parsed("unknown", reason="bo'sh")
    if _DEBIT.search(t):
        return Parsed("debit", reason="chiqim so'zi")
    cands: list[tuple[int, bool, bool]] = []          # (summa, kasrsiz, kirim belgisi bor)
    emoji_only: list[tuple[int, bool, bool]] = []     # 💰/💵 belgisi oldidagi summalar: qoldiq bo'lishi ham, HUMO «To'ldirish 💰 1.063,00 UZS» kirimi ham mumkin
    for m in _AMOUNT.finditer(t):
        sign, cur = m.group("sign"), m.group("cur")
        prev = t[m.start() - 1] if m.start() > 0 else " "
        if sign in ("-", "−", "–", "➖") and not prev.isalnum() and (cur or len(re.sub(r"\D", "", m.group("num"))) >= 4):
            return Parsed("debit", reason="manfiy summa")        # «-49 437 UZS»; sana/vaqt («05-10») emas
        signed = sign in ("+", "➕")
        if not cur and not signed:
            continue                                              # valyutasiz oddiy raqam (karta, vaqt, sana) — summa emas
        before = t[max(0, m.start() - 24):m.start()]
        if _BALANCE_CTX.search(before):
            continue                                              # qoldiq («Баланс: …») — kirim emas
        value, frac_ok = _num_to_int(m.group("num"))
        if not signed and _BALANCE_EMOJI.search(before[-3:]):
            emoji_only.append((value, frac_ok, False))
            continue
        cands.append((value, frac_ok, signed or bool(_CREDIT.search(before))))
    if not cands and emoji_only and _CREDIT.search(t) and len({v for v, _, _ in emoji_only}) == 1:
        cands = [(v, f, True) for v, f, _ in emoji_only]          # xabarda «To'ldirish/kirim» so'zi bor va summa bitta — kirim
    if not cands:
        return Parsed("unknown", reason="summa topilmadi")
    marked = [c for c in cands if c[2]]
    pool = marked or cands                                        # ishorali summa bo'lsa — faqat shular
    values = {v for v, _, _ in pool}
    if len(values) > 1:
        return Parsed("unknown", reason="bir nechta summa")
    value = next(iter(values))
    if value <= 0 or not all(f for v, f, _ in pool if v == value):
        return Parsed("unknown", reason="kasr summa")
    return Parsed("credit", value)


# ─────────────────────────── Kirim ↔ buyurtma moslash ───────────────────────────

@dataclass
class Outcome:
    kind: str                       # ignored | duplicate | matched | candidate | late | unmatched | closed
    order: TopupOrder | None = None
    result: ConfirmResult | None = None
    credit: BankCredit | None = None
    candidates: list[TopupOrder] | None = None
    parsed: Parsed | None = None


async def _active_by_amount(s: AsyncSession, amount: int, not_before: datetime | None = None) -> list[TopupOrder]:
    q = select(TopupOrder).where(TopupOrder.status == "pending", TopupOrder.expires_at > utcnow(),
                                 TopupOrder.payment_amount == amount)
    if not_before is not None:
        q = q.where(TopupOrder.created_at <= not_before)
    return list(await s.scalars(q))


async def handle_incoming(s: AsyncSession, source: str, source_msg_id: str, text: str, provider: str = "card") -> Outcome:
    """Bitta kirim xabarini qayta ishlaydi (CardXabarBot yoki SMS). Xabarlarni yuborish chaqiruvchining ishi."""
    parsed = parse_credit(text)
    if parsed.kind != "credit" or not parsed.amount:
        log.info("Kirim emas (%s): %s", source, parsed.reason)
        return Outcome("ignored", parsed=parsed)
    credit = BankCredit(source=source[:64], source_msg_id=str(source_msg_id)[:64], amount=parsed.amount,
                        text=(text or "")[:400], received_at=utcnow())
    s.add(credit)
    try:
        await s.commit()          # avval kirim yoziladi: takroriy xabar (bir xil manba+ID) bu yerda to'xtaydi
    except IntegrityError:
        await s.rollback()
        return Outcome("duplicate", parsed=parsed)
    await sweep_expired_in_tx(s)
    orders = await _active_by_amount(s, parsed.amount)
    from services import runtime
    if len(orders) == 1 and runtime.autoconfirm_enabled():
        txn = f"{source}:{source_msg_id}"
        res = await confirm_order(s, orders[0].id, provider, txn)
        credit = await s.get(BankCredit, credit.id)
        if res.ok:
            credit.status, credit.order_id = "matched", orders[0].id
            await s.commit()
            return Outcome("matched", res.order, res, credit, parsed=parsed)
        await s.commit()
        return Outcome("unmatched", orders[0], res, credit, parsed=parsed)
    if orders:                                       # bir nechta mos yoki avto-tasdiq o'chiq → admin hal qiladi
        credit.status = "candidate"
        await s.commit()
        return Outcome("candidate", credit=credit, candidates=orders, parsed=parsed)
    late = list(await s.scalars(select(TopupOrder).where(
        TopupOrder.payment_amount == parsed.amount, TopupOrder.status == "expired",
        TopupOrder.expires_at >= utcnow() - timedelta(hours=24))))
    if late:                                         # to'lov kech tushdi — avtomatik bermaymiz, admin ko'radi
        credit.status = "candidate"
        await s.commit()
        return Outcome("late", credit=credit, candidates=late, parsed=parsed)
    await s.commit()
    return Outcome("unmatched", credit=credit, parsed=parsed)


async def sweep_expired_in_tx(s: AsyncSession) -> None:
    await s.execute(update(TopupOrder).where(TopupOrder.status == "pending", TopupOrder.expires_at <= utcnow())
                    .values(status="expired"))


async def recheck_order(s: AsyncSession, order: TopupOrder) -> Outcome:
    """«To'lov qildim — tekshirish»: buyurtmadan keyin kelgan, hali hech narsaga bog'lanmagan kirimlarni qayta tekshiradi."""
    if order.status != "pending" or order.expires_at <= utcnow():
        return Outcome("closed", order)
    credits = list(await s.scalars(select(BankCredit).where(
        BankCredit.amount == order.payment_amount, BankCredit.status == "new",
        BankCredit.received_at >= order.created_at)))
    from services import runtime
    if len(credits) == 1 and runtime.autoconfirm_enabled():
        c = credits[0]
        res = await confirm_order(s, order.id, "card", f"{c.source}:{c.source_msg_id}")
        if res.ok:
            c = await s.get(BankCredit, c.id)
            c.status, c.order_id = "matched", order.id
            await s.commit()
            return Outcome("matched", res.order, res, c)
        return Outcome("unmatched", order, res)
    return Outcome("unmatched", order)
