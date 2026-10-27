from datetime import datetime, timedelta, timezone

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import case, func, or_, select

from ..deps import AdminUser, SessionDep
from ..models import DeliveryItem, Order, OrderStatus, Product, ReferralReward, RewardGrant, TopUp, TopUpStatus, User
from ..referrals import friends_count
from ..schemas import (
    AdminOrderOut,
    AdminProductOut,
    AdminStats,
    AdminUserDetail,
    AdminUserList,
    AdminUserOut,
    AdminUserTopUp,
    DeliveryItemOut,
    DeliveryItemsAdd,
    DeliveryItemsAddOut,
    RewardGrantOut,
    RewardIn,
    RewardOut,
    TopReferrerOut,
    OrderOut,
    ProductCreate,
    ProductUpdate,
    TopProductOut,
)
from ..stock import attach_sold_counts, sync_pool_stock

router = APIRouter(prefix="/admin", tags=["admin"])

# Pul tushgan buyurtmalar (bekor qilinganlari pul qaytarilgani uchun hisobga olinmaydi)
PAID = (OrderStatus.paid, OrderStatus.processing, OrderStatus.completed)
ACTIVE = (OrderStatus.pending, OrderStatus.paid, OrderStatus.processing)


@router.get("/stats", response_model=AdminStats)
async def stats(_: AdminUser, session: SessionDep):
    now = datetime.now(timezone.utc)
    users_total, users_new = (
        await session.execute(
            select(func.count(User.id), func.count(case((User.created_at >= now - timedelta(days=7), 1))))
        )
    ).one()
    products_total, products_active = (
        await session.execute(select(func.count(Product.id), func.count(case((Product.is_active, 1)))))
    ).one()
    revenue = func.coalesce(func.sum(case((Order.status.in_(PAID), Order.price))), 0)
    revenue_30d = func.coalesce(
        func.sum(case(((Order.status.in_(PAID)) & (Order.created_at >= now - timedelta(days=30)), Order.price))), 0
    )
    orders_total, orders_active, revenue_total, revenue_month = (
        await session.execute(
            select(func.count(Order.id), func.count(case((Order.status.in_(ACTIVE), 1))), revenue, revenue_30d)
        )
    ).one()
    topups_pending = await session.scalar(select(func.count(TopUp.id)).where(TopUp.status == TopUpStatus.pending))
    return AdminStats(
        users_total=users_total,
        users_new_7d=users_new,
        products_active=products_active,
        products_total=products_total,
        orders_total=orders_total,
        orders_active=orders_active,
        revenue_total=revenue_total,
        revenue_30d=revenue_month,
        topups_pending=topups_pending or 0,
    )


@router.get("/orders", response_model=list[AdminOrderOut])
async def recent_orders(
    _: AdminUser,
    session: SessionDep,
    # Bir nechta holat berilishi mumkin: ?status=paid&status=processing
    status_: list[OrderStatus] | None = Query(default=None, alias="status"),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = select(Order, User).join(User, User.id == Order.user_id)
    if status_:
        query = query.where(Order.status.in_(status_))
    rows = await session.execute(query.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset))
    return [
        AdminOrderOut(
            **OrderOut.model_validate(order).model_dump(),
            user_id=order.user_id,
            user_name=user.full_name or "—",
            user_telegram_username=user.telegram_username,
            user_phone=user.phone,
        )
        for order, user in rows
    ]


@router.get("/top-products", response_model=list[TopProductOut])
async def top_products(_: AdminUser, session: SessionDep, limit: int = Query(default=5, ge=1, le=20)):
    rows = await session.execute(
        select(Order.product_id, Order.product_name, func.count(Order.id), func.sum(Order.price))
        .where(Order.status.in_(PAID))
        .group_by(Order.product_id, Order.product_name)
        .order_by(func.sum(Order.price).desc())
        .limit(limit)
    )
    return [TopProductOut(product_id=pid, product_name=name, orders=n, revenue=total) for pid, name, n, total in rows]


# ---------- Foydalanuvchilar ----------


