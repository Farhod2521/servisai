"""duration unit (day/month) for products and orders

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # month — "1 oy" obunalar (avvalgi hamma mahsulotlar), day — "1 kun" (masalan, API kalitlar)
    op.add_column('products', sa.Column('duration_unit', sa.String(length=8), server_default='month', nullable=False))
    # Buyurtma vaqtidagi birlik saqlanadi (orders.duration_months shu birlikdagi son)
    op.add_column('orders', sa.Column('duration_unit', sa.String(length=8), server_default='month', nullable=False))


def downgrade() -> None:
    op.drop_column('orders', 'duration_unit')
    op.drop_column('products', 'duration_unit')
