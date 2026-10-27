"""Hisobni to‘ldirish so‘rovi (chek bilan): sayt API va Telegram bot shu yerdan foydalanadi."""

import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import TopUp, TopUpStatus, User
from .notify import format_price, send_topup_to_admin

RECEIPT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
MAX_RECEIPT_SIZE = 10 * 1024 * 1024
MAX_PENDING = 3


class TopUpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def topup_enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_admin_chat_id)


def check_amount(amount: int) -> None:
    if not settings.topup_min_amount <= amount <= settings.topup_max_amount:
        raise TopUpError(
            422,
            f"Summa {format_price(settings.topup_min_amount)} – {format_price(settings.topup_max_amount)} so‘m oralig‘ida bo‘lishi kerak",
        )


async def submit_topup(session: AsyncSession, user: User, amount: int, content: bytes, content_type: str | None) -> TopUp:
    """Chekni saqlaydi va admin chatiga «Tasdiqlash / Rad etish» tugmalari bilan yuboradi. Commit shu yerda."""
    if not topup_enabled():
        raise TopUpError(503, "Hisobni to‘ldirish hozircha sozlanmagan")
    check_amount(amount)
    ext = RECEIPT_TYPES.get(content_type or "")
    if ext is None:
        raise TopUpError(422, "Chek JPG, PNG, WEBP rasm yoki PDF bo‘lishi kerak")
    if len(content) > MAX_RECEIPT_SIZE:
        raise TopUpError(413, "Chek hajmi 10 MB dan oshmasligi kerak")
    if not content:
        raise TopUpError(422, "Chek fayli bo‘sh")

    pending = await session.scalar(
        select(func.count(TopUp.id)).where(TopUp.user_id == user.id, TopUp.status == TopUpStatus.pending)
    )
    if pending >= MAX_PENDING:
        raise TopUpError(429, "Avvalgi so‘rovlaringiz hali tekshirilmoqda, biroz kuting")

    folder = Path(settings.media_dir) / "receipts"
    folder.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.{ext}"
    path = folder / file_name
    path.write_bytes(content)

    topup = TopUp(user_id=user.id, amount=amount, receipt_path=str(path))
    session.add(topup)
    await session.flush()

    if not await send_topup_to_admin(topup, user, file_name, content, content_type):
        await session.rollback()
        path.unlink(missing_ok=True)
        raise TopUpError(502, "Chekni yuborib bo‘lmadi, birozdan so‘ng qayta urinib ko‘ring")

    await session.commit()
    return topup
