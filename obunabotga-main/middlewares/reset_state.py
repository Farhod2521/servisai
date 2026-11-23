"""Buyruq (/start va h.k.) kelganda admin panelning kutish holatini (FSM) tozalaydi.

Admin «Foydalanuvchilar», «Balans» kabi bo'limga kirsa bot matn kutish holatiga o'tadi va
admin router birinchi turgani uchun keyingi HAMMA xabarni (hatto /start ni ham) shu holat
oladi — natijada «Topilmadi. ID yoki @username ni tekshiring» chiqib, bot qotib qolardi.
Buyruq har doim holatdan chiqaradi; faqat zaxira kiritishdagi /done holatni saqlaydi.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

KEEP_STATE = {"done"}


def command_of(text: str | None) -> str | None:
    """'/start@bot arg' → 'start'. Buyruq bo'lmasa None."""
    if not text or not text.startswith("/"):
        return None
    return text.split(maxsplit=1)[0][1:].split("@", 1)[0].lower() or None


class ResetStateOnCommand(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            cmd = command_of(event.text)
            state = data.get("state")
            if cmd and cmd not in KEEP_STATE and state is not None:
                await state.clear()
                data["raw_state"] = None   # FSM filtri shu qiymatni o'qiydi (oldindan olib bo'lingan)
        return await handler(event, data)
