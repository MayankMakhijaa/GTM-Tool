"""create_credit_wallets_ledger_and_pricing

Revision ID: b7e891c23f45
Revises: 9f1234abcd56
Create Date: 2026-10-24 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e891c23f45'
down_revision: Union[str, Sequence[str], None] = '9f1234abcd56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_credit_wallets
    op.create_table(
        'user_credit_wallets',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_balance', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('reserved_balance', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('total_balance >= 0', name='chk_wallet_total_balance_non_negative'),
        sa.CheckConstraint('reserved_balance >= 0', name='chk_wallet_reserved_balance_non_negative'),
        sa.CheckConstraint('reserved_balance <= total_balance', name='chk_wallet_reserved_le_total'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # 2. feature_pricing
    op.create_table(
        'feature_pricing',
        sa.Column('feature_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('unit_name', sa.String(length=32), server_default='qualified_lead', nullable=False),
        sa.Column('credit_cost', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.CheckConstraint('credit_cost >= 0', name='chk_feature_pricing_credit_cost_non_negative'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user_table.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('feature_code')
    )

    # Idempotent seed for initial GTM feature
    op.execute("""
        INSERT INTO feature_pricing (feature_code, name, description, unit_name, credit_cost, is_active, version, created_at, updated_at)
        VALUES ('GTM_RESEARCH_LEAD', 'GTM Qualified Lead Discovery', 'Per qualified candidate discovered and saved to user dashboard', 'qualified_lead', 2.00, true, 1, NOW(), NOW())
        ON CONFLICT (feature_code) DO NOTHING;
    """)

    # 3. credit_reservations
    op.create_table(
        'credit_reservations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('billing_operation_id', sa.String(length=160), nullable=False),
        sa.Column('feature_code', sa.String(length=64), nullable=False),
        sa.Column('requested_quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price_snapshot', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('pricing_version_snapshot', sa.Integer(), nullable=False),
        sa.Column('reserved_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('charged_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='RESERVED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('settled_at', sa.DateTime(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('reserved_amount >= 0', name='chk_res_reserved_amount_non_negative'),
        sa.CheckConstraint('charged_amount >= 0', name='chk_res_charged_amount_non_negative'),
        sa.CheckConstraint('charged_amount <= reserved_amount', name='chk_res_charged_le_reserved'),
        sa.ForeignKeyConstraint(['feature_code'], ['feature_pricing.feature_code'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['job_id'], ['research_jobs.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credit_reservations_billing_operation_id'), 'credit_reservations', ['billing_operation_id'], unique=True)
    op.create_index(op.f('ix_credit_reservations_job_id'), 'credit_reservations', ['job_id'], unique=False)
    op.create_index(op.f('ix_credit_reservations_status'), 'credit_reservations', ['status'], unique=False)
    op.create_index(op.f('ix_credit_reservations_user_id'), 'credit_reservations', ['user_id'], unique=False)

    # 4. credit_transactions
    op.create_table(
        'credit_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('reservation_id', sa.Integer(), nullable=True),
        sa.Column('transaction_type', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reserved_delta', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reserved_after', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('feature_code', sa.String(length=64), nullable=True),
        sa.Column('unit_price_snapshot', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('pricing_version_snapshot', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=160), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['user_table.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['feature_code'], ['feature_pricing.feature_code'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['job_id'], ['research_jobs.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reservation_id'], ['credit_reservations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credit_transactions_idempotency_key'), 'credit_transactions', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_credit_transactions_job_id'), 'credit_transactions', ['job_id'], unique=False)
    op.create_index(op.f('ix_credit_transactions_reservation_id'), 'credit_transactions', ['reservation_id'], unique=False)
    op.create_index(op.f('ix_credit_transactions_transaction_type'), 'credit_transactions', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_credit_transactions_user_id'), 'credit_transactions', ['user_id'], unique=False)
    op.create_index('ix_credit_tx_user_created', 'credit_transactions', ['user_id', 'created_at'], unique=False)

    # 5. ai_provider_usage_logs
    op.create_table(
        'ai_provider_usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model_name', sa.String(length=64), nullable=False),
        sa.Column('operation', sa.String(length=64), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('estimated_cost_usd', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('provider_cost', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('provider_currency', sa.String(length=8), server_default='USD', nullable=True),
        sa.Column('status', sa.String(length=32), server_default='SUCCESS', nullable=False),
        sa.Column('error_category', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['research_jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_provider_usage_logs_correlation_id'), 'ai_provider_usage_logs', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_ai_provider_usage_logs_job_id'), 'ai_provider_usage_logs', ['job_id'], unique=False)
    op.create_index(op.f('ix_ai_provider_usage_logs_user_id'), 'ai_provider_usage_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('ai_provider_usage_logs')
    op.drop_table('credit_transactions')
    op.drop_table('credit_reservations')
    op.drop_table('feature_pricing')
    op.drop_table('user_credit_wallets')
