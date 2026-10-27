import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from ..accounts import AccountConflict, upsert_google_user
from ..config import settings
from ..deps import CurrentUser, OptionalUser, SessionDep
from ..models import TelegramLoginSession, TelegramLoginStatus, User
from ..referrals import normalize_code, notify_referral
from ..schemas import (
    AuthConfigOut,
    GoogleLoginIn,
    TelegramInitOut,
    TelegramStatusOut,
    TokenOut,
    UserOut,
)
from ..security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

_google_request = google_requests.Request()


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/config", response_model=AuthConfigOut)
async def auth_config():
    """Frontend qaysi kirish usullarini ko‘rsatishini shu yerdan biladi."""
    return AuthConfigOut(
        google_client_id=settings.google_client_id or None,
        telegram_bot_username=(settings.telegram_bot_username or None) if settings.telegram_bot_token else None,
    )


async def _verify_google(credential: str) -> dict:
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google orqali kirish sozlanmagan")
    try:
        info = await run_in_threadpool(
            id_token.verify_oauth2_token, credential, _google_request, settings.google_client_id
        )
    except (ValueError, GoogleAuthError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google tokeni yaroqsiz")
    if info.get("email") and not info.get("email_verified"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google email manzili tasdiqlanmagan")
    return info


@router.post("/google", response_model=TokenOut)
async def google_login(data: GoogleLoginIn, session: SessionDep, background: BackgroundTasks):
    info = await _verify_google(data.credential)
    user = await upsert_google_user(
        session,
        google_id=info["sub"],
        email=info.get("email"),
        name=info.get("name") or info.get("email", "").split("@")[0],
        picture=info.get("picture"),
        ref_code=data.ref,
    )
    await session.commit()
    background.add_task(notify_referral, user)
    return _token_response(user)


@router.post("/google/link", response_model=UserOut)
async def google_link(data: GoogleLoginIn, session: SessionDep, user: CurrentUser):
    """Tizimga kirgan foydalanuvchi profiliga Google hisobini ulash."""
    info = await _verify_google(data.credential)
    try:
        user = await upsert_google_user(
            session,
            google_id=info["sub"],
            email=info.get("email"),
            name=info.get("name") or "",
            picture=info.get("picture"),
            link_to=user,
        )
    except AccountConflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    await session.commit()
    return user


@router.post("/telegram/init", response_model=TelegramInitOut)
async def telegram_init(session: SessionDep, user: OptionalUser, ref: str | None = Query(default=None, max_length=32)):
    """Bir martalik token yaratadi. Foydalanuvchi botga /start <token> yuborganda kirish tasdiqlanadi.

    Agar so‘rov token bilan kelsa (foydalanuvchi allaqachon tizimda), Telegram uning profiliga ulanadi.
    """
    if not settings.telegram_bot_token or not settings.telegram_bot_username:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram orqali kirish sozlanmagan")
    token = secrets.token_urlsafe(24)
    session.add(
        TelegramLoginSession(
            token=token,
            link_user_id=user.id if user else None,
            ref_code=normalize_code(ref),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.telegram_login_ttl),
        )
    )
    await session.commit()
    return TelegramInitOut(
        token=token,
        bot_url=f"https://t.me/{settings.telegram_bot_username}?start={token}",
        expires_in=settings.telegram_login_ttl,
    )


@router.get("/telegram/status/{token}", response_model=TelegramStatusOut)
async def telegram_status(token: str, session: SessionDep):
    login = await session.get(TelegramLoginSession, token, with_for_update=True)
    if login is None or login.status == TelegramLoginStatus.used:
        return TelegramStatusOut(status="expired", detail="Havola eskirgan, qaytadan urinib ko‘ring")
    if login.error:
        return TelegramStatusOut(status="error", detail=login.error)
    if login.status == TelegramLoginStatus.pending:
        if login.expires_at < datetime.now(timezone.utc):
            return TelegramStatusOut(status="expired", detail="Havola muddati tugadi, qaytadan urinib ko‘ring")
        return TelegramStatusOut(status="pending")

    user = await session.get(User, login.user_id)
    login.status = TelegramLoginStatus.used
    await session.commit()
    if user is None:
        return TelegramStatusOut(status="error", detail="Foydalanuvchi topilmadi")
    tok = _token_response(user)
    return TelegramStatusOut(status="confirmed", access_token=tok.access_token, user=tok.user)
