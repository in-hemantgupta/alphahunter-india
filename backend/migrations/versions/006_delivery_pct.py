"""add delivery_pct to price_history

Phase 2 Task 1/2B: NSE bhavcopy (sec_bhavdata_full CSV, nsearchives.nseindia.com)
is reachable unauthenticated and carries DELIV_PER per symbol/date - the real
replacement for the delivery_ratio heuristic that pipeline.py previously left
as None (see docs/INSTITUTIONAL_REBUILD_PLAN.md Phase 2B).

Revision ID: 006
Revises: 005
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('price_history', sa.Column('delivery_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('price_history', 'delivery_pct')
