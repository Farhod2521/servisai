"""order quantity

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Avvalgi buyurtmalar bittadan bo‘lgan; orders.price — jami to‘langan summa (narx × soni)
    op.add_column('orders', sa.Column('quantity', sa.Integer(), server_default='1', nullable=False))
    op.create_check_constraint('ck_orders_quantity_positive', 'orders', 'quantity >= 1')


def downgrade() -> None:
    op.drop_constraint('ck_orders_quantity_positive', 'orders', type_='check')
    op.drop_column('orders', 'quantity')
