"""add factor_values audit table

Rule 9: every layer score in a stock's composite must be traceable back to
its raw input, source, confidence and as-of date - not just the final
0-100 number. One row per (symbol, factor_name, scored_at).

Revision ID: 005
Revises: 004
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'factor_values',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('factor_name', sa.String(), nullable=False),
        sa.Column('raw_value', sa.Float(), nullable=True),
        sa.Column('normalized_score', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('freshness_days', sa.Integer(), nullable=True),
        sa.Column('as_of_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('idx_factor_values_symbol', 'factor_values', ['symbol'])
    op.create_index('idx_factor_values_symbol_factor', 'factor_values', ['symbol', 'factor_name'])


def downgrade() -> None:
    op.drop_index('idx_factor_values_symbol_factor', table_name='factor_values')
    op.drop_index('idx_factor_values_symbol', table_name='factor_values')
    op.drop_table('factor_values')
