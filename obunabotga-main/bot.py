"""Kirish nuqtasi.

Ikki rejimda ishlaydi:
  • Polling  — .env da WEBHOOK_URL bo'sh bo'lsa (kompyuterda sinash uchun)
  • Webhook  — WEBHOOK_URL berilsa (Render, VPS va boshqa hosting uchun)

Ishga tushirish: python bot.py
"""
from __future__ import annotations

import asyncio
import os
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import settings
from database.db import init_db
from handlers import admin, admin_api, admin_ext, admin_quick, admin_shop, admin_tg, admin_guide, admin_brand, business, sessiya, pay, shop, start, tgstars
from middlewares.emoji_fallback import custom_emoji_fallback, premium_emoji
from services import runtime
from services import alerts, alerts_bot, backup, cardbridge
from services.catalog_sync import periodic_sync
from middlewares.reset_state import ResetStateOnCommand
from middlewares.subscription import SubscriptionMiddleware
from middlewares.user import UserMiddleware
from webapp.server import setup_webapp, start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("uzshop")

WEBHOOK_PATH = "/telegram/webhook"


def make_bot() -> Bot:
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Premium emoji yuborilmasa — oddiy emoji bilan qayta yuboriladi
    bot.session.middleware(premium_emoji)            # tashqi: oddiy emojini premium bilan almashtiradi
    bot.session.middleware(custom_emoji_fallback)    # ichki: rad etilsa oddiy emoji bilan qayta yuboradi
    return bot


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    # /start va boshqa buyruqlar admin panelning kutish holatida qolib ketmasin
    dp.message.outer_middleware(ResetStateOnCommand())
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    # Majburiy obuna — foydalanuvchi aniqlangandan keyin tekshiriladi
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    # Admin router birinchi — uning FSM holatlari ustunlikka ega
    dp.include_routers(
        admin.router,      # admin panel (FSM holatlari ustunlikka ega)
        admin_ext.router,  # admin: foyda/kurs, buyurtmalar, foydalanuvchilar, premium emoji
        admin_shop.router,  # admin: narxlar, qo'llanma, xabarnomalar
        admin_api.router,  # admin: API ro'yxatidan mahsulot qo'shish/olib tashlash
        admin_brand.router,  # admin: har brend uchun o'z foyda foizi
        admin_guide.router,  # admin panel qo'llanmasi (har tugma nima qiladi)
        business.router,   # Telegram Business ko'prigi: akkauntga ulangan bot @HUMOcardbot xabarlarini o'qiydi
        sessiya.router,    # owner: Telegram sessiyasini botning o'zida olish (/sessiya)
        admin_tg.router,   # admin: Stars/Premium (StarsUno) holati va ustamasi
        admin_quick.router,  # admin: tezkor amallar — majburiy obuna, ID bilan hisob to'ldirish
        pay.router,        # avtomatik to'lov: mijoz buyurtmasi va to'lov administratori (faqat owner ID)
        shop.router,       # oddiy do'kon: obunalar, buyurtmalar, profil, qo'llanma, yordam
        tgstars.router,    # Telegram Stars va Premium (StarsUno); shop'dan keyin: pastki menyu tugmalari ustun
        start.router,      # /start, obuna tekshirish
        start.fallback,    # qolgan hamma narsa → Mini App
    )
    dp.errors.register(on_error)
    return dp


async def on_error(event) -> bool:
    """Kutilmagan xato: logga to'liq yoziladi, foydalanuvchi esa jim qolmaydi."""
    upd = event.update
    log.error("Yangilanishni qayta ishlashda xato (update_id=%s)", upd.update_id, exc_info=event.exception)
    try:
        if upd.message:
            await upd.message.answer("⚠️ Vaqtincha xatolik yuz berdi. Birozdan so'ng /start ni qayta bosing.")
        elif upd.callback_query:
            await upd.callback_query.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko'ring.", show_alert=True)
    except Exception:  # noqa: BLE001
        pass
    return True


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="🤖 Servis AI — AI obunalar, Stars va Premium"),
        BotCommand(command="topup", description="💳 Hisobni to'ldirish"),
        BotCommand(command="hisob", description="👤 Profil va hisobim"),
    ])
    if settings.bot_name:   # faqat BOT_NAME berilsa va farq qilsa (Telegram tez-tez o'zgartirishni cheklaydi)
        try:
            if (await bot.get_my_name()).name != settings.bot_name:
                await bot.set_my_name(settings.bot_name)
        except Exception as ex:  # noqa: BLE001
            log.warning("Bot nomini o'rnatib bo'lmadi: %s", ex)
    try:   # Mini App yo'q: chat pastidagi menyu tugmasi oddiy buyruqlar ro'yxatini ochadi
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    except Exception as ex:  # noqa: BLE001
        log.warning("Menyu tugmasini o'rnatib bo'lmadi: %s", ex)
    if runtime.force_sub_channels():
        log.info("Majburiy obuna yoqilgan: %s", ", ".join(runtime.force_sub_channels()))
    if not settings.admins:
        log.warning("Admin yo'q: admin panel hech kimga ochilmaydi (ADMIN_IDS / EXTRA_ADMIN_IDS ni tekshiring).")


