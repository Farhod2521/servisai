"""Veb-server: to'lov webhooklari (Payme/Click/SMS), mahsulot rasmlari va health-check. Mini App yo'q."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiohttp import web

from config import settings
from webapp.payments_api import add_routes as add_payment_routes
from webapp.sessiya_web import add_routes as add_sessiya_routes

log = logging.getLogger("uzshop.web")


async def _product_image(request: web.Request) -> web.Response:
    """Admin yuklagan mahsulot rasmi (ommaviy: rasm maxfiy emas; ?v= o'zgarsa yangilanadi)."""
    from database.db import SessionMaker
    from database.models import ProductImage

    try:
        pid = int(request.match_info["pid"])
    except ValueError:
        raise web.HTTPNotFound()
    async with SessionMaker() as s:
        img = await s.get(ProductImage, pid)
    if not img:
        raise web.HTTPNotFound()
    return web.Response(body=img.data, content_type=img.mime or "image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


def setup_webapp(app: web.Application, bot: Bot) -> None:
    """Mavjud aiohttp ilovaga to'lov webhooklari va mahsulot rasmi marshrutlarini qo'shadi."""
    app["bot"] = bot
    add_payment_routes(app)
    add_sessiya_routes(app)
    app.router.add_get("/media/p/{pid}", _product_image)


async def start_web_server(bot: Bot) -> web.AppRunner:
    """Polling rejimida to'lov webhooklari uchun alohida server ishga tushiradi."""
    app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/healthz", health)
    setup_webapp(app, bot)
    runner = web.AppRunner(app)
    await runner.setup()
    # Kompyuterda (public URL yo'q) — faqat shu kompyuter uchun: Windows tarmoq (firewall) so'rovi chiqmaydi
    host = "0.0.0.0" if settings.public_url else "127.0.0.1"
    await web.TCPSite(runner, host, settings.port).start()
    log.info("Veb-server: http://%s:%s", host, settings.port)
    return runner
