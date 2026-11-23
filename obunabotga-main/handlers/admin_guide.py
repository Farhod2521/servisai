"""Admin panel qo'llanmasi: har bir tugma nima qilishi — oddiy tilda, 3 sahifada."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import settings

router = Router(name="admin_guide")

PAGES = [
    (
        "📖 <b>Admin panel qo'llanmasi</b> · 1/3\n<i>Bosh sahifadagi tugmalar</i>\n\n"
        "✅ <b>To'lovlarni tasdiqlash</b> — mijoz hisobini to'ldirish uchun pul o'tkazgan, lekin bot o'zi topa olmagan to'lovlar. "
        "Pul kelganini tekshirib ✅ (tasdiqlash) yoki ❌ (rad etish) bosasiz. Qavsdagi son — nechta kutayotgani.\n\n"
        "💰 <b>ID bilan hisob to'ldirish</b> — mijozning ID raqamini (yoki @username) yozasiz, keyin summani: "
        "<code>50000</code> — qo'shadi, <code>-20000</code> — ayiradi. Mijoz ID'sini botdagi «Profil»dan ko'radi.\n\n"
        "📢 <b>Majburiy obuna</b> — mijoz botdan foydalanishdan oldin a'zo bo'lishi shart bo'lgan kanallar. "
        "Bot o'sha kanalda admin bo'lishi kerak. Kanal qo'shmasangiz — o'chiq.\n\n"
        "🧾 <b>Buyurtmalar</b> — qo'lda bajariladigan yoki tekshirilishi kerak bo'lgan buyurtmalar. Qizil bo'lsa — kutayotgani bor.\n\n"
        "👥 <b>Mijozlar</b> — mijozni ID yoki @username bo'yicha topish: balansi, buyurtmalari, bloklash.\n\n"
        "🔄 <b>Katalogni yangilash</b> — ta'minotchidan mahsulotlarni hozir yangilaydi (o'zi ham har 3 daqiqada yangilanadi).\n"
        "🔃 <b>Yangilash</b> — bosh sahifadagi raqamlarni yangilaydi."
    ),
    (
        "📖 <b>Admin panel qo'llanmasi</b> · 2/3\n<i>Bo'limlar</i>\n\n"
        "🛍 <b>Obunalar</b> — mahsulotlar ro'yxati, yangi mahsulot/bo'lim qo'shish. "
        "«🌐 API'dan qo'shish» — qoidaga to'g'ri kelmagan (do'konda yo'q) ta'minotchi mahsulotini qo'lda chiqarish; "
        "«📋 Qo'shilganlar» — qo'lda chiqarganlaringizni olib tashlash.\n\n"
        "💰 <b>Narx va foyda</b> — sotuv narxlari: foyda foizi, dollar kursi, ustama jadvali, narx o'zgarishlari tarixi. "
        "Mahsulot narxini qo'lda o'zgartirsangiz — o'sha narx qulflanadi (avtomatik o'zgarmaydi). "
        "«🏷 Brend foizlari» — har brendga o'z foizi (masalan CapCut 40%, Claude 25%): o'sha brendning hamma narxi shu foiz bilan.\n\n"
        "💳 <b>To'lov sozlamalari</b> — mijoz pul o'tkazadigan karta raqami va egasining ismi, avto-tasdiqni yoqish/o'chirish, "
        "kelgan to'lovlar ro'yxati va statistikasi.\n\n"
        "⭐ <b>Stars / Premium</b> — Telegram Stars va Premium sotuvi (Fragment): hamyondagi TON, Fragment ishlayaptimi, narxlar va ustama foizi.\n\n"
        "📣 <b>Xabarlar</b> — hamma mijozlarga xabar yuborish, yangi obuna haqida xabar, /start matnini o'zgartirish.\n\n"
        "📊 <b>Hisobotlar</b> — bugungi, 10 va 30 kunlik savdo va foyda.\n\n"
        "⚙️ <b>Sozlamalar</b> — «Yordam» tugmasi olib boradigan username, premium emojilar, brend logotiplari, /start matni."
    ),
    (
        "📖 <b>Admin panel qo'llanmasi</b> · 3/3\n<i>Mahsulot ichidagi tugmalar va buyruqlar</i>\n\n"
        "<b>Mahsulotni ochganda:</b>\n"
        "✏️ Nom · 💵 Narx · 📝 Tavsif — qo'lda o'zgartirish (yangilanishda o'chmaydi)\n"
        "📖 Qo'llanma — mijozga «qanday ishlatiladi» matni (har qator — bitta qadam)\n"
        "🎬 Video qo'llanma — xariddan keyin mijozga yuboriladi\n"
        "🛡 Kafolat matni — xariddan keyin mijozga ko'rinadigan kafolat shartlari\n"
        "📥 Zaxira qo'shish — o'zingiz sotadigan akkaunt/kodlarni qo'shish\n"
        "📢 E'lon qilish — mahsulotni kanalga e'lon qilish\n"
        "🚫 O'chirib qo'yish — vaqtincha yashirish · 🗑 Butunlay o'chirish\n"
        "↩️ Avtomatik rejimga qaytarish — qo'lda o'zgartirganlaringizni bekor qiladi\n\n"
        "<b>Buyruqlar</b> (botga yozasiz):\n"
        "«⚙️ Admin panel» (pastki menyu) — shu panel\n"
        "<code>/zaxira</code> — baza zaxirasini hozir yuboradi\n"
        "<code>/apimatn chatgpt</code> — ta'minotchidagi mahsulotlarning asl matni\n"
        "<code>/sessiya</code> — avto-to'lov uchun Telegram ulash\n"
        "<code>/business</code> — Business ulanish holati\n\n"
        "💡 <b>To'lovni tez tasdiqlash:</b> HUMO bot «To'ldirish» xabarini shu botga <b>forward</b> qilsangiz — "
        "bot summani o'zi topadi va mijoz hisobini to'ldiradi."
    ),
]


def _kb(page: int) -> InlineKeyboardMarkup:
    from keyboards.user_kb import BLUE, GREEN
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"a:help:{page - 1}", style=BLUE))
    if page < len(PAGES) - 1:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"a:help:{page + 1}", style=BLUE))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="a:home", style=GREEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.regexp(r"^a:help:\d+$"))
async def show(call: CallbackQuery, user):
    if user.tg_id not in settings.admins:
        return await call.answer()
    page = min(max(int(call.data.split(":")[2]), 0), len(PAGES) - 1)
    try:
        await call.message.edit_text(PAGES[page], reply_markup=_kb(page))
    except TelegramBadRequest:
        pass
    await call.answer()
