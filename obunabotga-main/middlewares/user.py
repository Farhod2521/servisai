"""Har bir yangilanish uchun baza sessiyasi va foydalanuvchini biriktiradi."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database.db import SessionMaker
from services.repo import get_or_create_user


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        async with SessionMaker() as session:
            data["session"] = session
            if tg_user and not tg_user.is_bot:
                user = await get_or_create_user(
                    session, tg_user.id, tg_user.username,
                    tg_user.full_name or "",
                )
                if user.is_banned:
                    if isinstance(event, Message):
                        await event.answer("🚫 Siz bloklangansiz.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 Siz bloklangansiz.", show_alert=True)
                    return None
                data["user"] = user
                data["lang"] = user.lang
            else:
                data["lang"] = "uz"
            return await handler(event, data)
