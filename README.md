# servisai

AI va premium servislar do‘koni: **Next.js** frontend + **FastAPI** backend + **PostgreSQL** + **Telegram bot**.

```
servisai-front/   Next.js 16 (sayt, kirish oynasi, profil)
servisai-back/    FastAPI API, Alembic migratsiyalar, aiogram bot
docker-compose.yml
```

## Docker bilan ishga tushirish

```bash
cp .env.example .env      # GOOGLE_CLIENT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME, SECRET_KEY ni to‘ldiring
docker compose up -d --build
```

| Servis     | Manzil                              |
| ---------- | ----------------------------------- |
| Sayt       | http://localhost:3000               |
| API        | http://localhost:8000/api           |
| API hujjat | http://localhost:8000/api/docs      |

`backend` konteyneri ishga tushganda migratsiyalarni (`alembic upgrade head`) va mahsulotlar seed’ini avtomatik bajaradi.
`bot` konteyneri Telegram botni long-polling rejimida ishlatadi.

## Tizimga kirish

Saytdagi **«Tizimga kirish»** tugmasi oynani ochadi, unda ikki usul bor. Hisob bo‘lmasa — avtomatik ro‘yxatdan o‘tadi.

- **Google** — Google Identity Services tugmasi `credential` (ID token) qaytaradi, backend uni `GOOGLE_CLIENT_ID` bilan tekshiradi.
  Google Cloud Console’da OAuth client’ning *Authorized JavaScript origins* ro‘yxatiga sayt manzilini qo‘shing.
- **Telegram bot** — sayt `POST /api/auth/telegram/init` dan bir martalik token oladi va `t.me/<bot>?start=<token>` ni ochadi.
  Foydalanuvchi botda START bosganda bot foydalanuvchini yaratadi/topadi va tokenni tasdiqlaydi; sayt
  `GET /api/auth/telegram/status/<token>` ni so‘rab turib JWT oladi. Bot ixtiyoriy ravishda telefon raqamini ham so‘raydi.

Profil sahifasida bir hisobga ikkala usulni ham ulash mumkin («Kirish usullari» → «Ulash»).

## Hisob (balans)

1. Mijoz **Profil → Hisobim** bo‘limida `PAYMENT_CARD_NUMBER` kartasiga pul o‘tkazadi, summani yozib chek rasmini yuklaydi.
2. Chek `TELEGRAM_ADMIN_CHAT_ID` chatiga **«✅ Tasdiqlash / ❌ Rad etish»** tugmalari bilan boradi.
3. Admin (`ADMIN_TELEGRAM_IDS` dagi yoki `TELEGRAM_ADMIN_CHAT_ID` ning o‘zi) tasdiqlasa — summa hisobga tushadi, mijozga botdan xabar boradi.
4. «Sotib olish» narxni hisobdan yechadi (buyurtma darhol «To‘landi» bo‘ladi). Admin buyurtmani bekor qilsa, pul hisobga qaytadi.

Har bir kirim/chiqim `transactions` jadvalida saqlanadi, cheklar `media` volume’ida. Botda `/balans` buyrug‘i bor.

## Profil (`/profil`)

- **Hisobim** — balans, to‘ldirish (karta + chek), so‘rovlar holati, kirim/chiqim tarixi.
- **Profil** — statistika (jami/faol/bajarilgan buyurtmalar, jami xarid), ism va telefonni tahrirlash, kirish usullari.
- **Mening buyurtmalarim** — status bo‘yicha filtr, har bir buyurtmaning tarixi (timeline), faollashtirish ma’lumotlari, bekor qilish.
- **Buyurtmalar tarixi** — barcha buyurtmalar bo‘yicha voqealar lentasi.

Mahsulot sahifasidagi **«Sotib olish»** tugmasi narxni hisobdan yechib buyurtma yaratadi (kirilmagan bo‘lsa — avval kirish oynasi, mablag‘ yetmasa — «Hisobni to‘ldirish»).
Mijozga va `TELEGRAM_ADMIN_CHAT_ID` ga Telegram orqali xabar boradi.

## API

| Metod | Yo‘l | Tavsif |
| ----- | ---- | ------ |
| GET   | `/api/auth/config` | Yoqilgan kirish usullari |
| POST  | `/api/auth/google` | Google orqali kirish |
| POST  | `/api/auth/google/link` | Profilga Google ulash |
| POST  | `/api/auth/telegram/init` | Telegram kirish tokeni (token bilan chaqirilsa — ulash) |
| GET   | `/api/auth/telegram/status/{token}` | Tasdiqlanganini tekshirish, JWT qaytaradi |
| GET/PATCH | `/api/users/me` | Profil |
| GET   | `/api/users/me/stats` | Statistika |
| GET   | `/api/products` | Mahsulotlar |
| GET/POST | `/api/orders` | Buyurtmalar ro‘yxati (`?status=`) / yangi buyurtma |
| GET   | `/api/orders/history` | Barcha buyurtmalar tarixi |
| GET   | `/api/orders/{id}` | Buyurtma va uning tarixi |
| POST  | `/api/orders/{id}/cancel` | Bekor qilish (faqat `pending`) |
| PATCH | `/api/admin/orders/{id}` | Admin: status/izoh/faollashtirish ma’lumoti (bekor qilinsa pul qaytadi) |
| GET   | `/api/wallet` | Balans va karta rekvizitlari |
| GET/POST | `/api/wallet/topups` | To‘ldirish so‘rovlari / yangi so‘rov (`amount` + `receipt` fayl) |
| GET   | `/api/wallet/transactions` | Hisob tarixi |
| POST  | `/api/admin/topups/{id}` | Admin: `{"approve": true}` (odatda Telegram tugmasi orqali) |

Adminlar `ADMIN_EMAILS` / `ADMIN_TELEGRAM_IDS` orqali belgilanadi (keyingi kirishda `is_admin` bo‘ladi).
Statuslar: `pending` → `paid` → `processing` → `completed` (yoki `cancelled`).

## Docker’siz ishlab chiqish

```bash
# Backend
cd servisai-back
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # DATABASE_URL lokal PostgreSQL’ga
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload      # API
python -m app.bot                  # bot (alohida terminalda)

# Frontend
cd servisai-front
npm install
npm run dev                        # /api so‘rovlari http://localhost:8000 ga yo‘naltiriladi (BACKEND_URL)
```

Yangi migratsiya: `alembic revision --autogenerate -m "..."`.
