"""create_tenants_and_memberships

Revision ID: c1d2e3f4a5b6
Revises: b7e891c23f45
Create Date: 2026-11-03 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7e891c23f45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_tenants_slug')
    )
    op.create_index(op.f('ix_tenants_status'), 'tenants', ['status'], unique=False)

    # 2. Create tenant_memberships table
    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='MEMBER', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_tenant_memberships_tenant_id', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['user_table.user_id'], name='fk_tenant_memberships_user_id', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_membership_tenant_user')
    )
    op.create_index(op.f('ix_tenant_memberships_tenant_id'), 'tenant_memberships', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_memberships_user_id'), 'tenant_memberships', ['user_id'], unique=False)

    # 3. Data migration: Create default tenant and OWNER membership for every existing user
    # Handle user's name: if name is non-empty, use "<name>'s Workspace", else "Workspace <user_id>"
    op.execute(sa.text("""
        INSERT INTO tenants (name, slug, status, is_deleted, created_at, updated_at)
        SELECT 
            CASE 
                WHEN TRIM(COALESCE(u.name, '')) <> '' THEN TRIM(u.name) || '''s Workspace'
                ELSE 'Workspace ' || u.user_id
            END AS name,
            'tenant-' || u.user_id AS slug,
            'ACTIVE' AS status,
            false AS is_deleted,
            COALESCE(u.created_at, NOW()) AS created_at,
            COALESCE(u.updated_at, NOW()) AS updated_at
        FROM user_table u
        WHERE NOT EXISTS (
            SELECT 1 FROM tenants t WHERE t.slug = 'tenant-' || u.user_id
        );
    """))

    # Link every existing user to their default tenant with role 'OWNER' and status 'ACTIVE'
    op.execute(sa.text("""
        INSERT INTO tenant_memberships (tenant_id, user_id, role, status, created_at, updated_at)
        SELECT 
            t.id AS tenant_id,
            u.user_id AS user_id,
            'OWNER' AS role,
            'ACTIVE' AS status,
            COALESCE(u.created_at, NOW()) AS created_at,
            COALESCE(u.updated_at, NOW()) AS updated_at
        FROM user_table u
        JOIN tenants t ON t.slug = 'tenant-' || u.user_id
        WHERE NOT EXISTS (
            SELECT 1 FROM tenant_memberships tm 
            WHERE tm.tenant_id = t.id AND tm.user_id = u.user_id
        );
    """))


def downgrade() -> None:
    # Downgrade drops the new tables created in this migration
    op.drop_index(op.f('ix_tenant_memberships_user_id'), table_name='tenant_memberships')
    op.drop_index(op.f('ix_tenant_memberships_tenant_id'), table_name='tenant_memberships')
    op.drop_table('tenant_memberships')
    op.drop_index(op.f('ix_tenants_status'), table_name='tenants')
    op.drop_table('tenants')
