from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..config import settings
from ..deps import AdminUser, CurrentUser, SessionDep
from ..models import TopUp, TopUpStatus, Transaction, User
from ..notify import notify_topup_result
from ..schemas import AdminTopUpOut, TopUpOut, TopUpReview, TransactionOut, WalletOut
from ..topups import MAX_RECEIPT_SIZE, TopUpError, submit_topup, topup_enabled
from ..wallet import TopUpAlreadyReviewed, review_topup

router = APIRouter(prefix="/wallet", tags=["wallet"])
admin_router = APIRouter(prefix="/admin/topups", tags=["admin"])

@router.get("", response_model=WalletOut)
async def wallet(user: CurrentUser):
    return WalletOut(
        balance=user.balance,
        card_number=settings.payment_card_number or None,
        card_holder=settings.payment_card_holder or None,
        min_amount=settings.topup_min_amount,
        max_amount=settings.topup_max_amount,
        topup_enabled=topup_enabled(),
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
    content = await receipt.read(MAX_RECEIPT_SIZE + 1)
    try:
        return await submit_topup(session, user, amount, content, receipt.content_type)
    except TopUpError as e:
        raise HTTPException(e.status, e.message)


RECEIPT_MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf"}


@admin_router.get("", response_model=list[AdminTopUpOut])
async def admin_list(
    _: AdminUser,
    session: SessionDep,
    state: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(default=100, ge=1, le=200),
):
    """Saytdan ham, botdan ham yuborilgan hisob to‘ldirish so‘rovlari."""
    query = select(TopUp, User).join(User, User.id == TopUp.user_id)
    if state != "all":
        query = query.where(TopUp.status == TopUpStatus(state))
    rows = await session.execute(query.order_by(TopUp.created_at.desc(), TopUp.id.desc()).limit(limit))
    return [
        AdminTopUpOut(
            **TopUpOut.model_validate(t).model_dump(),
            user_id=u.id,
            user_name=u.full_name or "—",
            user_telegram_username=u.telegram_username,
            user_balance=u.balance,
            reviewed_by=t.reviewed_by,
            receipt_type=RECEIPT_MEDIA_TYPES.get(Path(t.receipt_path).suffix.lower(), "application/octet-stream"),
        )
        for t, u in rows
    ]


@admin_router.get("/{topup_id}/receipt")
async def admin_receipt(topup_id: int, _: AdminUser, session: SessionDep):
    """Chek fayli — faqat adminga (ommaviy havola yo‘q)."""
    topup = await session.get(TopUp, topup_id)
    if topup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "So‘rov topilmadi")
    root = (Path(settings.media_dir) / "receipts").resolve()
    path = Path(topup.receipt_path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chek fayli topilmadi")
    return FileResponse(path, media_type=RECEIPT_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"))


@admin_router.post("/{topup_id}", response_model=TopUpOut)
async def admin_review(topup_id: int, data: TopUpReview, admin: AdminUser, session: SessionDep, background: BackgroundTasks):
    """Saytdan (API) tasdiqlash/rad etish — odatda bu Telegram’dagi tugmalar orqali qilinadi."""
    try:
        reviewer = admin.full_name or (f"@{admin.telegram_username}" if admin.telegram_username else f"admin #{admin.id}")
        topup = await review_topup(session, topup_id, approve=data.approve, reviewer=f"{reviewer} (sayt)", note=data.note)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "So‘rov topilmadi")
    except TopUpAlreadyReviewed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu so‘rov allaqachon ko‘rib chiqilgan")
    await session.commit()
    owner = await session.get(User, topup.user_id)
    background.add_task(notify_topup_result, topup, owner)
    return topup
