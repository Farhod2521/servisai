# 🛍 Obunalar boti

Telegram'da AI va boshqa obunalarni sotadigan oddiy bot (Mini App yo'q — hammasi botning o'zida).
Obunalar ta'minotchi API'sidan olinadi va **har 3 daqiqada** yangilanadi. Xarid avtomatik: hamyondan
yechiladi → ta'minotchidan sotib olinadi → mijozga yuboriladi.

## Mijoz uchun

`/start` bosganda salom va **«Obunalarni tanlang»** ro'yxati chiqadi. Brend logotiplari premium emoji.
Zaxirasi bor obuna — 🟢 yashil, tugagan — 🔴 qizil tugma.

Ro'yxatdagi obunalar: ChatGPT · Claude · ElevenLabs · CapCut · Runway · Cursor · Seedance · Notion · Railway · Kling
(`handlers/shop.py` → `SERVICES`).

Pastki menyu:

| | |
|---|---|
| **Obunalar** | **Hisobni to'ldirish** |
| **Buyurtmalarim** | **Profil** (ID, balans, til: o'zbek/rus) |
| **Qo'llanma** | **Yordam** (→ @fen1xmedia) |

## Admin panel

Adminlarga pastki menyuda **⚙️ Admin panel** tugmasi chiqadi. Ochilgan **Boshqaruv markazi**da bugungi savdo,
foyda, yangi mijozlar, bajarilmagan buyurtmalar, kutilayotgan to'lovlar va ta'minotchi hamyoni bir qarashda ko'rinadi.
Bosh sahifaning boshida 3 ta tezkor amal: **✅ To'lovlarni tasdiqlash**, **💰 ID bilan hisob to'ldirish**, **📢 Majburiy obuna** (kanal qo'shish/olib tashlash).
Tugmalar rangli: bajarilmagan buyurtma bo'lsa 🧾 tugma qizil bo'ladi.

| Tugma | Ichida nima bor |
|---|---|
| 🧾 **Buyurtmalar** | kutilayotganlarini bajarish, pulni qaytarish |
| 👥 **Mijozlar** | qidirish, balans qo'shish/ayirish, bloklash |
| 🛍 **Obunalar** | mahsulotlar, bo'limlar, qo'shish, zaxira, katalogni yangilash |
| 💰 **Narx va foyda** | narxlar, foyda foizi, USD kursi, ustama jadvali, narx o'zgarishlari |
| 💳 **To'lovlar** | karta sozlamalari, kelgan to'lovlar, statistika, tekshiruv |
| 📣 **Xabarlar** | hammaga xabar, yangi obuna xabari, /start matni |
| 📊 **Hisobotlar** | bugun / 10 kun / 30 kun savdo va foyda, umumiy hisob |
| ⚙️ **Sozlamalar** | yordam username, premium emoji, brend emojilari |

Har bir bo'limda pastda **🏠 Bosh sahifa** tugmasi bor.

## Premium emoji

Menyu va matnlardagi emojilarni premium qilish uchun: **⚙️ Admin panel → ⚙️ Sozlamalar → 😀 Premium emoji** ga chiroyli
emoji-paketning havolasini yuboring (`https://t.me/addemoji/PaketNomi`). Bot kerakli emojilarni (💎 💳 📦 👤 📚 🎧 va boshqalar)
paketdan o'zi topib, ID'larini saqlaydi. Bir necha paket yuborish mumkin. Bot egasida Telegram Premium bo'lishi kerak.
Brend logotiplari (ChatGPT, Claude...) alohida: `services/brand_emoji.py`.

## Qaysi mahsulotlar do'konga qo'yiladi

Ta'minotchi (API) mahsulotlari avtomatik saralanadi (`services/curation.py`):
- **ChatGPT** obunalari: faqat kafolati bor, kamida **10 kun** (10 / 20 / 30 kun yoki to'liq kafolat). Kafolatsiz yoki kafolati ko'rsatilmaganlari qo'yilmaydi.
- **Codex / OpenAI API**: faqat **$100 va $500** lik, kafolati bor (24 soat, 2 kun, 30 kun...). Kafolatsizlari qo'yilmaydi.
- Qolgan brendlar: ChatGPT, Claude, ElevenLabs, CapCut, Runway, Cursor, Seedance, Notion, Railway, Kling.

Admin **⚙️ Admin panel → 🛍 Obunalar → 🌐 API'dan qo'shish** orqali API ro'yxatidagi istalgan mahsulotni (sababi bilan ko'rinadi) qo'lda qo'shadi; u qoidalarga
qaramasdan do'konda chiqadi. Yangi brend bo'lsa, menyuga o'zi qo'shiladi. **📋 Qo'shilganlar** orqali olib tashlanadi. Raqamlarni o'zgartirish: `curation.py` boshida.

## Ishga tushirish (Render)

1. GitHub'ga yuklang → Render → **New → Web Service** → shu repo.
   Build: `pip install -r requirements.txt` · Start: `python bot.py`
2. **Environment** bo'limiga qo'ying (`.env.example` ga qarang). Majburiylari:

| O'zgaruvchi | Nima |
|---|---|
| `BOT_TOKEN` | @BotFather tokeni (**faqat Render'da**, kodga/GitHub'ga yozmang) |
| `ADMIN_IDS` | Admin Telegram ID (sukut: 93758266 va 7330213371). Bir nechta bo'lsa vergul bilan |
| `TELEGRAM_OWNER_ID` | To'lov admini va zaxira egasi (sukut: 93758266) |
| `CANBOSO_API_KEY` | Ta'minotchi API kaliti |
| `DATABASE_URL` | Postgres manzili (tavsiya) |
| `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_OWNER` | Mijozlar to'laydigan karta (yoki admin paneldan) |
| `TG_API_ID`, `TG_API_HASH`, `TG_SESSION` | Bank xabarlarini o'qish uchun (`tools/make_session.py`) |
| `CARD_SOURCES` | Bank xabarnoma boti username'i (sukut: `humocardbot,cardxabarbot`) |
| `ALERT_BOT_TOKEN` | Hisobot boti (ixtiyoriy) |

3. Render Free tarifda bot uxlab qoladi, 24/7 uchun pullik tarif kerak.
4. Baza SQLite bo'lsa, bot zaxirani egasining chatida pinlab saqlaydi va yangi deployda o'zi tiklaydi.

## Testlar

```
python tests/smoke_test.py          # bot oqimi (soxta Telegram bilan)
python tests/test_payments.py       # va boshqa tests/test_*.py
```
