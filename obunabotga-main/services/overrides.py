"""Admin qo'lda o'zgartirgan mahsulot maydonlari.

Ta'minotchi mahsulotlari har sinxronlashda qayta yoziladi. Admin narx, nom,
tavsif yoki emojini o'zgartirsa, o'sha maydon "qulflanadi" va sinxronlash unga
tegmaydi. "hidden" — admin mahsulotni yashirgan (yoki o'chirgan), sinxronlash
uni qayta yoqmaydi.
"""
from __future__ import annotations

import json

from database.models import Product

FIELDS = ("price", "name", "description", "emoji", "hidden", "image")


def locked(p: Product) -> set[str]:
    try:
        return set(json.loads(p.overrides or "[]"))
    except ValueError:
        return set()


def lock(p: Product, *fields: str) -> None:
    p.overrides = json.dumps(sorted(locked(p) | set(fields)))


def unlock(p: Product, *fields: str) -> None:
    left = locked(p) - set(fields)
    p.overrides = json.dumps(sorted(left)) if left else None


def unlock_all(p: Product) -> None:
    p.overrides = None
