"""product details for admin panel

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Avval frontend katalogida turgan ma’lumotlar endi bazada saqlanadi
EXISTING = {
    "chatgpt-plus": ("chat", "popular", 1, [
        "GPT-4o va eng yangi OpenAI modellariga kirish",
        "DALL-E bilan rasm yaratish",
        "Advanced Data Analysis — fayl va jadvallarni tahlil qilish",
        "Custom GPT’lar yaratish va ishlatish",
        "Ovozli suhbat rejimi",
        "Bepul versiyaga nisbatan yuqori limitlar",
    ]),
    "capcut-pro": ("design", "popular", 2, [
        "Barcha Pro shablon va effektlar",
        "AI video tahrirlash vositalari",
        "Suv belgisisiz eksport",
        "4K sifatda eksport",
        "Avtomatik subtitrlar",
        "Bulutli xotira",
    ]),
    "gemini-advanced": ("chat", "new", 3, [
        "Gemini 1.5 Pro — Google’ning eng kuchli modeli",
        "1 million tokengacha kontekst",
        "2TB Google One bulutli xotirasi",
        "Gmail, Docs va Sheets ichida Gemini",
        "Uzun hujjat va kodlarni tahlil qilish",
        "18 oy davomida to‘liq imkoniyatlar",
    ]),
}


def upgrade() -> None:
    op.add_column('products', sa.Column('category', sa.String(length=32), server_default='other', nullable=False))
    op.add_column('products', sa.Column('badge', sa.String(length=16), nullable=True))
    op.add_column('products', sa.Column('features', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False))
    op.add_column('products', sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False))

    products = sa.table(
        'products',
        sa.column('id', sa.String),
        sa.column('category', sa.String),
        sa.column('badge', sa.String),
        sa.column('sort_order', sa.Integer),
        sa.column('features', postgresql.ARRAY(sa.Text())),
    )
    for product_id, (category, badge, sort_order, features) in EXISTING.items():
        op.execute(
            products.update()
            .where(products.c.id == product_id)
            .values(category=category, badge=badge, sort_order=sort_order, features=features)
        )


def downgrade() -> None:
    op.drop_column('products', 'sort_order')
    op.drop_column('products', 'features')
    op.drop_column('products', 'badge')
    op.drop_column('products', 'category')
