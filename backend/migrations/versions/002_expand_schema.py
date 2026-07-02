"""expand quarterly_financials (10 columns), create corporate_actions, insider_trades

Revision ID: 002
Revises: 001
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- Add missing columns to quarterly_financials using IF NOT EXISTS ---
    _add_cols(conn, 'quarterly_financials', [
        'operating_profit', 'operating_margin', 'cash_flow_operations',
        'free_cash_flow', 'debt', 'interest_expense', 'inventory', 'receivables',
        # P1B — 10 new columns
        'total_assets', 'total_equity', 'current_assets', 'current_liabilities',
        'depreciation', 'tax_expense', 'employee_cost', 'raw_material_cost',
        'cash_equivalents', 'capex',
    ])

    # P2 — corporate_actions table
    op.create_table(
        'corporate_actions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('dividend', sa.Float()),
        sa.Column('split_ratio', sa.String()),
        sa.Column('bonus_ratio', sa.String()),
        sa.Column('buyback_size', sa.Float()),
        sa.Column('rights_issue', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_corporate_actions_symbol', 'corporate_actions', ['symbol'])

    # P3 — insider_trades table
    op.create_table(
        'insider_trades',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('insider_name', sa.String()),
        sa.Column('transaction_type', sa.String()),
        sa.Column('quantity', sa.Integer()),
        sa.Column('avg_price', sa.Float()),
        sa.Column('insider_role', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_insider_trades_symbol', 'insider_trades', ['symbol'])


def downgrade() -> None:
    op.drop_table('insider_trades')
    op.drop_table('corporate_actions')
    _drop_cols(op.get_bind(), 'quarterly_financials', [
        'capex', 'cash_equivalents', 'raw_material_cost', 'employee_cost',
        'tax_expense', 'depreciation', 'current_liabilities', 'current_assets',
        'total_equity', 'total_assets', 'receivables', 'inventory',
        'interest_expense', 'debt', 'free_cash_flow', 'cash_flow_operations',
        'operating_margin', 'operating_profit',
    ])


def _add_cols(conn, table, columns):
    for col in columns:
        try:
            conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{col}" DOUBLE PRECISION')
        except Exception:
            pass


def _drop_cols(conn, table, columns):
    for col in columns:
        try:
            conn.exec_driver_sql(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{col}"')
        except Exception:
            pass