async def warn_if_temp_db(bot: Bot) -> None:
    """Render'da SQLite ishlatilsa — baza har deployda o'chadi (foydalanuvchilar, balans, buyurtmalar, karta sozlamasi). Ownerga ogohlantirish."""
    if settings.is_postgres or not os.environ.get("RENDER"):
        return
    log.warning("DIQQAT: Render'da SQLite — ma'lumotlar har deployda o'chadi. DATABASE_URL ga Postgres ulang!")
    if not settings.owner_id:
        return
    try:
        await bot.send_message(
            settings.owner_id,
            "ℹ️ <b>Baza vaqtinchalik (SQLite)</b>\n\nRender'da har deployda fayl o'chadi, shuning uchun bot bazani shu chatda "
            "<b>pinlangan zaxira faylida</b> saqlaydi va yangi deployda o'zi tiklaydi (hisoblar, buyurtmalar, sozlamalar). "
            "Zaxira faylini o'chirmang va pindan olmang.\n\n"
            "Eng ishonchli yo'l — doimiy Postgres (neon.tech yoki Render Postgres): Render → Environment → <code>DATABASE_URL</code>.")
    except Exception:  # noqa: BLE001
        pass


async def run_polling() -> None:
    """Kompyuterda ishlatish uchun. Terminal ochiq turgan vaqtda ishlaydi."""
    await init_db()
    bot = make_bot()
    await backup.restore_if_empty(bot)       # bo'sh baza bo'lsa — ownerning pinlangan zaxirasidan tiklaydi
    await runtime.load()
    await runtime.apply_migrations()
    dp = build_dispatcher()

    await set_commands(bot)
    me = await bot.get_me()
    log.info("Bot ishga tushdi (polling): @%s", me.username)

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(periodic_sync(bot))
    asyncio.create_task(backup.run(bot))           # baza zaxirasi (ownerning shaxsiy chatida)
    cardbridge.start(bot)      # CardXabarBot ko'prigi (sozlangan bo'lsa)
    asyncio.create_task(cardbridge.sweeper())
    runner = await start_web_server(bot)   # Mini App (WEBAPP_URL ga tunnel/hosting ulanadi)
    try:
        await dp.start_polling(bot)
    finally:
        await backup.final_backup(bot)       # to'xtashdan oldin oxirgi holat (papkaga va Telegram'ga)
        await runner.cleanup()


def run_webhook() -> None:
    """Hosting uchun. Telegram yangiliklarni o'zi shu manzilga yuboradi."""
    bot = make_bot()
    dp = build_dispatcher()

    async def on_startup(app: web.Application) -> None:
        await init_db()
        await backup.restore_if_empty(bot)   # yangi deployda baza bo'sh — zaxiradan tiklaymiz (hisobdagi pullar saqlanadi)
        await runtime.load()
        await runtime.apply_migrations()
        try:
            await set_commands(bot)
        except Exception as ex:  # noqa: BLE001 — buyruqlar ro'yxati botni to'xtatmasin
            log.warning("Buyruqlarni o'rnatib bo'lmadi: %s", ex)
        url = settings.public_url + WEBHOOK_PATH
        # Telegram vaqtincha javob bermasa ham server yiqilmasin — bir necha marta urinamiz
        for attempt in range(1, 6):
            try:
                await bot.set_webhook(
                    url,
                    drop_pending_updates=True,
                    secret_token=settings.webhook_secret or None,
                    allowed_updates=dp.resolve_used_update_types(),
                )
                me = await bot.get_me()
                log.info("Bot ishga tushdi (webhook): @%s → %s", me.username, url)
                break
            except Exception as ex:  # noqa: BLE001
                log.error("Webhook o'rnatilmadi (%d/5): %s | manzil=%s", attempt, ex, url)
                if attempt == 5:
                    raise
                await asyncio.sleep(3 * attempt)
        app["catalog_task"] = asyncio.create_task(periodic_sync(bot))
        app["db_warn_task"] = asyncio.create_task(warn_if_temp_db(bot))
        app["backup_task"] = asyncio.create_task(backup.run(bot))
        app["card_task"] = cardbridge.start(bot)       # bridge xatosi botni yiqitmaydi
        app["sweep_task"] = asyncio.create_task(cardbridge.sweeper())
        app["alert_task"] = asyncio.create_task(alerts_bot.start(bot))     # hisobot boti: webhook + «ulandi» xabari
        app["alert_daily"] = asyncio.create_task(alerts_bot.daily_loop(bot))   # har kuni 23:55 kunlik hisobot

    async def on_shutdown(app: web.Application) -> None:
        await backup.final_backup(bot)       # to'xtashdan oldin (deploy) oxirgi holat zaxiraga yoziladi
        for name in ("catalog_task", "card_task", "sweep_task", "backup_task", "alert_daily"):
            task = app.get(name)
            if task:
                task.cancel()
        await alerts.close()
        await bot.session.close()

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", health)        # Render health check shu manzilni so'raydi
    app.router.add_get("/healthz", health)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    SimpleRequestHandler(
        dispatcher=dp, bot=bot,
        secret_token=settings.webhook_secret or None,
    ).register(app, path=WEBHOOK_PATH)
    alerts_bot.setup(app)                  # hisobot boti webhooki (token berilgan bo'lsa)
    setup_webapp(app, bot)                 # Mini App: /app/ va /api/*
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=settings.port)


def main() -> None:
    if settings.public_url:
        run_webhook()
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        log.info("To'xtatildi.")
