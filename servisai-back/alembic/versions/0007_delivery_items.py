"""delivery items: per-buyer unique links/codes

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'delivery_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.String(length=64), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        # NULL — hali hech kimga berilmagan
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_delivery_items_product_free', 'delivery_items', ['product_id', 'order_id'])
    op.create_index('ix_delivery_items_order_id', 'delivery_items', ['order_id'])
    # Hammaga bir xil matn berish o‘rniga endi har xaridorga alohida element beriladi
    op.drop_column('products', 'auto_delivery')
    # Elementlari hali yo‘q avtomatik mahsulotlar admin qo‘shguncha qo‘lda yetkaziladi
    op.execute("UPDATE products SET delivery_mode = 'manual' WHERE delivery_mode = 'auto'")


def downgrade() -> None:
    op.add_column('products', sa.Column('auto_delivery', sa.Text(), nullable=True))
    op.drop_index('ix_delivery_items_order_id', table_name='delivery_items')
    op.drop_index('ix_delivery_items_product_free', table_name='delivery_items')
    op.drop_table('delivery_items')
