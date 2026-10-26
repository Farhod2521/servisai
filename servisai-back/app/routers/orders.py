from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import AdminUser, CurrentUser, SessionDep
from ..models import Order, OrderEvent, OrderStatus, Product, User
from ..notify import notify_order_created, notify_order_status
from ..schemas import (
    HistoryItemOut,
    OrderCreate,
    OrderDetailOut,
    OrderListOut,
    OrderOut,
    OrderStatusUpdate,
)

router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(prefix="/admin/orders", tags=["admin"])


async def _get_order(session: SessionDep, order_id: int, user_id: int | None = None) -> Order:
    query = select(Order).options(selectinload(Order.events)).where(Order.id == order_id)
    if user_id is not None:
        query = query.where(Order.user_id == user_id)
    order = await session.scalar(query)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyurtma topilmadi")
    return order


@router.post("", response_model=OrderDetailOut, status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, user: CurrentUser, session: SessionDep, background: BackgroundTasks):
    product = await session.get(Product, data.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    duration = data.duration_months or product.durations[0]
    if duration not in product.durations:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bu muddat mavjud emas")

    order = Order(
        user_id=user.id,
        product_id=product.id,
        product_name=product.name,
        duration_months=duration,
        price=product.price,
        comment=data.comment,
        events=[OrderEvent(status=OrderStatus.pending, note="Buyurtma yaratildi")],
    )
    session.add(order)
    await session.commit()
    order = await _get_order(session, order.id)
    background.add_task(notify_order_created, order, user)
    return order


@router.get("", response_model=OrderListOut)
async def list_orders(
    user: CurrentUser,
    session: SessionDep,
    status_: OrderStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    where = [Order.user_id == user.id]
    if status_ is not None:
        where.append(Order.status == status_)
    total = await session.scalar(select(func.count(Order.id)).where(*where))
    items = await session.scalars(
        select(Order).where(*where).order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset)
    )
    return OrderListOut(items=[OrderOut.model_validate(o) for o in items], total=total or 0)


@router.get("/history", response_model=list[HistoryItemOut])
async def order_history(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Barcha buyurtmalar bo‘yicha voqealar lentasi (yangi -> eski)."""
    rows = await session.execute(
        select(OrderEvent, Order)
        .join(Order, Order.id == OrderEvent.order_id)
        .where(Order.user_id == user.id)
        .order_by(OrderEvent.created_at.desc(), OrderEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        HistoryItemOut(
            id=event.id,
            order_id=order.id,
            order_number=order.number,
            product_name=order.product_name,
            status=event.status,
            note=event.note,
            created_at=event.created_at,
        )
        for event, order in rows
    ]


@router.get("/{order_id}", response_model=OrderDetailOut)
async def get_order(order_id: int, user: CurrentUser, session: SessionDep):
    return await _get_order(session, order_id, user.id)


@router.post("/{order_id}/cancel", response_model=OrderDetailOut)
async def cancel_order(order_id: int, user: CurrentUser, session: SessionDep):
    order = await _get_order(session, order_id, user.id)
    if order.status != OrderStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Faqat to‘lov kutilayotgan buyurtmani bekor qilish mumkin")
    order.status = OrderStatus.cancelled
    order.events.append(OrderEvent(status=OrderStatus.cancelled, note="Mijoz tomonidan bekor qilindi"))
    await session.commit()
    return await _get_order(session, order_id)


@admin_router.patch("/{order_id}", response_model=OrderDetailOut)
async def admin_update_status(
    order_id: int, data: OrderStatusUpdate, _: AdminUser, session: SessionDep, background: BackgroundTasks
):
    order = await _get_order(session, order_id)
    order.status = data.status
    if data.delivery_info is not None:
        order.delivery_info = data.delivery_info
    order.events.append(OrderEvent(status=data.status, note=data.note))
    await session.commit()
    order = await _get_order(session, order_id)
    owner = await session.get(User, order.user_id)
    if owner is not None:
        background.add_task(notify_order_status, order, owner, data.note)
    return order
