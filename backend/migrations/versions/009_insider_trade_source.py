"""add value/source/confidence to insider_trades

Phase 2 Task 3: real NSE corporates-pit feed (SEBI PIT Regulation 7(2)
disclosures) gives transaction value directly - not derivable from the old
schema's quantity+avg_price alone when only one side is filled in.

Revision ID: 009
Revises: 008
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('insider_trades', sa.Column('value', sa.Float(), nullable=True))
    op.add_column('insider_trades', sa.Column('source', sa.String(), nullable=True))
    op.add_column('insider_trades', sa.Column('confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('insider_trades', 'confidence')
    op.drop_column('insider_trades', 'source')
    op.drop_column('insider_trades', 'value')
