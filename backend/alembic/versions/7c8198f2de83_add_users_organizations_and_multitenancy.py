"""add_users_organizations_and_multitenancy

Revision ID: 7c8198f2de83
Revises: 3463d904417e
Create Date: 2026-11-15 15:56:49.496757

"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c8198f2de83'
down_revision: Union[str, None] = '3463d904417e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='viewer', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)

    # 3. Create user_organizations membership table
    op.create_table(
        'user_organizations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='viewer', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'organization_id', name='uq_user_organization'),
    )
    op.create_index(op.f('ix_user_organizations_organization_id'), 'user_organizations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_user_organizations_user_id'), 'user_organizations', ['user_id'], unique=False)

    # 4. Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    # 5. Add multi-tenant foreign keys to datasets
    op.add_column('datasets', sa.Column('organization_id', sa.String(length=36), nullable=True))
    op.add_column('datasets', sa.Column('created_by_user_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_datasets_organization_id'), 'datasets', ['organization_id'], unique=False)
    op.create_index(op.f('ix_datasets_created_by_user_id'), 'datasets', ['created_by_user_id'], unique=False)

    # 6. Add multi-tenant foreign keys to pipelines
    op.add_column('pipelines', sa.Column('organization_id', sa.String(length=36), nullable=True))
    op.add_column('pipelines', sa.Column('created_by_user_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_pipelines_organization_id'), 'pipelines', ['organization_id'], unique=False)
    op.create_index(op.f('ix_pipelines_created_by_user_id'), 'pipelines', ['created_by_user_id'], unique=False)

    # 7. Safe Default Organization Seed & Backfill
    bind = op.get_bind()
    default_org_id = "org_default_001"
    now_utc = datetime.now(timezone.utc)

    # Check if default org already exists before inserting
    check_query = sa.text("SELECT id FROM organizations WHERE id = :org_id")
    res = bind.execute(check_query, {"org_id": default_org_id}).first()
    if not res:
        insert_org = sa.text("""
            INSERT INTO organizations (id, name, slug, description, is_active, created_at, updated_at)
            VALUES (:id, :name, :slug, :description, :is_active, :created_at, :updated_at)
        """)
        bind.execute(
            insert_org,
            {
                "id": default_org_id,
                "name": "Default Workspace",
                "slug": "default-workspace",
                "description": "System default organization for existing datasets and streaming pipelines.",
                "is_active": True,
                "created_at": now_utc,
                "updated_at": now_utc,
            },
        )

    # Backfill datasets
    update_datasets = sa.text("""
        UPDATE datasets SET organization_id = :org_id WHERE organization_id IS NULL
    """)
    bind.execute(update_datasets, {"org_id": default_org_id})

    # Backfill pipelines
    update_pipelines = sa.text("""
        UPDATE pipelines SET organization_id = :org_id WHERE organization_id IS NULL
    """)
    bind.execute(update_pipelines, {"org_id": default_org_id})


def downgrade() -> None:
    op.drop_index(op.f('ix_pipelines_created_by_user_id'), table_name='pipelines')
    op.drop_index(op.f('ix_pipelines_organization_id'), table_name='pipelines')
    op.drop_column('pipelines', 'created_by_user_id')
    op.drop_column('pipelines', 'organization_id')

    op.drop_index(op.f('ix_datasets_created_by_user_id'), table_name='datasets')
    op.drop_index(op.f('ix_datasets_organization_id'), table_name='datasets')
    op.drop_column('datasets', 'created_by_user_id')
    op.drop_column('datasets', 'organization_id')

    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    op.drop_index(op.f('ix_user_organizations_user_id'), table_name='user_organizations')
    op.drop_index(op.f('ix_user_organizations_organization_id'), table_name='user_organizations')
    op.drop_table('user_organizations')

    op.drop_index(op.f('ix_organizations_slug'), table_name='organizations')
    op.drop_table('organizations')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
