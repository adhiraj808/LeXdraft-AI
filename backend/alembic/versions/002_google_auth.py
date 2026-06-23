"""Add Google Sign-In support to users

Revision ID: 002
Revises: 001
Create Date: 2026-06-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(255), nullable=True)
    op.add_column('users', sa.Column('auth_provider', sa.String(20), nullable=False, server_default='local'))
    op.add_column('users', sa.Column('google_sub', sa.String(255), nullable=True))
    op.create_index('ix_users_google_sub', 'users', ['google_sub'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_google_sub', 'users')
    op.drop_column('users', 'google_sub')
    op.drop_column('users', 'auth_provider')
    op.alter_column('users', 'hashed_password', existing_type=sa.String(255), nullable=False)
