"""add source + confidence to quarterly_financials

Phase 2 Task 4/5: financial_ingestor.py already has a real 3-tier fallback
(screener.in -> NSE -> BSE) but never recorded which tier supplied a given
row or how much to trust it - this closes that gap.

Revision ID: 008
Revises: 007
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('quarterly_financials', sa.Column('source', sa.String(), nullable=True))
    op.add_column('quarterly_financials', sa.Column('confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('quarterly_financials', 'confidence')
    op.drop_column('quarterly_financials', 'source')
