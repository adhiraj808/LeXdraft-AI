"""Phase 1: add raw_prompt and fact_sheet to cases

Revision ID: 003
Revises: 002
Create Date: 2026-01-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'cases',
        sa.Column('raw_prompt', sa.Text(), nullable=True)
    )
    op.add_column(
        'cases',
        sa.Column('fact_sheet', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('cases', 'fact_sheet')
    op.drop_column('cases', 'raw_prompt')