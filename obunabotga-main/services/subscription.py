"""Majburiy kanal obunasi.

FORCE_SUB_CHANNEL (.env) ichidagi har bir kanal uchun foydalanuvchi a'zoligini
tekshiradi. Bot o'sha kanalda ADMIN bo'lishi shart — aks holda Telegram
a'zolikni ko'rsatmaydi.

Sozlama noto'g'ri bo'lsa (bot admin emas, kanal topilmadi) foydalanuvchi
qulflanib qolmasligi uchun tekshiruv o'tkazib yuboriladi va logga ogohlantirish
yoziladi.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import settings
from services import runtime

log = logging.getLogger("uzshop.sub")

_OK_STATUSES = {"creator", "administrator", "member"}
_POSITIVE_TTL = 120  # soniya: a'zolik natijasi shuncha vaqt eslab qolinadi
_positive: dict[tuple[int, str], float] = {}
_info: dict[str, "ChannelInfo"] = {}


@dataclass
class ChannelInfo:
    ref: str
    title: str
    url: str


async def channel_info(bot: Bot, ref: str) -> ChannelInfo:
    if ref in _info:
        return _info[ref]
    title, url = ref.lstrip("@"), ""
    try:
        chat = await bot.get_chat(int(ref) if ref.lstrip("-").isdigit() else ref)
        title = chat.title or title
        if chat.username:
            url = f"https://t.me/{chat.username}"
        else:
            url = chat.invite_link or await bot.export_chat_invite_link(chat.id)
    except TelegramAPIError as ex:
        log.warning("Kanal ma'lumotini olib bo'lmadi (%s): %s", ref, ex)
        if ref.startswith("@"):
            url = f"https://t.me/{ref[1:]}"
    info = ChannelInfo(ref=ref, title=title, url=url)
    if url:  # muvaffaqiyatsiz natijani keshlamaymiz
        _info[ref] = info
    return info


async def _is_member(bot: Bot, user_id: int, ref: str, fresh: bool) -> bool:
    key = (user_id, ref)
    if not fresh and time.monotonic() - _positive.get(key, -1e9) < _POSITIVE_TTL:
        return True
    try:
        member = await bot.get_chat_member(
            int(ref) if ref.lstrip("-").isdigit() else ref, user_id
        )
    except TelegramAPIError as ex:
        log.warning(
            "Obunani tekshirib bo'lmadi (%s). Bot kanalda admin ekanini tekshiring: %s", ref, ex
        )
        return True
    ok = member.status in _OK_STATUSES or (
        member.status == "restricted" and getattr(member, "is_member", False)
    )
    if ok:
        _positive[key] = time.monotonic()
    else:
        _positive.pop(key, None)
    return ok


async def missing_channels(bot: Bot, user_id: int, fresh: bool = False) -> list[ChannelInfo]:
    """Foydalanuvchi hali obuna bo'lmagan kanallar ro'yxati (bo'sh = hammasi joyida)."""
    if user_id in settings.admins:
        return []
    out: list[ChannelInfo] = []
    for ref in runtime.force_sub_channels():
        if not await _is_member(bot, user_id, ref, fresh):
            out.append(await channel_info(bot, ref))
    return out
