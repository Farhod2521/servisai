"""announcements (news banners shown as a popup on the site)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        # referral — "N ta do‘stingizni taklif qiling" (sovg‘a va progress bilan), custom — oddiy e’lon
        sa.Column('kind', sa.String(length=16), server_default='custom', nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        # Sarlavhaning ko‘k rangdagi ikkinchi qatori
        sa.Column('highlight', sa.String(length=255), server_default='', nullable=False),
        sa.Column('subtitle', sa.String(length=255), server_default='', nullable=False),
        sa.Column('text', sa.Text(), server_default='', nullable=False),
        sa.Column('button_text', sa.String(length=64), server_default='', nullable=False),
        sa.Column('button_url', sa.String(length=512), server_default='', nullable=False),
        sa.Column('image_url', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # Avvalgi "do‘st taklif qiling" oynasi endi shu e’lon sifatida boshqariladi
    op.execute(
        "INSERT INTO announcements (kind, title, highlight, subtitle, text, button_text, is_active) VALUES "
        "('referral', '{n} ta do‘stingizni', 'taklif qiling', '{product} akkauntini BEPUL oling!', "
        "'Do‘stlaringiz havolangiz orqali ro‘yxatdan o‘tsin — {n} ta taklifdan so‘ng sovg‘angizni qo‘lga kiriting.', "
        "'Taklif havolasini olish', true)"
    )


def downgrade() -> None:
    op.drop_table('announcements')
