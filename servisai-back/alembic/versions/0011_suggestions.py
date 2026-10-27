"""suggestions: user ideas/requests with admin replies

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'suggestions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('reply', sa.Text(), nullable=True),
        sa.Column('replied_by', sa.String(length=255), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        # Foydalanuvchi javobni saytda ko‘rdimi (ko‘rmagan bo‘lsa vidjetda belgi chiqadi)
        sa.Column('reply_seen', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_suggestions_user_id', 'suggestions', ['user_id'])
    op.create_index('ix_suggestions_created_at', 'suggestions', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_suggestions_created_at', table_name='suggestions')
    op.drop_index('ix_suggestions_user_id', table_name='suggestions')
    op.drop_table('suggestions')