@router.get("/users", response_model=AdminUserList)
async def list_users(
    _: AdminUser,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=100),
    sort: Literal["new", "balance", "spent", "last_login"] = "new",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    orders = (
        select(
            Order.user_id.label("user_id"),
            func.count(Order.id).label("orders_count"),
            func.coalesce(func.sum(case((Order.status.in_(PAID), Order.price))), 0).label("total_spent"),
        )
        .group_by(Order.user_id)
        .subquery()
    )
    orders_count = func.coalesce(orders.c.orders_count, 0)
    total_spent = func.coalesce(orders.c.total_spent, 0)

    where = []
    if q and q.strip():
        term = f"%{q.strip().lstrip('@')}%"
        conditions = [
            User.full_name.ilike(term),
            User.email.ilike(term),
            User.telegram_username.ilike(term),
            User.phone.ilike(term),
        ]
        if q.strip().isdigit():
            conditions += [User.id == int(q.strip()), User.telegram_id == int(q.strip())]
        where.append(or_(*conditions))

    order_by = {
        "new": (User.created_at.desc(), User.id.desc()),
        "balance": (User.balance.desc(), User.id.desc()),
        "spent": (total_spent.desc(), User.id.desc()),
        "last_login": (User.last_login_at.desc().nulls_last(), User.id.desc()),
    }[sort]

    total = await session.scalar(select(func.count(User.id)).where(*where))
    rows = await session.execute(
        select(User, orders_count, total_spent)
        .outerjoin(orders, orders.c.user_id == User.id)
        .where(*where)
        .order_by(*order_by)
        .limit(limit)
        .offset(offset)
    )
    total_balance, with_balance = (
        await session.execute(select(func.coalesce(func.sum(User.balance), 0), func.count(case((User.balance > 0, 1)))))
    ).one()
    return AdminUserList(
        items=[
            AdminUserOut(
                id=u.id,
                full_name=u.full_name,
                email=u.email,
                phone=u.phone,
                avatar_url=u.avatar_url,
                telegram_id=u.telegram_id,
                telegram_username=u.telegram_username,
                balance=u.balance,
                is_admin=u.is_admin,
                created_at=u.created_at,
                last_login_at=u.last_login_at,
                orders_count=n,
                total_spent=spent,
            )
            for u, n, spent in rows
        ],
        total=total or 0,
        total_balance=total_balance,
        users_with_balance=with_balance,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: int, _: AdminUser, session: SessionDep):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foydalanuvchi topilmadi")
    orders = (
        await session.scalars(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc(), Order.id.desc()))
    ).all()
    topups = (
        await session.scalars(select(TopUp).where(TopUp.user_id == user_id).order_by(TopUp.created_at.desc(), TopUp.id.desc()))
    ).all()
    spent = sum(o.price for o in orders if o.status in PAID)
    referrer = await session.get(User, user.referred_by_id) if user.referred_by_id else None
    return AdminUserDetail(
        friends=await friends_count(session, user.id),
        referred_by_name=referrer.full_name if referrer else None,
        user=AdminUserOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            balance=user.balance,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            orders_count=len(orders),
            total_spent=spent,
        ),
        topped_up=sum(t.amount for t in topups if t.status == TopUpStatus.approved),
        topups=[AdminUserTopUp(id=t.id, amount=t.amount, status=t.status, admin_note=t.admin_note, created_at=t.created_at) for t in topups],
        orders=[OrderOut.model_validate(o) for o in orders],
    )


# ---------- Mahsulotlar ----------


@router.get("/products", response_model=list[AdminProductOut])
async def list_products(_: AdminUser, session: SessionDep):
    products = (await session.scalars(select(Product).order_by(Product.sort_order, Product.name))).all()
    return await attach_sold_counts(session, products)


@router.post("/products", response_model=AdminProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, _: AdminUser, session: SessionDep):
    if await session.get(Product, data.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"“{data.id}” identifikatorli mahsulot allaqachon bor")
    values = data.model_dump(exclude_none=True)
    product = Product(
        **{
            "description": "",
            "features": [],
            "category": "other",
            "is_active": True,
            "delivery_mode": "manual",
            "delivery_time": "10 daqiqa – 1 soat",
            "notes": "",
            **values,
        }
    )
    if product.delivery_mode == "auto":
        product.stock = 0  # elementlar qo‘shilgach ko‘payadi
    session.add(product)
    await session.commit()
    await session.refresh(product)
    await attach_sold_counts(session, [product])
    return product


