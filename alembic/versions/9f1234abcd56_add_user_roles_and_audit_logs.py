"""add_user_roles_and_audit_logs

Revision ID: 9f1234abcd56
Revises: 85c062393f71
Create Date: 2026-10-24 12:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9f1234abcd56'
down_revision: Union[str, Sequence[str], None] = '85c062393f71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add role column to user_table with server_default 'CUSTOMER'
    op.add_column(
        'user_table',
        sa.Column('role', sa.String(length=32), nullable=False, server_default='CUSTOMER')
    )

    # 2. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=True),
        sa.Column('target_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['admin_user_id'], ['user_table.user_id'], ),
        sa.ForeignKeyConstraint(['target_user_id'], ['user_table.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_admin_user_id'), 'audit_logs', ['admin_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_target_user_id'), 'audit_logs', ['target_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_target_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_admin_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_column('user_table', 'role')
