"""Takliflar: foydalanuvchi qaysi servis kerakligini yozadi, admin javob beradi (javob Telegramga ham boradi)."""

import html
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, select, update

from ..config import settings
from ..deps import AdminUser, CurrentUser, SessionDep
from ..models import Suggestion, User
from ..notify import send_message, user_contact
from ..schemas import AdminSuggestionOut, SuggestionIn, SuggestionOut, SuggestionReply

router = APIRouter(prefix="/suggestions", tags=["suggestions"])
admin_router = APIRouter(prefix="/admin/suggestions", tags=["admin"])

# Spamdan himoya: bir foydalanuvchi bir kunda shuncha taklif yubora oladi
DAILY_LIMIT = 5


async def _notify_admin(suggestion: Suggestion, user: User) -> None:
    await send_message(
        settings.telegram_admin_chat_id,
        f"💡 <b>Yangi taklif</b> #{suggestion.id}\n\n{html.escape(suggestion.text)}\n\n"
        f"Mijoz: {user_contact(user)}\nJavob berish: admin panel → Takliflar",
    )


async def _notify_reply(suggestion: Suggestion, user: User) -> None:
    if user.telegram_id:
        await send_message(
            user.telegram_id,
            "💬 <b>Taklifingizga javob keldi!</b>\n\n"
            f"<i>Sizning taklifingiz:</i>\n{html.escape(suggestion.text)}\n\n"
            f"<b>Javob:</b>\n{html.escape(suggestion.reply or '')}",
        )


@router.post("", response_model=SuggestionOut, status_code=status.HTTP_201_CREATED)
async def create_suggestion(data: SuggestionIn, user: CurrentUser, session: SessionDep, background: BackgroundTasks):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    today = await session.scalar(
        select(func.count(Suggestion.id)).where(Suggestion.user_id == user.id, Suggestion.created_at >= since)
    )
    if today >= DAILY_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Bugun yetarlicha taklif yubordingiz, ertaga yana yozing 🙂")
    suggestion = Suggestion(user_id=user.id, text=data.text)
    session.add(suggestion)
    await session.commit()
    await session.refresh(suggestion)
    background.add_task(_notify_admin, suggestion, user)
    return suggestion


@router.get("/me", response_model=list[SuggestionOut])
async def my_suggestions(user: CurrentUser, session: SessionDep):
    return (
        await session.scalars(
            select(Suggestion).where(Suggestion.user_id == user.id).order_by(Suggestion.created_at.desc()).limit(50)
        )
    ).all()


@router.post("/me/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_replies_seen(user: CurrentUser, session: SessionDep):
    await session.execute(
        update(Suggestion)
        .where(Suggestion.user_id == user.id, Suggestion.reply.is_not(None), Suggestion.reply_seen.is_(False))
        .values(reply_seen=True)
    )
    await session.commit()


# ---------- Admin ----------


@admin_router.get("", response_model=list[AdminSuggestionOut])
async def admin_list(
    _: AdminUser,
    session: SessionDep,
    state: str = Query(default="new", pattern="^(new|answered|all)$"),
    limit: int = Query(default=100, ge=1, le=200),
):
    query = select(Suggestion, User).join(User, User.id == Suggestion.user_id)
    if state == "new":
        query = query.where(Suggestion.reply.is_(None))
    elif state == "answered":
        query = query.where(Suggestion.reply.is_not(None))
    rows = await session.execute(query.order_by(Suggestion.created_at.desc()).limit(limit))
    return [
        AdminSuggestionOut(
            **SuggestionOut.model_validate(s).model_dump(),
            user_id=u.id,
            user_name=u.full_name or "—",
            user_telegram_username=u.telegram_username,
            replied_by=s.replied_by,
        )
        for s, u in rows
    ]


@admin_router.post("/{suggestion_id}/reply", response_model=AdminSuggestionOut)
async def admin_reply(suggestion_id: int, data: SuggestionReply, admin: AdminUser, session: SessionDep, background: BackgroundTasks):
    suggestion = await session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Taklif topilmadi")
    suggestion.reply = data.text
    suggestion.replied_by = admin.full_name or (f"@{admin.telegram_username}" if admin.telegram_username else "Admin")
    suggestion.replied_at = datetime.now(timezone.utc)
    suggestion.reply_seen = False
    await session.commit()
    await session.refresh(suggestion)
    user = await session.get(User, suggestion.user_id)
    background.add_task(_notify_reply, suggestion, user)
    return AdminSuggestionOut(
        **SuggestionOut.model_validate(suggestion).model_dump(),
        user_id=user.id,
        user_name=user.full_name or "—",
        user_telegram_username=user.telegram_username,
        replied_by=suggestion.replied_by,
    )
