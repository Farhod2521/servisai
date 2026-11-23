"""Baza zaxirasi: Render'da SQLite har deployda o'chadi — odamlarning hisobidagi pullar yo'qolmasligi uchun.

Bot butun bazani gzip JSON qilib ownerning shaxsiy chatiga yuboradi va PIN qiladi (bitta xabar, har safar yangilanadi).
Bot bo'sh baza bilan ishga tushsa (yangi deploy), ownerning pinlangan zaxirasidan hammasini tiklaydi: foydalanuvchilar,
balanslar, buyurtmalar, to'lovlar, mahsulot sozlamalari, rasmlar, admin sozlamalari.

Zaxira tez-tez yangilanadi: balans/to'lov/buyurtma o'zgarishidan bir necha soniya keyin, qolgan o'zgarishlar ≤10 daqiqada,
shuningdek bot to'xtashidan oldin (deploy paytida). Doimiy Postgres bazasi ulansa — zaxira qo'shimcha xavfsizlik bo'lib qoladi.
Faylda foydalanuvchi ma'lumotlari va yetkazilgan login/parollar bor — faqat ownerning shaxsiy chatida turadi.
"""
from __future__ import annotations

import asyncio
import base64
import enum
import gzip
import hashlib
import io
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from aiogram.types import BufferedInputFile, InputMediaDocument
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from config import settings
from database.db import SessionMaker
from database.models import Base, Order, Payment, Product, ProductImage, Setting, TopupOrder, User

log = logging.getLogger("uzshop.backup")

FILE_PREFIX = "obunalar-backup"
MAX_BYTES = 18 * 1024 * 1024          # Telegram'dan yuklab olish chegarasi 20 MB
MIN_GAP = 600                         # muhim bo'lmagan o'zgarishlar uchun zaxiralar orasidagi eng kam vaqt (soniya)
VOLATILE = {"synced_at"}              # tez-tez o'zgaradigan, zaxira tarkibini «o'zgardi» qilmasligi kerak bo'lgan ustunlar

LOCAL_KEEP = 48                       # kompyuterdagi «zaxira» papkasida shuncha oxirgi nusxa saqlanadi
LOCAL_PREFIX = "obunalar-zaxira"

_event = asyncio.Event()
_flags = {"critical": False, "installed": False}
STATE = {"last_upload": None, "last_error": "", "last_restore": ""}


def mark_dirty(critical: bool = False) -> None:
    """Baza o'zgardi. critical=True (pul/buyurtma) — zaxira bir necha soniyada yangilanadi."""
    if critical:
        _flags["critical"] = True
    _event.set()


def install() -> None:
    """Sessiya hodisalari: har commit'da zaxira navbatga qo'yiladi; balans o'zgarsa — darhol."""
    if _flags["installed"]:
        return
    _flags["installed"] = True

    admin_cols = ("overrides", "guide", "guide_video", "warranty_note", "image_url")   # sinxronlash o'zgartirmaydigan, admin kiritadigan maydonlar

    @event.listens_for(Session, "after_flush")
    def _flush(session, _ctx):  # noqa: ANN001
        from sqlalchemy import inspect as _insp
        for obj in list(session.new) + list(session.dirty):
            if isinstance(obj, (ProductImage, Setting, Order, TopupOrder, Payment)):
                _flags["critical"] = True                       # rasm, sozlama, buyurtma, to'lov — darhol
                return
            if isinstance(obj, User) and (obj in session.new or _insp(obj).attrs.balance.history.has_changes()):
                _flags["critical"] = True
                return
            if isinstance(obj, Product) and obj in session.dirty:
                attrs = _insp(obj).attrs
                if any(attrs[c].history.has_changes() for c in admin_cols):
                    _flags["critical"] = True                   # admin tahriri (narx qulfi, qo'llanma, video, kafolat, rasm)
                    return

    @event.listens_for(Session, "after_commit")
    def _commit(_session):  # noqa: ANN001
        _event.set()


# ─────────────────────────── Dump / restore ───────────────────────────

