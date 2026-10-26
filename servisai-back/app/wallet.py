"""Hisob (balans) bilan ishlash: to‘ldirish, xarid, qaytarish. Har bir o‘zgarish Transaction sifatida yoziladi."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TopUp, TopUpStatus, Transaction, TransactionType, User


class InsufficientFunds(Exception):
    def __init__(self, balance: int):
        super().__init__(balance)
        self.balance = balance


class TopUpAlreadyReviewed(Exception):
    pass


async def _locked_user(session: AsyncSession, user_id: int) -> User:
    # Bir vaqtda kelgan so‘rovlar balansni buzmasligi uchun qatorni qulflaymiz
    return await session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))


async def change_balance(
    session: AsyncSession,
    user_id: int,
    amount: int,
    type_: TransactionType,
    *,
    note: str | None = None,
    topup_id: int | None = None,
    order_id: int | None = None,
) -> User:
    user = await _locked_user(session, user_id)
    if user.balance + amount < 0:
        raise InsufficientFunds(user.balance)
    user.balance += amount
    session.add(
        Transaction(
            user_id=user.id,
            type=type_,
            amount=amount,
            balance_after=user.balance,
            note=note,
            topup_id=topup_id,
            order_id=order_id,
        )
    )
    return user


async def review_topup(session: AsyncSession, topup_id: int, *, approve: bool, reviewer: str, note: str | None = None) -> TopUp:
    """Adminning qarori. Commit chaqiruvchi tomonda qilinadi."""
    topup = await session.scalar(select(TopUp).where(TopUp.id == topup_id).with_for_update())
    if topup is None:
        raise LookupError("So‘rov topilmadi")
    if topup.status != TopUpStatus.pending:
        raise TopUpAlreadyReviewed
    topup.status = TopUpStatus.approved if approve else TopUpStatus.rejected
    topup.reviewed_by = reviewer
    topup.reviewed_at = datetime.now(timezone.utc)
    topup.admin_note = note
    if approve:
        await change_balance(
            session, topup.user_id, topup.amount, TransactionType.topup, note=f"Hisob to‘ldirildi (#{topup.id})", topup_id=topup.id
        )
    return topup
