import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .logos import PUBLIC_FOLDERS, media_dir
from .routers import admin, announcements, auth, orders, products, referrals, suggestions, supplier, users, wallet
from .supplier import client as supplier_client
from .supplier.sync import run_forever as supplier_sync_forever


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Ta’minotchi katalogi fonda yangilanib turadi (kalit .env da bo‘lsa)
    task = asyncio.create_task(supplier_sync_forever(settings.supplier_sync_seconds)) if supplier_client.enabled() else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="servisai.uz API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(users.router)
api.include_router(products.router)
api.include_router(orders.router)
api.include_router(orders.admin_router)
api.include_router(wallet.router)
api.include_router(wallet.admin_router)
api.include_router(admin.router)
api.include_router(referrals.router)
api.include_router(suggestions.router)
api.include_router(suggestions.admin_router)
api.include_router(announcements.router)
api.include_router(announcements.admin_router)
api.include_router(supplier.router)


@api.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


app.include_router(api)
# Faqat logolar va e’lon rasmlari ommaga ochiq (cheklar media/receipts da yopiq qoladi)
for _folder in PUBLIC_FOLDERS:
    app.mount(f"/api/media/{_folder}", StaticFiles(directory=media_dir(_folder)), name=_folder)
