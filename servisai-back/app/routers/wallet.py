import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from ..config import settings
from ..deps import AdminUser, CurrentUser, SessionDep
from ..models import TopUp, TopUpStatus, Transaction, User
from ..notify import notify_topup_result, send_topup_to_admin
from ..schemas import TopUpOut, TopUpReview, TransactionOut, WalletOut
from ..wallet import TopUpAlreadyReviewed, review_topup

router = APIRouter(prefix="/wallet", tags=["wallet"])
admin_router = APIRouter(prefix="/admin/topups", tags=["admin"])

RECEIPT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
MAX_RECEIPT_SIZE = 10 * 1024 * 1024


def _topup_enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_admin_chat_id)


@router.get("", response_model=WalletOut)
async def wallet(user: CurrentUser):
    return WalletOut(
        balance=user.balance,
        card_number=settings.payment_card_number or None,
        card_holder=settings.payment_card_holder or None,
        min_amount=settings.topup_min_amount,
        max_amount=settings.topup_max_amount,
        topup_enabled=_topup_enabled(),
    )


@router.get("/transactions", response_model=list[TransactionOut])
async def transactions(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return (
        await session.scalars(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()


@router.get("/topups", response_model=list[TopUpOut])
async def topups(user: CurrentUser, session: SessionDep, limit: int = Query(default=20, ge=1, le=100)):
    return (
        await session.scalars(
            select(TopUp).where(TopUp.user_id == user.id).order_by(TopUp.created_at.desc(), TopUp.id.desc()).limit(limit)
        )
    ).all()


@router.post("/topups", response_model=TopUpOut, status_code=status.HTTP_201_CREATED)
async def create_topup(
    user: CurrentUser,
    session: SessionDep,
    amount: int = Form(...),
    receipt: UploadFile = File(...),
):
    """Summa va chek rasmi qabul qilinadi, chek admin Telegram chatiga tasdiqlash tugmalari bilan yuboriladi."""
    if not _topup_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Hisobni to‘ldirish hozircha sozlanmagan")
    if not settings.topup_min_amount <= amount <= settings.topup_max_amount:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Summa {settings.topup_min_amount:,} – {settings.topup_max_amount:,} so‘m oralig‘ida bo‘lishi kerak".replace(",", " "),
        )
    ext = RECEIPT_TYPES.get(receipt.content_type or "")
    if ext is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Chek JPG, PNG, WEBP rasm yoki PDF bo‘lishi kerak")
    content = await receipt.read(MAX_RECEIPT_SIZE + 1)
    if len(content) > MAX_RECEIPT_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Chek hajmi 10 MB dan oshmasligi kerak")
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Chek fayli bo‘sh")

    pending = (
        await session.scalars(select(TopUp.id).where(TopUp.user_id == user.id, TopUp.status == TopUpStatus.pending))
    ).all()
    if len(pending) >= 3:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Avvalgi so‘rovlaringiz hali tekshirilmoqda, biroz kuting")

    folder = Path(settings.media_dir) / "receipts"
    folder.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.{ext}"
    path = folder / file_name
    path.write_bytes(content)

    topup = TopUp(user_id=user.id, amount=amount, receipt_path=str(path))
    session.add(topup)
    await session.flush()

    if not await send_topup_to_admin(topup, user, file_name, content, receipt.content_type):
        await session.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Chekni yuborib bo‘lmadi, birozdan so‘ng qayta urinib ko‘ring")

    await session.commit()
    return topup


@admin_router.post("/{topup_id}", response_model=TopUpOut)
async def admin_review(topup_id: int, data: TopUpReview, admin: AdminUser, session: SessionDep, background: BackgroundTasks):
    """Saytdan (API) tasdiqlash/rad etish — odatda bu Telegram’dagi tugmalar orqali qilinadi."""
    try:
        topup = await review_topup(session, topup_id, approve=data.approve, reviewer=f"web:{admin.id}", note=data.note)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "So‘rov topilmadi")
    except TopUpAlreadyReviewed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu so‘rov allaqachon ko‘rib chiqilgan")
    await session.commit()
    owner = await session.get(User, topup.user_id)
    background.add_task(notify_topup_result, topup, owner)
    return topup
