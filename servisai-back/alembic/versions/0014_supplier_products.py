"""supplier (canboso) products: source, external_id, brand, supplier price/meta; order customer input

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-09 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('source', sa.String(length=16), server_default='own', nullable=False))
    op.add_column('products', sa.Column('external_id', sa.String(length=64), nullable=True))
    op.add_column('products', sa.Column('brand', sa.String(length=64), nullable=True))
    op.add_column('products', sa.Column('supplier_price', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('supplier_meta', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.create_unique_constraint('uq_products_external_id', 'products', ['external_id'])
    op.create_index('ix_products_brand', 'products', ['brand'])
    op.add_column('orders', sa.Column('customer_input', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('supplier_ref', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'supplier_ref')
    op.drop_column('orders', 'customer_input')
    op.drop_index('ix_products_brand', table_name='products')
    op.drop_constraint('uq_products_external_id', 'products', type_='unique')
    op.drop_column('products', 'supplier_meta')
    op.drop_column('products', 'supplier_price')
    op.drop_column('products', 'brand')
    op.drop_column('products', 'external_id')
    op.drop_column('products', 'source')
