"""product logo_url (uploaded image)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL — saytdagi standart (chizilgan yoki harfli) logo ishlatiladi
    op.add_column('products', sa.Column('logo_url', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'logo_url')
