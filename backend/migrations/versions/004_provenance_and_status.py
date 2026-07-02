"""add data provenance columns + stocks_master status/delisting

Rule 1 (never fake data) / Rule 2 (full provenance) / Rule 4 (no survivorship bias).

shareholding_pattern.pledge was, in every existing row, written by a hardcoded
`pledge_pct = 0` in the old ingestor (never actually read from a filing). That
value is indistinguishable from "genuinely zero pledge" and must not be
treated as real. This migration nulls it out for all legacy rows rather than
leaving a fabricated 0 in place, and tags those rows with a low-confidence
legacy source so downstream code can tell it apart from a real filing.

Revision ID: 004
Revises: 003
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('shareholding_pattern', sa.Column('source', sa.String(), nullable=True))
    op.add_column('shareholding_pattern', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('shareholding_pattern', sa.Column('filing_date', sa.Date(), nullable=True))
    op.add_column('shareholding_pattern', sa.Column('fetched_at', sa.DateTime(), nullable=True))

    op.execute("""
        UPDATE shareholding_pattern
        SET pledge = NULL,
            source = 'yfinance_legacy_unreliable',
            confidence = 0.15,
            fetched_at = now()
        WHERE source IS NULL
    """)

    op.add_column('stocks_master', sa.Column('status', sa.String(), nullable=False, server_default='active'))
    op.add_column('stocks_master', sa.Column('listing_date', sa.Date(), nullable=True))
    op.add_column('stocks_master', sa.Column('delisting_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('stocks_master', 'delisting_date')
    op.drop_column('stocks_master', 'listing_date')
    op.drop_column('stocks_master', 'status')

    op.drop_column('shareholding_pattern', 'fetched_at')
    op.drop_column('shareholding_pattern', 'filing_date')
    op.drop_column('shareholding_pattern', 'confidence')
    op.drop_column('shareholding_pattern', 'source')
