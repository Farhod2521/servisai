"""Majburiy obuna: kanalga a'zo bo'lmaganlarni boshqa bo'limga o'tkazmaydi."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from services import runtime
from keyboards.user_kb import subscribe_kb
from locales.texts import t
from services.subscription import missing_channels


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if not runtime.force_sub_channels() or user is None:
            return await handler(event, data)
        # "Tekshirish" tugmasini o'z handleri qayta tekshiradi
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        missing = await missing_channels(data["bot"], user.tg_id)
        if not missing:
            return await handler(event, data)

        lang = data.get("lang", "uz")
        target = event.message if isinstance(event, CallbackQuery) else event
        if isinstance(event, CallbackQuery):
            await event.answer(t(lang, "sub_alert"), show_alert=True)
        if isinstance(target, Message):
            await target.answer(t(lang, "sub_required"), reply_markup=subscribe_kb(missing, lang))
        return None
