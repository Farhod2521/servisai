"""Baza ulanishi va yordamchi funksiyalar."""
from __future__ import annotations

import enum
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Enum, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)

from config import settings
from database.models import Base

engine = create_async_engine(
    settings.sqlalchemy_url,
    echo=False,
    pool_pre_ping=True,   # uzilib qolgan ulanishni avtomatik tiklaydi
    pool_recycle=280,     # Render ulanishni ~5 daqiqada uzadi
)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


log = logging.getLogger("uzshop.db")


def _server_default(col, dialect: str) -> str | None:
    """Ustun uchun DEFAULT (eski qatorlar to'lishi uchun). Yo'q bo'lsa None."""
    d = col.server_default.arg if col.server_default is not None else (
        col.default.arg if col.default is not None and col.default.is_scalar else None
    )
    if d is None:
        return None
    if isinstance(d, enum.Enum):
        d = d.name                     # SQLAlchemy Enum bazada nomini saqlaydi
    if isinstance(d, bool):
        return ("TRUE" if d else "FALSE") if dialect == "postgresql" else str(int(d))
    if isinstance(d, (int, float)):
        return str(d)
    return "'" + str(d).replace("'", "''") + "'"


def _add_missing_columns(sync_conn) -> None:
    """create_all mavjud jadvalga yangi ustun qo'shmaydi. Eski bazada (masalan Render'da)
    modeldagi, lekin bazada yo'q ustunlarni o'zi qo'shadi — shunda yangilanishdan keyin
    bot va Mini App «no such column» xatosi bilan to'xtab qolmaydi."""
    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name
    existing = set(insp.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            if dialect == "postgresql" and isinstance(col.type, Enum):
                col.type.create(sync_conn, checkfirst=True)
            ddl = col.type.compile(dialect=sync_conn.dialect)
            default = _server_default(col, dialect)
            sql = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}"
            if default is not None:
                sql += f" DEFAULT {default}" + ("" if col.nullable else " NOT NULL")
            sync_conn.execute(text(sql))
            if col.unique or col.index:
                kind = "UNIQUE " if col.unique else ""
                sync_conn.execute(text(
                    f"CREATE {kind}INDEX IF NOT EXISTS ix_{table.name}_{col.name} "
                    f"ON {table.name} ({col.name})"
                ))
            log.warning("Bazaga yetishmayotgan ustun qo'shildi: %s.%s", table.name, col.name)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionMaker() as session:
        yield session
