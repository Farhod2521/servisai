"""referral program and rewards

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Taklif havolasi kodi (birinchi so‘ralganda yaratiladi) va kim taklif qilgani
    op.add_column('users', sa.Column('referral_code', sa.String(length=16), nullable=True))
    op.create_index('ix_users_referral_code', 'users', ['referral_code'], unique=True)
    op.add_column('users', sa.Column('referred_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_referred_by', 'users', 'users', ['referred_by_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_users_referred_by_id', 'users', ['referred_by_id'])

    # Saytdan Telegram orqali kirishda taklif kodi bot tasdiqlaguncha shu yerda saqlanadi
    op.add_column('telegram_login_sessions', sa.Column('ref_code', sa.String(length=16), nullable=True))

    op.create_table(
        'referral_rewards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('required_friends', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.String(length=64), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('required_friends >= 1', name='ck_rewards_friends_positive'),
        sa.CheckConstraint('quantity >= 1', name='ck_rewards_quantity_positive'),
    )
    op.create_table(
        'reward_grants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reward_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reward_id'], ['referral_rewards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        # Har bir sovg‘a bir foydalanuvchiga bir marta beriladi
        sa.UniqueConstraint('user_id', 'reward_id', name='uq_reward_grants_user_reward'),
    )


def downgrade() -> None:
    op.drop_table('reward_grants')
    op.drop_table('referral_rewards')
    op.drop_column('telegram_login_sessions', 'ref_code')
    op.drop_index('ix_users_referred_by_id', table_name='users')
    op.drop_constraint('fk_users_referred_by', 'users', type_='foreignkey')
    op.drop_column('users', 'referred_by_id')
    op.drop_index('ix_users_referral_code', table_name='users')
    op.drop_column('users', 'referral_code')
