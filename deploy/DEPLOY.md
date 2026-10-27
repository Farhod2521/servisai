# servisai.uz — serverga joylash

Server: `185.74.5.15` · Domenlar: `servisai.uz` (sayt), `api.servisai.uz` (API)

```
Internet ──► nginx :80/:443 ──┬─ servisai.uz        ──► 127.0.0.1:3101  (frontend, Next.js)
                              │   servisai.uz/api/  ──► 127.0.0.1:8101  (backend, FastAPI)
                              └─ api.servisai.uz    ──► 127.0.0.1:8101
                                                         + bot (Telegram polling), db (PostgreSQL) — tashqariga ochilmaydi
```

Docker portlari faqat `127.0.0.1` da ochiladi, shuning uchun serverdagi boshqa loyihalarga xalaqit bermaydi va internetga
to‘g‘ridan-to‘g‘ri chiqmaydi. Port raqamlari `.env` da (`FRONTEND_PORT`, `BACKEND_PORT`) — band bo‘lsa boshqasini tanlang.

## 0. Kerak bo‘ladi

- Docker va Docker Compose plagini: `docker compose version`
- nginx va certbot: `sudo apt install nginx certbot python3-certbot-nginx`
- DNS: `servisai.uz` va `api.servisai.uz` → `185.74.5.15` (Cloudflare’da «DNS only» — tayyor)

## 1. Portlar bo‘shligini tekshirish

```bash
sudo ss -ltnp | grep -E ':3101|:8101' || echo "bo‘sh"
```

Band bo‘lsa, `.env` va `deploy/nginx/servisai.conf` dagi portlarni bir xil qilib o‘zgartiring.

## 2. Kodni olish

```bash
sudo mkdir -p /opt/servisai && sudo chown $USER /opt/servisai
git clone https://github.com/Farhod2521/servisai.git /opt/servisai
cd /opt/servisai
```

## 3. `.env`

```bash
cp deploy/env.production.example .env
openssl rand -hex 32   # -> SECRET_KEY
openssl rand -hex 16   # -> POSTGRES_PASSWORD
nano .env              # <...> joylarini to‘ldiring
```

## 4. Ishga tushirish

```bash
docker compose up -d --build
docker compose ps                         # 4 ta konteyner: db, backend, bot, frontend
curl -s http://127.0.0.1:8101/api/health  # {"status":"ok"}
curl -sI http://127.0.0.1:3101 | head -1  # HTTP/1.1 200 OK
```

Backend birinchi ishga tushganda bazani o‘zi yaratadi (migratsiyalar) va katalogni yozadi:
`servisai-back/app/seed_catalog.json` dagi barcha mahsulotlar (tavsif, narx, soni, boshlang‘ich sotuvlar) va sovg‘a qoidalari.
Keyingi ishga tushishlarda mavjud mahsulotlarga tegilmaydi — ular admin paneldan tahrirlanadi.

> Avtomatik mahsulotlarning havolalari (masalan, Gemini) maxfiy bo‘lgani uchun faylga kirmaydi — serverda
> Admin → Mahsulotlar → «🔗 Havolalar» orqali qayta qo‘shing. Foydalanuvchilar va buyurtmalar ham ko‘chmaydi
> (ularni ko‘chirish kerak bo‘lsa — pastdagi «Kompyuterdagi ma’lumotlarni serverga ko‘chirish» bo‘limi).

Katalogni lokal bazadan yangilash (keyinroq yangi mahsulotlar qo‘shilsa) — `seed_catalog.json` ni qayta eksport qilib commit qiling.

> **Telegram bot faqat bitta joyda ishlay oladi.** Serverda ishga tushgach, kompyuteringizdagi botni to‘xtating:
> `docker compose stop bot` — aks holda ikkalasi «Conflict: terminated by other getUpdates» xatosi bilan bir-biriga xalaqit beradi.

## 5. nginx

```bash
sudo cp deploy/nginx/servisai-proxy.conf /etc/nginx/snippets/
sudo cp deploy/nginx/servisai.conf /etc/nginx/sites-available/servisai.conf
sudo ln -s /etc/nginx/sites-available/servisai.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

> Serverda `sites-available` o‘rniga `/etc/nginx/conf.d/` ishlatilsa: `sudo cp deploy/nginx/servisai.conf /etc/nginx/conf.d/`.

## 6. HTTPS (bepul Let’s Encrypt sertifikati)

```bash
sudo certbot --nginx -d servisai.uz -d api.servisai.uz --redirect
```

certbot 443-port bloklarini qo‘shadi, http → https yo‘naltiradi va sertifikatni o‘zi yangilab turadi.
Firewall yoqilgan bo‘lsa: `sudo ufw allow 'Nginx Full'` (3101/8101 portlarini ochish **shart emas**).

## 7. Tekshirish

- https://servisai.uz — sayt
- https://api.servisai.uz/api/health — `{"status":"ok"}`
- https://api.servisai.uz/api/docs — API hujjatlari
- Telegram’da botga `/start` — menyu chiqishi kerak (endi «🌐 Sayt» tugmasi ham ko‘rinadi)

## Yangilash (yangi kod chiqqanda)

```bash
cd /opt/servisai
git pull
docker compose up -d --build
```

## Kompyuterdagi ma’lumotlarni serverga ko‘chirish (ixtiyoriy)

Mahsulotlar, foydalanuvchilar, buyurtmalar, havolalar va sovg‘alarni ko‘chirish uchun bazani nusxalang.

Kompyuterda:

```bash
docker compose exec -T db pg_dump -U servisai -d servisai -Fc > servisai.dump
scp servisai.dump user@185.74.5.15:/opt/servisai/
```

Serverda (4-qadamdan oldin yoki o‘rniga):

```bash
docker compose up -d db
docker compose exec -T db pg_restore -U servisai -d servisai --clean --if-exists < servisai.dump
docker compose up -d --build
```

## Zaxira nusxa (tavsiya)

Har kuni soat 03:00 da bazaning nusxasini olish (`crontab -e`):

```
0 3 * * * cd /opt/servisai && docker compose exec -T db pg_dump -U servisai -d servisai -Fc > /opt/servisai/backup-$(date +\%F).dump
```

Hisob to‘ldirish cheklari `servisai_media` Docker volume’ida saqlanadi.
