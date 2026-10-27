"""product stock

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL — cheklanmagan; mavjud mahsulotlar admin son kiritguncha sotuvda qoladi
    op.add_column('products', sa.Column('stock', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_products_stock_non_negative', 'products', 'stock >= 0')


def downgrade() -> None:
    op.drop_constraint('ck_products_stock_non_negative', 'products', type_='check')
    op.drop_column('products', 'stock')
