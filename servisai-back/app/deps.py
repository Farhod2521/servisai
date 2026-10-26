from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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
    return user


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tizimga kirish talab qilinadi")
    return user


async def get_admin_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Faqat administratorlar uchun")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
