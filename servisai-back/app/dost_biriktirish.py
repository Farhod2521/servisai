"""Foydalanuvchilarni kimningdir taklif qilgan do‘sti sifatida biriktirish (hech kim o‘chirilmaydi).

Do‘st Telegram ID, profil ID yoki @username bilan ko‘rsatiladi. Profil bazada bo‘lmasa (masalan, o‘chib ketgan),
ma’lumotlari bilan qayta yaratiladi: "TG_ID|@username|+telefon|Ism" (username, telefon, ism ixtiyoriy).

Avval tekshiring (bazaga tegmaydi):

    docker compose exec backend python -m app.dost_biriktirish --referrer 48 \\
        --friend "7472223632|@Isroiljonov_design|+998507370027|ISROILJONOV" \\
        --friend "6460571495||+998500759188|." \\
        --friend "8856997735|@isroiljon0v|+998501598891|ISROILJONOV"

To‘g‘ri bo‘lsa — oxiriga --apply qo‘shib bajaring.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal, engine
from .models import User
from .referrals import friends_count, grant_rewards, notify_grants


@dataclass
class FriendSpec:
    key: str
    username: str | None = None
    phone: str | None = None
    name: str | None = None


def parse_friend(raw: str) -> FriendSpec:
    parts = [p.strip() for p in raw.split("|")]
    parts += [""] * (4 - len(parts))
    key, username, phone, name = parts[:4]
    return FriendSpec(key=key, username=username.lstrip("@") or None, phone=phone or None, name=name or None)


async def find(session: AsyncSession, key: str) -> User | None:
    key = key.strip()
    if key.startswith("@"):
        return await session.scalar(select(User).where(func.lower(User.telegram_username) == key[1:].lower()))
    if key.isdigit():
        n = int(key)
        # Katta son — Telegram ID, kichigi — profil ID
        if n > 10_000_000:
            return await session.scalar(select(User).where(User.telegram_id == n))
        return await session.get(User, n)
    return None


def describe(u: User) -> str:
    tg = f"@{u.telegram_username}" if u.telegram_username else "username yo‘q"
    return f"ID {u.id} · {u.full_name or '—'} · {tg} · TG {u.telegram_id or '—'} · {u.phone or 'telefon yo‘q'}"


async def run(referrer_key: str, raw_friends: list[str], apply: bool) -> None:
    async with SessionLocal() as session:
        referrer = await find(session, referrer_key)
        if referrer is None:
            sys.exit(f"❌ Taklif qilgan profil topilmadi: {referrer_key}")
        print("👤 Taklif qilgan:")
        print("   " + describe(referrer))
        print(f"   hozirgi do‘stlari: {await friends_count(session, referrer.id)} ta\n")

        print("👥 Do‘st sifatida biriktiriladi:")
        for spec in map(parse_friend, raw_friends):
            user = await find(session, spec.key)
            if user is None:
                if not (spec.key.isdigit() and int(spec.key) > 10_000_000):
                    sys.exit(f"❌ Topilmadi va qayta yaratib bo‘lmaydi (Telegram ID kerak): {spec.key}")
                tg_id = int(spec.key)
                print(f"   ➕ yangidan yaratiladi: {spec.name or '—'} · @{spec.username or '—'} · TG {tg_id} · {spec.phone or 'telefon yo‘q'}")
                if apply:
                    # Ism bo‘sh qolsa, foydalanuvchi botga kirganda Telegram’dagi ismi bilan to‘ladi
                    user = User(full_name=spec.name or "", telegram_id=tg_id, telegram_username=spec.username, phone=spec.phone)
                    session.add(user)
                    await session.flush()
                    user.referred_by_id = referrer.id
                continue
            if user.id == referrer.id:
                sys.exit("❌ Foydalanuvchi o‘zini o‘zi taklif qila olmaydi")
            if user.referred_by_id == referrer.id:
                print(f"   ✔ allaqachon do‘st: {describe(user)}")
                continue
            note = f" (avval ID {user.referred_by_id} ga biriktirilgan edi)" if user.referred_by_id else ""
            print(f"   🔗 biriktiriladi: {describe(user)}{note}")
            if apply:
                user.referred_by_id = referrer.id

        if not apply:
            print("\nℹ️  Bu faqat tekshiruv — bazaga hech narsa yozilmadi. Bajarish uchun oxiriga --apply qo‘shing.")
            await engine.dispose()
            return

        await session.flush()
        count, grants = await grant_rewards(session, referrer)
        await session.commit()
        print(f"\n🎉 Tayyor. {describe(referrer)} — do‘stlari: {count} ta")
        for reward, order in grants:
            print(f"   🎁 sovg‘a berildi: {reward.title} ({order.number})")
    if grants:
        await notify_grants(referrer, grants)
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Foydalanuvchilarni taklif qilgan do‘st sifatida biriktirish")
    parser.add_argument("--referrer", required=True, help="Taklif qilgan: profil ID, Telegram ID yoki @username")
    parser.add_argument("--friend", action="append", required=True, help='"TG_ID|@username|+telefon|Ism", profil ID yoki @username')
    parser.add_argument("--apply", action="store_true", help="Haqiqatda bajarish (busiz faqat tekshiruv)")
    args = parser.parse_args()
    asyncio.run(run(args.referrer, args.friend, args.apply))


if __name__ == "__main__":
    main()
