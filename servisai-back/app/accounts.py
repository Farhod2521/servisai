"""Google va Telegram orqali kelgan foydalanuvchilarni yaratish/yangilash."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import User
from .referrals import on_signup


class AccountConflict(Exception):
    pass


def is_configured_admin(user: User) -> bool:
    """Admin huquqi faqat .env dagi ADMIN_TELEGRAM_IDS / ADMIN_EMAILS ro‘yxati bilan belgilanadi."""
    return bool(
        (user.telegram_id and user.telegram_id in settings.admin_telegram_id_list)
        or (user.email and user.email.lower() in settings.admin_email_list)
    )


def _apply_admin(user: User) -> None:
    user.is_admin = is_configured_admin(user)


async def upsert_google_user(
    session: AsyncSession,
    *,
    google_id: str,
    email: str | None,
    name: str,
    picture: str | None,
    link_to: User | None = None,
    ref_code: str | None = None,
) -> User:
    user = await session.scalar(select(User).where(User.google_id == google_id))

    if link_to is not None:
        if user is not None and user.id != link_to.id:
            raise AccountConflict("Bu Google hisobi boshqa profilga ulangan")
        user = link_to
    elif user is None and email:
        # Shu email bilan avval ro‘yxatdan o‘tgan bo‘lsa, Google’ni o‘sha profilga bog‘laymiz
        user = await session.scalar(select(User).where(User.email == email))

    created = user is None
    if user is None:
        user = User(full_name=name)
        session.add(user)

    user.google_id = google_id
    if email and user.email is None:
        taken = await session.scalar(select(User.id).where(User.email == email))
        if taken is None:
            user.email = email
    if not user.full_name:
        user.full_name = name
    if picture and not user.avatar_url:
        user.avatar_url = picture
    user.last_login_at = datetime.now(timezone.utc)
    _apply_admin(user)
    await session.flush()
    if created:
        # Taklif havolasi orqali kelgan bo‘lsa; xabarlar commit’dan keyin notify_referral(user) bilan yuboriladi
        await on_signup(session, user, ref_code)
    return user


async def upsert_telegram_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    first_name: str,
    last_name: str | None,
    username: str | None,
    link_to: User | None = None,
    ref_code: str | None = None,
) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    name = " ".join(p for p in (first_name, last_name) if p).strip() or (username or "Foydalanuvchi")

    if link_to is not None:
        if user is not None and user.id != link_to.id:
            raise AccountConflict("Bu Telegram hisobi boshqa profilga ulangan")
        user = link_to

    created = user is None
    if user is None:
        user = User(full_name=name)
        session.add(user)

    user.telegram_id = telegram_id
    user.telegram_username = username
    if not user.full_name:
        user.full_name = name
    user.last_login_at = datetime.now(timezone.utc)
    _apply_admin(user)
    await session.flush()
    if created:
        # Taklif havolasi orqali kelgan bo‘lsa; xabarlar commit’dan keyin notify_referral(user) bilan yuboriladi
        await on_signup(session, user, ref_code)
    return user
