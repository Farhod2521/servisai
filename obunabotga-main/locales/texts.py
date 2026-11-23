"""Ko'p tilli matnlar. Asosiy til — o'zbekcha."""
from __future__ import annotations

LANGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "menu_orders": "📦 Buyurtmalarim",
        "menu_topup": "💳 Hisobni to'ldirish",
        "menu_help": "💬 Yordam / Aloqa",
        "menu_admin": "⚙️ Admin panel",

        "out_of_stock": "😔 Tugagan",

        "btn_back": "⬅️ Orqaga",


        "not_enough_balance": (
            "❌ <b>Hisobingizda mablag' yetarli emas.</b>\n\n"
            "💵 Kerak: <b>{need}</b>\n"
            "💰 Hisobda: <b>{have}</b>\n"
            "➖➖➖➖➖➖➖➖\n"
            "🔻 Yetishmayapti: <b>{diff}</b>"
        ),
        "order_success": (
            "✅ <b>Buyurtma #{order_id} muvaffaqiyatli!</b>\n\n"
            "💵 To'landi: <b>{total}</b>\n"
            "💰 Qolgan hisob: <b>{balance}</b>\n\n"
            "{delivery}"
        ),
        "order_manual_note": (
            "⏳ Buyurtmangiz qabul qilindi. Administrator tez orada "
            "siz bilan bog'lanadi."
        ),
        "item_failed": "bajarilmadi, mablag' hisobingizga qaytarildi",
        "order_failed": (
            "❌ <b>Buyurtma bajarilmadi</b>\n\n"
            "{delivery}\n\n"
            "💰 Hisobingiz: <b>{balance}</b>"
        ),
        "orders_title": "📦 <b>Buyurtmalarim</b>",
        "orders_empty": "📭 Sizda hali buyurtma yo'q.",

        "topup_title": (
            "💳 <b>Hisobni to'ldirish</b>\n\n"
            "💰 Joriy hisob: <b>{balance}</b>\n\n"
            "To'lov usulini tanlang:"
        ),
        "topup_ok": "✅ Hisobingiz <b>{amount}</b> ga to'ldirildi.\n💰 Yangi hisob: <b>{balance}</b>",


        "help": (
            "💬 <b>Yordam va aloqa</b>\n\n"
            "Savollaringiz bo'lsa administratorga yozing:\n"
            "👤 @{support}\n\n"
            "⏰ Ish vaqti: 09:00 — 23:00"
        ),

        "announce_new": (
            "🆕 <b>YANGI MAHSULOT!</b>\n\n"
            "{emoji} <b>{name}</b>\n\n"
            "{description}\n\n"
            "💵 Narx: <b>{price}</b>\n"
            "📦 Mavjud: <b>{stock}</b>\n\n"
            "👇 Sotib olish uchun bosing"
        ),
        "btn_open_bot": "🛒 Botga o'tish",

        "sub_required": (
            "🔒 <b>Davom etish uchun kanalga obuna bo'ling</b>\n\n"
            "Servis AI botidan foydalanish uchun quyidagi kanal(lar)ga a'zo bo'ling, "
            "so'ng <b>«Tekshirish»</b> tugmasini bosing 👇"
        ),
        "sub_alert": "🔒 Avval kanalga obuna bo'ling.",
        "sub_not_yet": "❌ Hali obuna bo'lmadingiz. Kanalga a'zo bo'lib, qayta urinib ko'ring.",
        "sub_ok": "✅ Rahmat! Obuna tasdiqlandi.",
        "btn_check_sub": "✅ Tekshirish",
        "btn_open_app": "Obunalar",

        "banned": "🚫 Siz bloklangansiz.",
        "unknown": "🤔 Tushunmadim. /start buyrug'ini bosing.",
    },
}

