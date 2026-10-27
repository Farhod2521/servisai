"""Do‘st taklif qilish dasturi: taklif kodi, do‘stni biriktirish va sovg‘alarni avtomatik berish."""

import html
import secrets
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Order, OrderStatus, ReferralReward, RewardGrant, User
from .notify import send_message, user_contact
from .shop import place_order

# Adashtiriladigan belgilarsiz (O/0, I/1)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def normalize_code(code: str | None) -> str | None:
    code = (code or "").strip().upper()
    if code.startswith("REF_"):
        code = code[4:]
    return code if 4 <= len(code) <= 16 and all(c in CODE_ALPHABET for c in code) else None


async def ensure_code(session: AsyncSession, user: User) -> str:
    """Foydalanuvchining taklif kodini qaytaradi (yo‘q bo‘lsa yaratadi). Commit chaqiruvchida."""
    while not user.referral_code:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if await session.scalar(select(User.id).where(User.referral_code == code)) is None:
            user.referral_code = code
            await session.flush()
    return user.referral_code


def site_link(code: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/?ref={code}"


def bot_link(code: str) -> str | None:
    return f"https://t.me/{settings.telegram_bot_username}?start=ref_{code}" if settings.telegram_bot_username else None


async def friends_count(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.count(User.id)).where(User.referred_by_id == user_id)) or 0


@dataclass
class ReferralEvent:
    """Ro‘yxatdan o‘tish natijasi — commit’dan keyin xabar yuborish uchun saqlanadi."""

    referrer: User
    friend: User
    friends: int
    grants: list[tuple[ReferralReward, Order]] = field(default_factory=list)


async def grant_rewards(session: AsyncSession, referrer: User) -> tuple[int, list[tuple[ReferralReward, Order]]]:
    """Shartini bajargan, hali berilmagan sovg‘alarni beradi (bepul buyurtma). Commit chaqiruvchida."""
    # Bir vaqtda ikki do‘st qo‘shilsa sovg‘a ikki marta berilmasligi uchun
    await session.execute(select(User.id).where(User.id == referrer.id).with_for_update())
    count = await friends_count(session, referrer.id)
    granted = set((await session.scalars(select(RewardGrant.reward_id).where(RewardGrant.user_id == referrer.id))).all())
    rewards = (
        await session.scalars(
            select(ReferralReward)
            .where(ReferralReward.is_active, ReferralReward.required_friends <= count)
            .order_by(ReferralReward.required_friends, ReferralReward.id)
        )
    ).all()
    result = []
    for reward in rewards:
        if reward.id in granted:
            continue
        order = await place_order(
            session,
            referrer,
            reward.product,
            quantity=reward.quantity,
            gift_note=f"🎁 Sovg‘a: {reward.required_friends} ta do‘st taklif qilgani uchun",
        )
        session.add(RewardGrant(user_id=referrer.id, reward_id=reward.id, order_id=order.id))
        result.append((reward, order))
    await session.flush()
    return count, result


async def on_signup(session: AsyncSession, user: User, code: str | None) -> None:
    """Yangi foydalanuvchini taklif qilganga biriktiradi va sovg‘alarni tekshiradi.

    Natija `user.referral_event` ga yoziladi; commit’dan keyin `notify_referral(user)` chaqiriladi.
    """
    code = normalize_code(code)
    if not code or user.referred_by_id is not None:
        return
    referrer = await session.scalar(select(User).where(User.referral_code == code))
    if referrer is None or referrer.id == user.id:
        return
    user.referred_by_id = referrer.id
    await session.flush()
    count, grants = await grant_rewards(session, referrer)
    user.referral_event = ReferralEvent(referrer=referrer, friend=user, friends=count, grants=grants)


async def notify_referral(user: User) -> None:
    """Commit’dan keyin: taklif qilganga "yangi do‘st" va (bo‘lsa) sovg‘a xabarlari."""
    event: ReferralEvent | None = getattr(user, "referral_event", None)
    if event is None:
        return
    if event.referrer.telegram_id:
        await send_message(
            event.referrer.telegram_id,
            f"👥 Yangi do‘stingiz qo‘shildi: <b>{html.escape(event.friend.full_name or 'Foydalanuvchi')}</b>\n"
            f"Jami taklif qilgan do‘stlaringiz: <b>{event.friends} ta</b>",
        )
    await notify_grants(event.referrer, event.grants)


async def notify_grants(referrer: User, grants: list[tuple[ReferralReward, Order]]) -> None:
    for reward, order in grants:
        if referrer.telegram_id:
            text = (
                f"🎁 <b>Tabriklaymiz!</b> Siz {reward.required_friends} ta do‘stingizni taklif qildingiz va sovg‘a oldingiz:\n"
                f"<b>{html.escape(reward.title)}</b> — {html.escape(order.product_name)}"
                + (f" × {order.quantity}" if order.quantity > 1 else "")
            )
            if order.status == OrderStatus.completed and order.delivery_info:
                text += f"\n\n📦 <b>Sizning ma’lumotlaringiz:</b>\n{html.escape(order.delivery_info)}"
            else:
                text += f"\n\n⏳ Yetkazib berish vaqti: {html.escape(reward.product.delivery_time)}. Tayyor bo‘lgach shu yerga yuboramiz."
            await send_message(referrer.telegram_id, text)
        done = order.status == OrderStatus.completed
        await send_message(
            settings.telegram_admin_chat_id,
            f"🎁 Sovg‘a berildi: {html.escape(reward.title)}\n<b>{order.number}</b> — {html.escape(order.product_name)}\n"
            f"Mijoz: {user_contact(referrer)}\n" + ("✅ Avtomatik yetkazildi" if done else "⏳ Yetkazib berish kerak (admin panel → Buyurtmalar)"),
        )
