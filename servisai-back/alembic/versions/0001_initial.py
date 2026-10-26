"""initial

Revision ID: 0001
Revises: 
Create Date: 2026-10-26 12:49:53.293033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('products',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('old_price', sa.Integer(), nullable=True),
    sa.Column('durations', postgresql.ARRAY(sa.Integer()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('avatar_url', sa.String(length=512), nullable=True),
    sa.Column('google_id', sa.String(length=64), nullable=True),
    sa.Column('telegram_id', sa.BigInteger(), nullable=True),
    sa.Column('telegram_username', sa.String(length=64), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=64), nullable=True),
    sa.Column('product_name', sa.String(length=255), nullable=False),
    sa.Column('duration_months', sa.Integer(), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'paid', 'processing', 'completed', 'cancelled', name='order_status'), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('delivery_info', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)
    op.create_table('telegram_login_sessions',
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('status', sa.Enum('pending', 'confirmed', 'used', name='telegram_login_status'), nullable=False),
    sa.Column('link_user_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=255), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['link_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token')
    )
    op.create_table('order_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'paid', 'processing', 'completed', 'cancelled', name='order_status'), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_events_order_id'), 'order_events', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_events_order_id'), table_name='order_events')
    op.drop_table('order_events')
    op.drop_table('telegram_login_sessions')
    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_users_telegram_id'), table_name='users')
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('products')
    sa.Enum(name='order_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='telegram_login_status').drop(op.get_bind(), checkfirst=True)