# Ruscha va inglizcha — o'zbekcha kalitlar asosida, tarjima to'ldiriladi.
TEXTS["ru"] = dict(TEXTS["uz"])
TEXTS["ru"].update({
    "menu_orders": "📦 Мои заказы",
    "menu_topup": "💳 Пополнить баланс",
    "menu_help": "💬 Помощь / Связь",
    "btn_back": "⬅️ Назад",
    "sub_required": (
        "🔒 <b>Подпишитесь на канал, чтобы продолжить</b>\n\n"
        "Подпишитесь на канал(ы) ниже и нажмите <b>«Проверить»</b> 👇"
    ),
    "sub_alert": "🔒 Сначала подпишитесь на канал.",
    "sub_not_yet": "❌ Вы ещё не подписались. Подпишитесь и попробуйте снова.",
    "sub_ok": "✅ Спасибо! Подписка подтверждена.",
    "btn_check_sub": "✅ Проверить",
    "btn_open_app": "Obunalar",
})
TEXTS["en"] = dict(TEXTS["uz"])
TEXTS["en"].update({
    "menu_orders": "📦 My orders",
    "menu_topup": "💳 Top up balance",
    "menu_help": "💬 Help / Contact",
    "btn_back": "⬅️ Back",
    "sub_required": (
        "🔒 <b>Subscribe to our channel to continue</b>\n\n"
        "Join the channel(s) below, then press <b>“Check”</b> 👇"
    ),
    "sub_alert": "🔒 Please subscribe to the channel first.",
    "sub_not_yet": "❌ You haven't subscribed yet. Join the channel and try again.",
    "sub_ok": "✅ Thanks! Subscription confirmed.",
    "btn_check_sub": "✅ Check",
    "btn_open_app": "Obunalar",
})


# Yangi mahsulot / zaxira xabarnomalari
TEXTS["uz"].update({
    "ev_new": "🆕 <b>Yangi obuna qo'shildi!</b>",
    "ev_added": "➕ Qo'shildi: <b>{n}</b>",
    "ev_stock": "📦 Hozirgi zaxira: <b>{n}</b>",
    "ev_price": "💵 Narxi: <b>{price}</b>",
    "ev_digest": "🔔 <b>Servis AI'da yangiliklar!</b>",
    "btn_buy_now": "Sotib olish",
    "guide_title": "📖 <b>Qanday foydalaniladi:</b>",
})
TEXTS["ru"].update({
    "ev_new": "🆕 <b>Добавлена новая подписка!</b>",
    "ev_added": "➕ Добавлено: <b>{n}</b>",
    "ev_stock": "📦 Сейчас в наличии: <b>{n}</b>",
    "ev_price": "💵 Цена: <b>{price}</b>",
    "ev_digest": "🔔 <b>Новинки в Servis AI!</b>",
    "btn_buy_now": "Купить",
    "guide_title": "📖 <b>Как пользоваться:</b>",
})
TEXTS["en"].update({
    "ev_new": "🆕 <b>New subscription added!</b>",
    "ev_added": "➕ Added: <b>{n}</b>",
    "ev_stock": "📦 Current stock: <b>{n}</b>",
    "ev_price": "💵 Price: <b>{price}</b>",
    "ev_digest": "🔔 <b>What's new in Servis AI!</b>",
    "btn_buy_now": "Buy now",
    "guide_title": "📖 <b>How to use:</b>",
})