def _enc(v):
    if isinstance(v, datetime):
        return {"$dt": v.isoformat()}
    if isinstance(v, (bytes, bytearray)):
        return {"$b": base64.b64encode(bytes(v)).decode()}
    if isinstance(v, enum.Enum):
        return {"$e": v.name}
    return v


def _dec(table, key, v):
    if isinstance(v, dict):
        if "$dt" in v:
            return datetime.fromisoformat(v["$dt"])
        if "$b" in v:
            return base64.b64decode(v["$b"])
        if "$e" in v:
            return table.c[key].type.enum_class[v["$e"]]
    return v


SECRET_KEYS = {"tg_session"}


async def dump(include_images: bool = True) -> tuple[bytes, str]:
    """(gzip JSON, tarkib xeshi). Xesh tez-tez o'zgaradigan ustunlarsiz — keraksiz yuborishni oldini oladi."""
    tables: dict[str, list] = {}
    digest = hashlib.sha256()
    async with SessionMaker() as s:
        for table in Base.metadata.sorted_tables:
            if table.name == "product_images" and not include_images:
                continue
            rows = (await s.execute(select(table))).mappings().all()
            if table.name == "settings":          # Telegram session — akkaunt kaliti: zaxira fayliga (chatga) tushmaydi
                rows = [r for r in rows if r.get("key") not in SECRET_KEYS]
            enc = [{k: _enc(v) for k, v in r.items()} for r in rows]
            tables[table.name] = enc
            digest.update(json.dumps(
                [{k: v for k, v in r.items() if k not in VOLATILE} for r in enc], sort_keys=True, separators=(",", ":")).encode())
    raw = json.dumps({"v": 1, "created": datetime.utcnow().isoformat(), "tables": tables}, separators=(",", ":")).encode()
    return gzip.compress(raw, 6), digest.hexdigest()


async def is_empty() -> bool:
    async with SessionMaker() as s:
        for model in (User, Order, TopupOrder):
            if (await s.scalar(select(func.count()).select_from(model))) or 0:
                return False
    return True


async def restore(blob: bytes) -> dict[str, int]:
    """Zaxiradan bo'sh bazaga tiklaydi. Jadval nomi → qatorlar soni."""
    data = json.loads(gzip.decompress(blob))
    counts: dict[str, int] = {}
    async with SessionMaker() as s:
        for table in Base.metadata.sorted_tables:
            rows = data["tables"].get(table.name) or []
            if not rows:
                continue
            clean = []
            for r in rows:
                clean.append({k: _dec(table, k, v) for k, v in r.items() if k in table.c})
            for i in range(0, len(clean), 400):
                await s.execute(table.insert(), clean[i:i + 400])
            counts[table.name] = len(clean)
        if s.bind.dialect.name == "postgresql":          # id ketma-ketligini tiklangan eng katta id dan davom ettiramiz
            for table in Base.metadata.sorted_tables:
                if "id" in table.c and table.c.id.primary_key and table.name in counts:
                    await s.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), (SELECT COALESCE(MAX(id), 1) FROM {table.name}))"))
        await s.commit()
    return counts


# ─────────────────────────── Kompyuterdagi zaxira papkasi ───────────────────────────

def local_dir() -> Path | None:
    return Path(settings.backup_dir) if (settings.backup_dir or "").strip() else None


def save_local(blob: bytes) -> Path | None:
    """Zaxirani diskka yozadi (avval vaqtinchalik faylga, keyin almashtiradi — yarim yozilgan fayl qolmaydi).
    Eng oxirgi LOCAL_KEEP ta nusxa saqlanadi, eskilari o'chiriladi."""
    d = local_dir()
    if d is None:
        return None
    try:
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{LOCAL_PREFIX}-{datetime.now():%Y%m%d-%H%M%S}.json.gz"
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, path)
        for old in sorted(d.glob(f"{LOCAL_PREFIX}-*.json.gz"))[:-LOCAL_KEEP]:
            old.unlink(missing_ok=True)
        STATE["last_local"] = datetime.utcnow()
        return path
    except OSError as ex:
        STATE["last_error"] = f"disk: {type(ex).__name__}"
        log.warning("Zaxira diskka yozilmadi: %s", ex)
        return None


