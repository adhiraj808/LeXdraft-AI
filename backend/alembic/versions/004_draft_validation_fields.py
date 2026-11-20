"""Phase 3: add validation fields to drafts

Revision ID: 004
Revises: 003
Create Date: 2026-11-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add validation metadata columns to drafts table
    op.add_column(
        'drafts',
        sa.Column('review_notes', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'drafts',
        sa.Column('to_complete', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'drafts',
        sa.Column('validation_failed', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        'drafts',
        sa.Column('disclaimer', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('drafts', 'disclaimer')
    op.drop_column('drafts', 'validation_failed')
    op.drop_column('drafts', 'to_complete')
    op.drop_column('drafts', 'review_notes')