# ─── Oddiy bot (Mini App'siz): pastki menyu va mijozga qulay matnlar ───
TEXTS["uz"].update({
    "menu_subs": "Obunalar", "menu_topup": "Hisobni to'ldirish", "menu_orders": "Buyurtmalarim",
    "menu_profile": "Profil", "menu_guide": "Qo'llanma", "menu_help": "Yordam",
    "hello": (
        "<b>Salom, {name}!</b> 👋\n\n"
        "Eng kerakli premium obunalar bir joyda 💎\n"
        "⚡ Tez  ·  🛡 Kafolatli  ·  💳 Qulay to'lov"
    ),
    "choose_sub": "<b>Obunani tanlang</b> 👇",
    "sub_unavailable": "😔 Bu obuna vaqtincha tugagan. Tez orada qaytadi, keyinroq urinib ko'ring.",
    "brand_empty": "Bu bo'limda hozircha obuna yo'q. Tez orada qo'shiladi.",
    "all_sold_out": "🔴 Hozircha hammasi tugagan, tez orada qaytadi.",
    "choose_plan": "{brand}\n\n📋 Tarifni tanlang:",
    "plan_card": "💎 <b>{name}</b>\n\n{description}\n\n💵 Narxi: <b>{price}</b>\n💳 Hisobingiz: <b>{balance}</b>",
    "btn_confirm_buy": "Sotib olish", "btn_back": "⬅️ Orqaga",
    "ask_email": "📧 Obuna biriktiriladigan <b>email</b> manzilni yozing:",
    "ask_accounts": "🔑 <b>{n}</b> ta akkaunt ma'lumotini yozing (har qatorga bittadan):",
    "bad_input": "❌ {why}\n\nQaytadan yozing yoki /start bosing.",
    "buying": "⏳ Buyurtmangiz bajarilmoqda, biroz kuting...",
    "order_success": (
        "✅ <b>Buyurtma #{order_id} tayyor!</b>\n\n"
        "💵 To'landi: <b>{total}</b>\n"
        "💳 Qolgan hisob: <b>{balance}</b>\n\n"
        "{delivery}\n\n"
        "🎉 Xaridingiz uchun rahmat!"
    ),
    "topup_title": "💳 <b>Hisobni to'ldirish</b>\n\nQulay summani tanlang 👇",
    "orders_empty": "📦 Hozircha buyurtmalaringiz yo'q.\n\n🛍 «Obunalar» bo'limidan birinchi obunangizni oling!",
    "orders_title": "📦 <b>Buyurtmalaringiz</b>",
    "profile": "👤 <b>Mening profilim</b>\n\n🆔 ID: <code>{id}</code>\n🙍 Ism: {name}\n💳 Hisob: <b>{balance}</b>\n🌐 Til: {language}",
     "lang_changed": "✅ Til o'zgartirildi.",
    "guide_choose": "📚 <b>Qo'llanma</b>\n\nQaysi obuna uchun yo'riqnoma kerak?",
    "guide_none": "Bu obuna uchun qo'llanma hali yozilmagan. «Yordam» bo'limiga yozing.",
    "help": "🎧 <b>Yordam markazi</b>\n\nSavolingiz yoki muammoyingiz bormi? Administratorga yozing, tez javob beramiz 👇",
    "btn_write_support": "@{support} ga yozish", "btn_topup_now": "Hisobni to'ldirish",
    "stale_button": "Bu tugma eskirgan. /start bosing.",
})
TEXTS["ru"].update({
    "menu_subs": "Подписки", "menu_topup": "Пополнить баланс", "menu_orders": "Мои заказы",
    "menu_profile": "Профиль", "menu_guide": "Инструкция", "menu_help": "Помощь",
    "hello": (
        "<b>Привет, {name}!</b> 👋\n\n"
        "Самые нужные премиум-подписки в одном месте 💎\n"
        "⚡ Быстро  ·  🛡 С гарантией  ·  💳 Удобная оплата"
    ),
    "choose_sub": "<b>Выберите подписку</b> 👇",
    "sub_unavailable": "😔 Эта подписка временно закончилась. Скоро вернётся, попробуйте позже.",
    "brand_empty": "В этом разделе пока нет подписок. Скоро добавим.",
    "all_sold_out": "🔴 Пока всё закончилось, скоро вернётся.",
    "choose_plan": "{brand}\n\n📋 Выберите тариф:",
    "plan_card": "💎 <b>{name}</b>\n\n{description}\n\n💵 Цена: <b>{price}</b>\n💳 Ваш баланс: <b>{balance}</b>",
    "btn_confirm_buy": "Купить", "btn_back": "⬅️ Назад",
    "ask_email": "📧 Напишите <b>email</b>, к которому привязать подписку:",
    "ask_accounts": "🔑 Напишите данные <b>{n}</b> аккаунтов (по одному в строке):",
    "bad_input": "❌ {why}\n\nНапишите ещё раз или нажмите /start.",
    "buying": "⏳ Заказ выполняется, подождите немного...",
    "order_success": (
        "✅ <b>Заказ #{order_id} готов!</b>\n\n"
        "💵 Оплачено: <b>{total}</b>\n"
        "💳 Остаток на счёте: <b>{balance}</b>\n\n"
        "{delivery}\n\n"
        "🎉 Спасибо за покупку!"
    ),
    "topup_title": "💳 <b>Пополнение баланса</b>\n\nВыберите удобную сумму 👇",
    "orders_empty": "📦 Заказов пока нет.\n\n🛍 Выберите первую подписку в разделе «Подписки»!",
    "orders_title": "📦 <b>Ваши заказы</b>",
    "profile": "👤 <b>Мой профиль</b>\n\n🆔 ID: <code>{id}</code>\n🙍 Имя: {name}\n💳 Баланс: <b>{balance}</b>\n🌐 Язык: {language}",
     "lang_changed": "✅ Язык изменён.",
    "guide_choose": "📚 <b>Инструкция</b>\n\nДля какой подписки нужна инструкция?",
    "guide_none": "Для этой подписки инструкция ещё не написана. Напишите в «Помощь».",
    "help": "🎧 <b>Центр помощи</b>\n\nЕсть вопрос или проблема? Напишите администратору, ответим быстро 👇",
    "btn_write_support": "Написать @{support}", "btn_topup_now": "Пополнить баланс",
    "stale_button": "Эта кнопка устарела. Нажмите /start.",
})
TEXTS["en"].update({
    "menu_subs": "Subscriptions", "menu_topup": "Top up", "menu_orders": "My orders",
    "menu_profile": "Profile", "menu_guide": "Guide", "menu_help": "Help",
    "hello": (
        "<b>Hi, {name}!</b> 👋\n\n"
        "The most useful premium subscriptions in one place 💎\n"
        "⚡ Fast  ·  🛡 Warranty  ·  💳 Easy payment"
    ),
    "choose_sub": "<b>Choose a subscription</b> 👇",
    "sub_unavailable": "😔 This subscription is temporarily out of stock. It will be back soon.",
    "brand_empty": "No subscriptions in this section yet. Coming soon.",
    "all_sold_out": "🔴 Everything is out of stock for now, back soon.",
    "choose_plan": "{brand}\n\n📋 Choose a plan:",
    "plan_card": "💎 <b>{name}</b>\n\n{description}\n\n💵 Price: <b>{price}</b>\n💳 Your balance: <b>{balance}</b>",
    "btn_confirm_buy": "Buy", "btn_back": "⬅️ Back",
    "ask_email": "📧 Send the <b>email</b> to attach the subscription to:",
    "ask_accounts": "🔑 Send <b>{n}</b> account details (one per line):",
    "bad_input": "❌ {why}\n\nSend it again or press /start.",
    "buying": "⏳ Processing your order, please wait...",
    "order_success": (
        "✅ <b>Order #{order_id} is ready!</b>\n\n"
        "💵 Paid: <b>{total}</b>\n"
        "💳 Balance left: <b>{balance}</b>\n\n"
        "{delivery}\n\n"
        "🎉 Thank you for your purchase!"
    ),
    "topup_title": "💳 <b>Top up balance</b>\n\nChoose a convenient amount 👇",
    "orders_empty": "📦 You have no orders yet.\n\n🛍 Get your first subscription in «Subscriptions»!",
    "orders_title": "📦 <b>Your orders</b>",
    "profile": "👤 <b>My profile</b>\n\n🆔 ID: <code>{id}</code>\n🙍 Name: {name}\n💳 Balance: <b>{balance}</b>\n🌐 Language: {language}",
     "lang_changed": "✅ Language changed.",
    "guide_choose": "📚 <b>Guide</b>\n\nWhich subscription do you need a guide for?",
    "guide_none": "No guide for this subscription yet. Please contact «Help».",
    "help": "🎧 <b>Help center</b>\n\nHave a question or a problem? Write to the administrator, we reply fast 👇",
    "btn_write_support": "Write @{support}", "btn_topup_now": "Top up",
    "stale_button": "This button is outdated. Press /start.",
})


def t(lang: str, key: str, **kwargs) -> str:
    """Matnni tilga qarab qaytaradi."""
    table = TEXTS.get(lang) or TEXTS["uz"]
    raw = table.get(key) or TEXTS["uz"].get(key, key)
    return raw.format(**kwargs) if kwargs else raw


def money(amount: int) -> str:
    """50000 -> '50 000 so'm'"""
    return f"{amount:,}".replace(",", " ") + " so'm"
