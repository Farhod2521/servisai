"""wallet

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26 13:18:10.637953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('topups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('receipt_path', sa.String(length=255), nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='topup_status'), nullable=False),
    sa.Column('admin_note', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=255), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_topups_status'), 'topups', ['status'], unique=False)
    op.create_index(op.f('ix_topups_user_id'), 'topups', ['user_id'], unique=False)
    op.create_table('transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('topup', 'purchase', 'refund', name='transaction_type'), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('balance_after', sa.BigInteger(), nullable=False),
    sa.Column('topup_id', sa.Integer(), nullable=True),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['topup_id'], ['topups.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_user_id'), 'transactions', ['user_id'], unique=False)
    op.add_column('orders', sa.Column('paid_from_balance', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('balance', sa.BigInteger(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'balance')
    op.drop_column('orders', 'paid_from_balance')
    op.drop_index(op.f('ix_transactions_user_id'), table_name='transactions')
    op.drop_table('transactions')
    op.drop_index(op.f('ix_topups_user_id'), table_name='topups')
    op.drop_index(op.f('ix_topups_status'), table_name='topups')
    op.drop_table('topups')
    sa.Enum(name='transaction_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='topup_status').drop(op.get_bind(), checkfirst=True)
