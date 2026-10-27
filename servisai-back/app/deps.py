from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .accounts import is_configured_admin
from .database import get_session
from .models import User
from .security import decode_access_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]

bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    session: SessionDep, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User | None:
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token yaroqsiz yoki muddati o‘tgan")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi topilmadi")
    # Admin ro‘yxati (.env) har so‘rovda tekshiriladi: qayta kirish shart emas,
    # ro‘yxatdan olib tashlangan ID esa huquqini darhol yo‘qotadi
    admin = is_configured_admin(user)
    if user.is_admin != admin:
        user.is_admin = admin
        await session.commit()
    return user


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tizimga kirish talab qilinadi")
    return user


async def get_admin_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_configured_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Faqat administratorlar uchun")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