async def restore_from_local() -> dict[str, int] | None:
    """Bo'sh bazani papkadagi eng yangi (butun) zaxiradan tiklaydi. Fayl buzilgan bo'lsa — oldingisi olinadi."""
    d = local_dir()
    if d is None or not d.is_dir():
        return None
    for path in sorted(d.glob(f"{LOCAL_PREFIX}-*.json.gz"), reverse=True):
        try:
            counts = await restore(path.read_bytes())
        except Exception as ex:  # noqa: BLE001 — buzilgan/yarim fayl: keyingisini sinaymiz
            log.warning("Zaxira fayli o'qilmadi (%s): %s", path.name, type(ex).__name__)
            continue
        log.info("Baza papkadagi zaxiradan tiklandi: %s %s", path.name, counts)
        STATE["last_restore"] = f"{datetime.utcnow():%d.%m.%Y %H:%M} UTC ({path.name})"
        return counts
    return None


# ─────────────────────────── Telegram: yuborish / tiklash ───────────────────────────

def _is_backup_doc(msg) -> bool:
    doc = getattr(msg, "document", None)
    return bool(doc and (doc.file_name or "").startswith(FILE_PREFIX))


async def upload(bot, blob: bytes, caption: str) -> None:
    owner = settings.owner_id
    name = f"{FILE_PREFIX}-{datetime.utcnow():%Y%m%d-%H%M%S}.json.gz"
    doc = BufferedInputFile(blob, filename=name)
    old = None
    try:
        old = (await bot.get_chat(owner)).pinned_message
    except Exception as ex:  # noqa: BLE001
        log.warning("Pin o'qib bo'lmadi: %s", type(ex).__name__)
    if old is not None and _is_backup_doc(old):
        try:
            await bot.edit_message_media(chat_id=owner, message_id=old.message_id,
                                         media=InputMediaDocument(media=doc, caption=caption))
            return
        except Exception as ex:  # noqa: BLE001 — tahrirlab bo'lmasa, yangisini yuborib pinlaymiz
            log.info("Zaxira xabarini tahrirlab bo'lmadi (%s) — yangisi yuboriladi", type(ex).__name__)
            doc = BufferedInputFile(blob, filename=name)
    msg = await bot.send_document(owner, doc, caption=caption, disable_notification=True)
    await bot.pin_chat_message(owner, msg.message_id, disable_notification=True)
    if old is not None and _is_backup_doc(old):
        try:
            await bot.delete_message(owner, old.message_id)
        except Exception:  # noqa: BLE001
            pass


