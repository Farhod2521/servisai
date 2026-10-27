"""product delivery settings

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # manual — admin qo‘lda yetkazadi; auto — xariddan so‘ng auto_delivery matni darhol beriladi
    op.add_column('products', sa.Column('delivery_mode', sa.String(length=16), server_default='manual', nullable=False))
    op.add_column('products', sa.Column('delivery_time', sa.String(length=64), server_default='10 daqiqa – 1 soat', nullable=False))
    op.add_column('products', sa.Column('auto_delivery', sa.Text(), nullable=True))
    # Servis sahifasidagi "Muhim ma’lumot" (qoidalar, kafolat shartlari)
    op.add_column('products', sa.Column('notes', sa.Text(), server_default='', nullable=False))
    # Gemini avtomatik beriladi (havolani admin paneldan kiritish kerak, bo‘lmasa qo‘lda yetkaziladi)
    op.execute("UPDATE products SET delivery_mode = 'auto' WHERE id = 'gemini-advanced'")


def downgrade() -> None:
    op.drop_column('products', 'notes')
    op.drop_column('products', 'auto_delivery')
    op.drop_column('products', 'delivery_time')
    op.drop_column('products', 'delivery_mode')
