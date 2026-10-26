from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import SessionDep
from ..models import Product
from ..schemas import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(session: SessionDep):
    return (await session.scalars(select(Product).where(Product.is_active).order_by(Product.name))).all()


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, session: SessionDep):
    product = await session.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    return product