async def backup_now(bot, *, force: bool = False, last_hash: list | None = None) -> str:
    """Zaxira yaratadi: papkaga yozadi va Telegram'ga yuboradi. Qaytaradi: 'ok' | 'same' | 'empty' | 'error'."""
    if await is_empty():
        return "empty"                                  # bo'sh bazani zaxiraga yozib, yaxshi zaxirani o'chirib yubormaymiz
    blob, h = await dump()
    if len(blob) > MAX_BYTES:
        blob, h = await dump(include_images=False)
        log.warning("Zaxira katta (%d MB) — rasmlarsiz yuborildi", len(blob) // 1048576)
    if last_hash is not None and not force and last_hash[0] == h:
        return "same"
    save_local(blob)                                    # avval diskka (internet bo'lmasa ham saqlanadi)
    if not settings.owner_id:
        STATE["last_error"] = "owner_yoq"
        if last_hash is not None:
            last_hash[0] = h
        return "error"                                  # owner belgilanmagan — Telegram'ga yuboriladigan joy yo'q
    try:
        await upload(bot, blob, f"💾 Baza zaxirasi · {datetime.utcnow():%d.%m.%Y %H:%M} UTC · {len(blob) // 1024} KB")
    except Exception as ex:  # noqa: BLE001
        STATE["last_error"] = type(ex).__name__
        log.warning("Zaxira yuborilmadi: %s", type(ex).__name__)
        return "error"
    if last_hash is not None:
        last_hash[0] = h
    STATE["last_upload"], STATE["last_error"] = datetime.utcnow(), ""
    return "ok"


async def restore_if_empty(bot) -> bool:
    """Bo'sh bazada ishga tushganda tiklaydi: avval kompyuterdagi «zaxira» papkasidan, bo'lmasa ownerning pinlangan zaxirasidan."""
    if not await is_empty():
        return False
    counts = await restore_from_local()
    if counts is not None:
        try:
            await bot.send_message(settings.owner_id, "♻️ <b>Baza «zaxira» papkasidan tiklandi</b>\n"
                                                      f"Foydalanuvchilar: {counts.get('users', 0)} · buyurtmalar: {counts.get('orders', 0)} · "
                                                      f"to'lovlar: {counts.get('topup_orders', 0)}")
        except Exception:  # noqa: BLE001
            pass
        return True
    if not settings.owner_id:
        return False
    try:
        pm = (await bot.get_chat(settings.owner_id)).pinned_message
        if pm is None or not _is_backup_doc(pm):
            log.info("Tiklash uchun zaxira topilmadi (yangi o'rnatish)")
            return False
        buf = io.BytesIO()
        await bot.download(pm.document.file_id, destination=buf)
        counts = await restore(buf.getvalue())
    except Exception as ex:  # noqa: BLE001
        STATE["last_restore"] = f"xato: {type(ex).__name__}"
        log.error("Zaxiradan tiklab bo'lmadi: %s", type(ex).__name__)
        try:
            await bot.send_message(settings.owner_id, f"⚠️ Bazani zaxiradan tiklab bo'lmadi ({type(ex).__name__}). "
                                                      "Pinlangan zaxira faylini o'chirmang — menga yuboring.")
        except Exception:  # noqa: BLE001
            pass
        return False
    STATE["last_restore"] = f"{datetime.utcnow():%d.%m.%Y %H:%M} UTC"
    log.info("Baza zaxiradan tiklandi: %s", counts)
    try:
        await bot.send_message(settings.owner_id, "♻️ <b>Baza zaxiradan tiklandi</b>\n"
                                                  f"Foydalanuvchilar: {counts.get('users', 0)} · buyurtmalar: {counts.get('orders', 0)} · "
                                                  f"to'lovlar: {counts.get('topup_orders', 0)} · mahsulotlar: {counts.get('products', 0)}")
    except Exception:  # noqa: BLE001
        pass
    return True


async def run(bot) -> None:
    """Fon vazifasi: o'zgarishlarni kuzatadi va zaxirani yangilab turadi."""
    install()
    last_hash: list = [None]
    last_upload = 0.0
    while True:
        try:
            try:
                await asyncio.wait_for(_event.wait(), timeout=MIN_GAP)
            except asyncio.TimeoutError:
                pass
            _event.clear()
            crit, _flags["critical"] = _flags["critical"], False
            now = time.monotonic()
            if not crit and now - last_upload < MIN_GAP:
                continue
            await asyncio.sleep(5 if crit else 20)         # bir nechta yozuvni bitta zaxiraga jamlaymiz
            res = await backup_now(bot, last_hash=last_hash)
            if res == "ok":
                last_upload = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001
            STATE["last_error"] = type(ex).__name__
            log.warning("Zaxira vazifasi xatosi: %s", type(ex).__name__)
            await asyncio.sleep(30)


async def final_backup(bot) -> None:
    """Bot to'xtashidan oldin (deploy) oxirgi holatni yuboradi."""
    try:
        await asyncio.wait_for(backup_now(bot), timeout=20)
    except Exception as ex:  # noqa: BLE001
        log.warning("Yakuniy zaxira yuborilmadi: %s", type(ex).__name__)
