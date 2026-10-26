from fastapi import APIRouter
from sqlalchemy import case, func, select

from ..deps import CurrentUser, SessionDep
from ..models import Order, OrderStatus
from ..schemas import UserOut, UserStats, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

ACTIVE = (OrderStatus.pending, OrderStatus.paid, OrderStatus.processing)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value.strip() if isinstance(value, str) else value)
    await session.commit()
    return user


@router.get("/me/stats", response_model=UserStats)
async def my_stats(user: CurrentUser, session: SessionDep):
    row = (
        await session.execute(
            select(
                func.count(Order.id),
                func.count(case((Order.status.in_(ACTIVE), 1))),
                func.count(case((Order.status == OrderStatus.completed, 1))),
                func.coalesce(
                    func.sum(case((Order.status.in_((OrderStatus.paid, OrderStatus.processing, OrderStatus.completed)), Order.price))),
                    0,
                ),
            ).where(Order.user_id == user.id)
        )
    ).one()
    return UserStats(total_orders=row[0], active_orders=row[1], completed_orders=row[2], total_spent=row[3])
