"""Bir odamning bir nechta profilini bittaga birlashtirish.

Eski profillarning buyurtmalari, to‘ldirishlari, hisob tarixi, takliflari, berilgan havolalari, sovg‘alari va
taklif qilgan do‘stlari asosiy profilga o‘tadi, balans qo‘shiladi, so‘ng eski profillar o‘chiriladi.
Asosiy profilning Telegram akkaunti saqlanadi (bir profilda faqat bitta Telegram bo‘la oladi).

Profil ID raqami yoki @username bilan ko‘rsatiladi. Avval tekshiring (bazaga tegmaydi):

    docker compose exec backend python -m app.tuzatish --into @Ielts_oling --from 51 52 53

Hammasi to‘g‘ri bo‘lsa, bajaring (bitta tranzaksiya — xato bo‘lsa hech narsa o‘zgarmaydi):

    docker compose exec backend python -m app.tuzatish --into @Ielts_oling --from 51 52 53 --apply
"""

import argparse
import asyncio
import sys

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal, engine
from .models import DeliveryItem, Order, RewardGrant, Suggestion, TelegramLoginSession, TopUp, Transaction, User
from .notify import format_price

# Profilga bog‘langan yozuvlar: (nomi, model, ustun)
MOVABLE = [
    ("buyurtma", Order, Order.user_id),
    ("hisob to‘ldirish", TopUp, TopUp.user_id),
    ("hisob tarixi", Transaction, Transaction.user_id),
    ("taklif", Suggestion, Suggestion.user_id),
    ("berilgan havola", DeliveryItem, DeliveryItem.user_id),
    ("taklif qilgan do‘st", User, User.referred_by_id),
]


async def find_user(session: AsyncSession, ref: str) -> User:
    ref = ref.strip()
    if ref.lstrip("@").isdigit() and not ref.startswith("@"):
        user = await session.get(User, int(ref))
    else:
        user = await session.scalar(select(User).where(func.lower(User.telegram_username) == ref.lstrip("@").lower()))
    if user is None:
        sys.exit(f"❌ Profil topilmadi: {ref}")
    return user


def describe(u: User) -> str:
    tg = f"@{u.telegram_username}" if u.telegram_username else "username yo‘q"
    return f"ID {u.id} · {u.full_name or '—'} · {tg} · TG {u.telegram_id or '—'} · {u.phone or 'telefon yo‘q'} · balans {format_price(u.balance)} so‘m"


async def merge(target_ref: str, source_refs: list[str], apply: bool) -> None:
    async with SessionLocal() as session:
        target = await find_user(session, target_ref)
        sources = [await find_user(session, r) for r in source_refs]
        if any(s.id == target.id for s in sources):
            sys.exit("❌ Asosiy profil birlashtiriladiganlar ro‘yxatida ham bor")
        if len({s.id for s in sources}) != len(sources):
            sys.exit("❌ Bir profil ikki marta ko‘rsatilgan")
        ids = [s.id for s in sources]

        # Bir vaqtda xarid/to‘ldirish bo‘lib, balans buzilmasligi uchun qatorlarni qulflaymiz
        await session.execute(select(User.id).where(User.id.in_([target.id, *ids])).with_for_update())

        print("✅ Asosiy profil (qoladi):")
        print("   " + describe(target))
        print("🔀 Birlashtiriladi va o‘chiriladi:")
        for s in sources:
            print("   " + describe(s))

        print("\nKo‘chiriladi:")
        for name, model, column in MOVABLE:
            n = await session.scalar(select(func.count()).select_from(model).where(column.in_(ids)))
            print(f"   {name}: {n} ta")
        balance = sum(s.balance for s in sources)
        print(f"   balans: +{format_price(balance)} so‘m → {format_price(target.balance + balance)} so‘m")

        if not apply:
            print("\nℹ️  Bu faqat tekshiruv — bazaga hech narsa yozilmadi. Bajarish uchun oxiriga --apply qo‘shing.")
            await engine.dispose()
            return

        # Yozuvlarni asosiy profilga o‘tkazish
        for _, model, column in MOVABLE:
            await session.execute(update(model).where(column.in_(ids)).values({column.key: target.id}))

        # Sovg‘alar: asosiy profilda allaqachon bor sovg‘a takrorlanmaydi (bitta foydalanuvchi — bitta sovg‘a)
        have = set((await session.scalars(select(RewardGrant.reward_id).where(RewardGrant.user_id == target.id))).all())
        for grant in (await session.scalars(select(RewardGrant).where(RewardGrant.user_id.in_(ids)))).all():
            if grant.reward_id in have:
                await session.delete(grant)
            else:
                grant.user_id = target.id
                have.add(grant.reward_id)

        # Eski kirish sessiyalari kerak emas
        await session.execute(
            delete(TelegramLoginSession).where(
                or_(TelegramLoginSession.user_id.in_(ids), TelegramLoginSession.link_user_id.in_(ids))
            )
        )

        # Bo‘sh maydonlarni eski profildan to‘ldirish; noyob maydonlar (email, google) eski profil o‘chgach o‘tkaziladi
        carry = {"email": None, "google_id": None}
        for s in sources:
            target.phone = target.phone or s.phone
            target.avatar_url = target.avatar_url or s.avatar_url
            if not target.full_name or target.full_name.strip() in {"", "."}:
                target.full_name = s.full_name
            carry["email"] = carry["email"] or s.email
            carry["google_id"] = carry["google_id"] or s.google_id
            if target.referred_by_id is None and s.referred_by_id not in (None, target.id, *ids):
                target.referred_by_id = s.referred_by_id
        # O‘zini o‘zi taklif qilgan bo‘lib qolmasin
        if target.referred_by_id in (target.id, *ids):
            target.referred_by_id = None

        target.balance += balance
        await session.flush()
        await session.execute(delete(User).where(User.id.in_(ids)))
        await session.flush()
        if target.email is None and carry["email"]:
            target.email = carry["email"]
        if target.google_id is None and carry["google_id"]:
            target.google_id = carry["google_id"]

        await session.commit()
        await session.refresh(target)
        print("\n🎉 Birlashtirildi:")
        print("   " + describe(target))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bir odamning bir nechta profilini bittaga birlashtirish")
    parser.add_argument("--into", required=True, help="Qoladigan profil: ID yoki @username")
    parser.add_argument("--from", dest="sources", nargs="+", required=True, help="Birlashtiriladigan profillar: ID yoki @username")
    parser.add_argument("--apply", action="store_true", help="Haqiqatda bajarish (busiz faqat tekshiruv)")
    args = parser.parse_args()
    asyncio.run(merge(args.into, args.sources, args.apply))


if __name__ == "__main__":
    main()
