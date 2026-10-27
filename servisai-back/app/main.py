from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import admin, auth, orders, products, referrals, users, wallet

app = FastAPI(title="servisai.uz API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

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


@api.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


app.include_router(api)