async def _get(session: SessionDep, product_id: str) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    return product


@router.patch("/products/{product_id}", response_model=AdminProductOut)
async def update_product(product_id: str, data: ProductUpdate, _: AdminUser, session: SessionDep):
    product = await _get(session, product_id)
    changes = data.model_dump(exclude_unset=True)
    # badge va old_price ni null qilib olib tashlash mumkin, qolganlari majburiy
    for field in (
        "name", "price", "durations", "category", "features", "sort_order", "is_active", "description",
        "delivery_mode", "delivery_time", "notes", "sold_base", "duration_unit",
    ):
        if field in changes and changes[field] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"“{field}” bo‘sh bo‘lishi mumkin emas")
    price = changes.get("price", product.price)
    old_price = changes.get("old_price", product.old_price)
    if old_price is not None and old_price <= price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Eski narx hozirgi narxdan katta bo‘lishi kerak")
    for field, value in changes.items():
        setattr(product, field, value)
    # Avtomatik mahsulotda soni qo‘lda emas, berilmagan elementlar soni bilan belgilanadi
    await sync_pool_stock(session, product)
    await session.commit()
    await session.refresh(product)
    await attach_sold_counts(session, [product])
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, _: AdminUser, session: SessionDep):
    # Buyurtmalar o‘chmaydi: product_id NULL bo‘ladi, nomi va narxi buyurtmada saqlanib qoladi
    await session.delete(await _get(session, product_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Avtomatik yetkaziladigan elementlar (har xaridorga alohida havola/kod) ----------


@router.get("/products/{product_id}/items", response_model=list[DeliveryItemOut])
async def list_items(
    product_id: str,
    _: AdminUser,
    session: SessionDep,
    state: Literal["available", "delivered"] = "available",
):
    await _get(session, product_id)
    query = (
        select(DeliveryItem, Order, User)
        .outerjoin(Order, Order.id == DeliveryItem.order_id)
        .outerjoin(User, User.id == DeliveryItem.user_id)
        .where(DeliveryItem.product_id == product_id)
    )
    if state == "available":
        query = query.where(DeliveryItem.order_id.is_(None)).order_by(DeliveryItem.id)
    else:
        query = query.where(DeliveryItem.delivered_at.is_not(None)).order_by(DeliveryItem.delivered_at.desc())
    rows = await session.execute(query.limit(1000))
    return [
        DeliveryItemOut(
            id=item.id,
            content=item.content,
            created_at=item.created_at,
            delivered_at=item.delivered_at,
            order_id=item.order_id,
            order_number=order.number if order else None,
            user_id=item.user_id,
            user_name=user.full_name if user else None,
        )
        for item, order, user in rows
    ]


@router.post("/products/{product_id}/items", response_model=DeliveryItemsAddOut, status_code=status.HTTP_201_CREATED)
async def add_items(product_id: str, data: DeliveryItemsAdd, _: AdminUser, session: SessionDep):
    product = await _get(session, product_id)
    existing = set(
        (
            await session.scalars(
                select(DeliveryItem.content).where(DeliveryItem.product_id == product_id, DeliveryItem.order_id.is_(None))
            )
        ).all()
    )
    added = 0
    for line in data.lines:
        content = line.strip()
        if not content or content in existing:
            continue
        existing.add(content)
        session.add(DeliveryItem(product_id=product_id, content=content))
        added += 1
    await session.flush()
    await sync_pool_stock(session, product)
    await session.commit()
    return DeliveryItemsAddOut(added=added, skipped=len(data.lines) - added, stock=product.stock)


@router.delete("/products/{product_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(product_id: str, item_id: int, _: AdminUser, session: SessionDep):
    item = await session.get(DeliveryItem, item_id)
    if item is None or item.product_id != product_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Element topilmadi")
    if item.order_id is not None or item.delivered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Mijozga berilgan elementni o‘chirib bo‘lmaydi")
    await session.delete(item)
    await session.flush()
    await sync_pool_stock(session, await _get(session, product_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Sovg‘alar (do‘st taklif qilish) ----------


async def _reward_out(session: SessionDep, reward: ReferralReward) -> RewardOut:
    granted = await session.scalar(select(func.count(RewardGrant.id)).where(RewardGrant.reward_id == reward.id))
    # Kamida N ta do‘st taklif qilgan foydalanuvchilar
    per_user = select(User.referred_by_id).where(User.referred_by_id.is_not(None)).group_by(User.referred_by_id)
    eligible = await session.scalar(
        select(func.count()).select_from(per_user.having(func.count(User.id) >= reward.required_friends).subquery())
    )
    return RewardOut(
        id=reward.id,
        title=reward.title,
        required_friends=reward.required_friends,
        product_id=reward.product_id,
        product_name=reward.product.name,
        quantity=reward.quantity,
        is_active=reward.is_active,
        granted_count=granted or 0,
        eligible_count=eligible or 0,
        created_at=reward.created_at,
    )


async def _reward_with_product(session: SessionDep, reward_id: int) -> ReferralReward:
    # Async sessiyada lazy-load ishlamaydi — mahsulot so‘rov bilan birga yuklanadi
    reward = await session.scalar(
        select(ReferralReward).where(ReferralReward.id == reward_id).execution_options(populate_existing=True)
    )
    if reward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sovg‘a topilmadi")
    return reward


async def _get_reward(session: SessionDep, reward_id: int) -> ReferralReward:
    reward = await session.get(ReferralReward, reward_id)
    if reward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sovg‘a topilmadi")
    return reward


@router.get("/rewards", response_model=list[RewardOut])
async def list_rewards(_: AdminUser, session: SessionDep):
    rewards = (await session.scalars(select(ReferralReward).order_by(ReferralReward.required_friends, ReferralReward.id))).all()
    return [await _reward_out(session, r) for r in rewards]


@router.post("/rewards", response_model=RewardOut, status_code=status.HTTP_201_CREATED)
async def create_reward(data: RewardIn, _: AdminUser, session: SessionDep):
    await _get(session, data.product_id)
    reward = ReferralReward(**data.model_dump())
    session.add(reward)
    await session.commit()
    return await _reward_out(session, await _reward_with_product(session, reward.id))


@router.patch("/rewards/{reward_id}", response_model=RewardOut)
async def update_reward(reward_id: int, data: RewardIn, _: AdminUser, session: SessionDep):
    reward = await _get_reward(session, reward_id)
    await _get(session, data.product_id)
    for field, value in data.model_dump().items():
        setattr(reward, field, value)
    await session.commit()
    return await _reward_out(session, await _reward_with_product(session, reward_id))


@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward(reward_id: int, _: AdminUser, session: SessionDep):
    # Berilgan sovg‘alarning buyurtmalari saqlanib qoladi
    await session.delete(await _get_reward(session, reward_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/rewards/grants", response_model=list[RewardGrantOut])
async def reward_grants(_: AdminUser, session: SessionDep, limit: int = Query(default=50, ge=1, le=200)):
    rows = await session.execute(
        select(RewardGrant, ReferralReward, User, Order)
        .join(ReferralReward, ReferralReward.id == RewardGrant.reward_id)
        .join(User, User.id == RewardGrant.user_id)
        .outerjoin(Order, Order.id == RewardGrant.order_id)
        .order_by(RewardGrant.created_at.desc(), RewardGrant.id.desc())
        .limit(limit)
    )
    return [
        RewardGrantOut(
            id=g.id,
            user_id=u.id,
            user_name=u.full_name or "—",
            user_telegram_username=u.telegram_username,
            reward_title=r.title,
            order_id=o.id if o else None,
            order_number=o.number if o else None,
            order_status=o.status if o else None,
            created_at=g.created_at,
        )
        for g, r, u, o in rows
    ]


@router.get("/referrers", response_model=list[TopReferrerOut])
async def top_referrers(_: AdminUser, session: SessionDep, limit: int = Query(default=10, ge=1, le=100)):
    friend = User.__table__.alias("friend")
    rows = await session.execute(
        select(User, func.count(friend.c.id).label("friends"))
        .join(friend, friend.c.referred_by_id == User.id)
        .group_by(User.id)
        .order_by(func.count(friend.c.id).desc(), User.id)
        .limit(limit)
    )
    return [
        TopReferrerOut(user_id=u.id, user_name=u.full_name or "—", user_telegram_username=u.telegram_username, friends=n)
        for u, n in rows
    ]
