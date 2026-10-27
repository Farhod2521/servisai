from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Order, ReferralReward, RewardGrant, User
from ..referrals import bot_link, ensure_code, friends_count, grant_rewards, notify_grants, site_link
from ..schemas import ClaimOut, MyReferralOut, MyRewardOut, PublicRewardOut, ReferralFriendOut

router = APIRouter(prefix="/referrals", tags=["referrals"])


async def _rewards(session: SessionDep, user: User, friends: int) -> list[MyRewardOut]:
    rewards = (
        await session.scalars(
            select(ReferralReward).where(ReferralReward.is_active).order_by(ReferralReward.required_friends, ReferralReward.id)
        )
    ).all()
    # Berilgan sovg‘a -> buyurtma raqami
    granted = {
        grant.reward_id: (order.number if order else None)
        for grant, order in (
            await session.execute(
                select(RewardGrant, Order).outerjoin(Order, Order.id == RewardGrant.order_id).where(RewardGrant.user_id == user.id)
            )
        ).all()
    }
    return [
        MyRewardOut(
            id=r.id,
            title=r.title,
            required_friends=r.required_friends,
            product_id=r.product_id,
            product_name=r.product.name,
            quantity=r.quantity,
            achieved=friends >= r.required_friends,
            granted=r.id in granted,
            order_number=granted.get(r.id),
        )
        for r in rewards
    ]


@router.get("/rewards", response_model=list[PublicRewardOut])
async def public_rewards(session: SessionDep):
    """Faol sovg‘alar (eng kam do‘st talab qiladigani birinchi) — saytdagi taklif oynasi uchun."""
    rewards = (
        await session.scalars(
            select(ReferralReward).where(ReferralReward.is_active).order_by(ReferralReward.required_friends, ReferralReward.id)
        )
    ).all()
    return [
        PublicRewardOut(
            id=r.id,
            title=r.title,
            required_friends=r.required_friends,
            product_id=r.product_id,
            product_name=r.product.name,
            quantity=r.quantity,
        )
        for r in rewards
        if r.product.is_active
    ]


@router.get("/me", response_model=MyReferralOut)
async def my_referrals(user: CurrentUser, session: SessionDep):
    code = await ensure_code(session, user)
    await session.commit()
    friends = (
        await session.scalars(select(User).where(User.referred_by_id == user.id).order_by(User.created_at.desc()).limit(100))
    ).all()
    count = await friends_count(session, user.id)
    return MyReferralOut(
        code=code,
        site_link=site_link(code),
        bot_link=bot_link(code),
        friends=count,
        # Do‘stning faqat ismi (birinchi so‘zi) ko‘rsatiladi
        friends_list=[ReferralFriendOut(name=(f.full_name or "Foydalanuvchi").split()[0], joined_at=f.created_at) for f in friends],
        rewards=await _rewards(session, user, count),
    )


@router.post("/claim", response_model=ClaimOut)
async def claim(user: CurrentUser, session: SessionDep, background: BackgroundTasks):
    """Shartini bajargan, lekin hali olinmagan sovg‘alarni beradi (masalan, sovg‘a keyinroq qo‘shilgan bo‘lsa)."""
    count, grants = await grant_rewards(session, user)
    await session.commit()
    if grants:
        background.add_task(notify_grants, user, grants)
    granted_ids = {r.id for r, _ in grants}
    return ClaimOut(granted=[r for r in await _rewards(session, user, count) if r.id in granted_ids])
