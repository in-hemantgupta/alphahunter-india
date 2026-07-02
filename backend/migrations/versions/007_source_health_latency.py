"""add latency + total_requests to data_source_health

Phase 2 Task 7: uptime_pct is derived (total_requests - total_failures) /
total_requests at read time, not stored, so it can't drift out of sync with
the counters it's computed from.

Revision ID: 007
Revises: 006
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('data_source_health', sa.Column('avg_latency_ms', sa.Float(), nullable=True))
    op.add_column('data_source_health', sa.Column('total_requests', sa.Integer(), server_default='0'))


def downgrade() -> None:
    op.drop_column('data_source_health', 'total_requests')
    op.drop_column('data_source_health', 'avg_latency_ms')
