"""product sold_base: starting purchase count shown on the site

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Saytdagi boshlang‘ich "sotib olganlar" soni; haqiqiy xaridlar shu songa qo‘shilib boradi
START = {"chatgpt-plus": 23, "capcut-pro": 45, "gemini-advanced": 84}


def upgrade() -> None:
    op.add_column('products', sa.Column('sold_base', sa.Integer(), server_default='0', nullable=False))
    for product_id, base in START.items():
        op.execute(sa.text("UPDATE products SET sold_base = :base WHERE id = :id").bindparams(base=base, id=product_id))


def downgrade() -> None:
    op.drop_column('products', 'sold_base')
