"""create_bulk_email_tables

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-03 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create user_smtp_accounts table
    op.create_table(
        'user_smtp_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_address', sa.String(length=255), nullable=False),
        sa.Column('sender_name', sa.String(length=255), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=True),
        sa.Column('connection_type', sa.String(length=32), server_default='SMTP', nullable=False),
        sa.Column('smtp_host', sa.String(length=255), nullable=True),
        sa.Column('smtp_port', sa.Integer(), server_default='587', nullable=True),
        sa.Column('smtp_username', sa.String(length=255), nullable=True),
        sa.Column('use_tls', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('use_ssl', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('encrypted_credentials', sa.String(), nullable=True),
        sa.Column('encryption_key_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('connection_status', sa.String(length=32), server_default='CONNECTED', nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('last_error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], name='fk_user_smtp_accounts_user_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_smtp_accounts_user_id'), 'user_smtp_accounts', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_smtp_accounts_email'), 'user_smtp_accounts', ['email_address'], unique=False)

    # 2. Create email_batches table
    op.create_table(
        'email_batches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('smtp_account_id', sa.Integer(), nullable=True),
        sa.Column('batch_name', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('body_html', sa.String(), nullable=True),
        sa.Column('body_text', sa.String(), nullable=True),
        sa.Column('sending_mode', sa.String(length=32), server_default='PERSONALIZED', nullable=False),
        sa.Column('total_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('valid_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('invalid_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('accepted_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='DRAFT', nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('detected_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('header_mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['smtp_account_id'], ['user_smtp_accounts.id'], name='fk_email_batches_smtp_account_id', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], name='fk_email_batches_user_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_batches_user_id'), 'email_batches', ['user_id'], unique=False)
    op.create_index(op.f('ix_email_batches_status'), 'email_batches', ['status'], unique=False)

    # 3. Create email_recipients table
    op.create_table(
        'email_recipients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_address', sa.String(length=255), nullable=False),
        sa.Column('recipient_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('rendered_subject', sa.String(), nullable=True),
        sa.Column('rendered_body', sa.String(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('provider_message_id', sa.String(length=255), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('bounced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['email_batches.id'], name='fk_email_recipients_batch_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], name='fk_email_recipients_user_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_recipients_batch_id'), 'email_recipients', ['batch_id'], unique=False)
    op.create_index(op.f('ix_email_recipients_user_id'), 'email_recipients', ['user_id'], unique=False)
    op.create_index(op.f('ix_email_recipients_status'), 'email_recipients', ['status'], unique=False)
    op.create_index(op.f('ix_email_recipients_email'), 'email_recipients', ['email_address'], unique=False)


def downgrade() -> None:
    op.drop_table('email_recipients')
    op.drop_table('email_batches')
    op.drop_table('user_smtp_accounts')
