"""Admin: ta’minotchi (canboso) holati va katalogni qo‘lda yangilash."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import AdminUser, SessionDep
from ..models import Product
from ..supplier import client, sync

router = APIRouter(prefix="/admin/supplier", tags=["admin"])


@router.get("")
async def supplier_status(_: AdminUser, session: SessionDep):
    total, active = (
        await session.execute(
            select(func.count(Product.id), func.count(Product.id).filter(Product.is_active)).where(Product.source == "canboso")
        )
    ).one()
    enabled = client.enabled()
    return {
        "enabled": enabled,
        "balance_usd": await client.fetch_balance() if enabled else None,
        "usd_rate": client._rate_cache[1] or None,
        "products": total,
        "active": active,
        "last_sync_at": sync.last_sync_at,
        "last_errors": (sync.last_result.errors[:5] if sync.last_result else []),
    }


@router.post("/sync")
async def supplier_sync(_: AdminUser, session: SessionDep):
    if not client.enabled():
        raise HTTPException(status.HTTP_409_CONFLICT, "CANBOSO_API_KEY sozlanmagan")
    try:
        result = await sync.sync(session)
    except client.SupplierError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    return {"created": result.created, "updated": result.updated, "hidden": result.hidden, "skipped": result.skipped, "errors": result.errors[:5]}
