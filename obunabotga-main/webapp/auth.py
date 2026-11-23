"""Telegram Mini App `initData` imzosini tekshirish.

Mini App foydalanuvchini o'zi aytgan ID bilan emas, Telegram imzolagan
`initData` orqali taniydi. Imzo bot tokeni bilan HMAC-SHA256 orqali tekshiriladi:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class AuthError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict:
    """Imzo to'g'ri bo'lsa Telegram foydalanuvchisi (dict) ni qaytaradi."""
    if not init_data:
        raise AuthError("initData yo'q")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", "")
    if not received:
        raise AuthError("hash yo'q")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("imzo noto'g'ri")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as ex:
        raise AuthError("auth_date noto'g'ri") from ex
    if time.time() - auth_date > max_age:
        raise AuthError("sessiya eskirgan")

    try:
        user = json.loads(pairs["user"])
        int(user["id"])
    except (KeyError, ValueError, TypeError) as ex:
        raise AuthError("user maydoni noto'g'ri") from ex
    return user
