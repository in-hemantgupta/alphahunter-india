"""initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'stocks_master',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('company_name', sa.String()),
        sa.Column('sector', sa.String()),
        sa.Column('exchange', sa.String()),
        sa.Column('isin', sa.String()),
        sa.Column('market_cap', sa.Integer())
    )

    op.create_table(
        'quarterly_financials',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('quarter', sa.String(), primary_key=True),
        sa.Column('revenue', sa.Float()),
        sa.Column('ebitda', sa.Float()),
        sa.Column('pat', sa.Float()),
        sa.Column('eps', sa.Float()),
        sa.Column('roe', sa.Float()),
        sa.Column('roce', sa.Float()),
        sa.Column('debt_equity', sa.Float())
    )

    op.create_table(
        'price_history',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('open', sa.Float()),
        sa.Column('high', sa.Float()),
        sa.Column('low', sa.Float()),
        sa.Column('close', sa.Float()),
        sa.Column('volume', sa.Float())
    )

    op.create_table(
        'shareholding_pattern',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('quarter', sa.String(), primary_key=True),
        sa.Column('promoter', sa.Float()),
        sa.Column('fii', sa.Float()),
        sa.Column('dii', sa.Float()),
        sa.Column('pledge', sa.Float())
    )

    op.create_table(
        'corporate_filings',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('symbol', sa.String()),
        sa.Column('date', sa.Date()),
        sa.Column('announcement_type', sa.String()),
        sa.Column('text', sa.Text())
    )

    op.create_table(
        'ticker_mapping',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('nse_symbol', sa.String()),
        sa.Column('bse_code', sa.String()),
        sa.Column('isin', sa.String()),
        sa.Column('yahoo_symbol', sa.String())
    )

    op.create_table(
        'market_microstructure',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('delivery_percent', sa.Float()),
        sa.Column('volume', sa.Float()),
        sa.Column('avg_volume_30d', sa.Float()),
        sa.Column('vwap', sa.Float()),
        sa.Column('atr', sa.Float()),
        sa.Column('oi', sa.Float()),
        sa.Column('bulk_deal_flag', sa.Boolean())
    )

    op.create_table(
        'bulk_deals',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('symbol', sa.String()),
        sa.Column('buyer', sa.String()),
        sa.Column('seller', sa.String()),
        sa.Column('quantity', sa.Integer()),
        sa.Column('date', sa.Date())
    )

    op.create_table(
        'alternative_signals',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('google_trend_score', sa.Float()),
        sa.Column('contract_score', sa.Float()),
        sa.Column('shipment_score', sa.Float()),
        sa.Column('hiring_score', sa.Float()),
        sa.Column('patent_score', sa.Float()),
        sa.Column('news_score', sa.Float())
    )

    op.create_table(
        'llm_analysis',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('annual_score', sa.Float()),
        sa.Column('concall_score', sa.Float()),
        sa.Column('governance_score', sa.Float()),
        sa.Column('narrative_score', sa.Float()),
        sa.Column('risk_score', sa.Float()),
        sa.Column('final_score', sa.Float())
    )

    op.create_table(
        'portfolio_history',
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('allocation', sa.Float()),
        sa.Column('score', sa.Float())
    )

    op.create_table(
        'rebalance_history',
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('old_weight', sa.Float()),
        sa.Column('new_weight', sa.Float()),
        sa.Column('reason', sa.String())
    )

    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date()),
        sa.Column('portfolio_return', sa.Float()),
        sa.Column('benchmark_return', sa.Float()),
        sa.Column('drawdown', sa.Float()),
        sa.Column('sharpe', sa.Float())
    )

    op.create_table(
        'factor_performance',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('factor', sa.String()),
        sa.Column('contribution', sa.Float()),
        sa.Column('importance', sa.Float())
    )

    op.create_table(
        'ml_training_data',
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('features', sa.JSON()),
        sa.Column('label', sa.Float())
    )

    op.create_table(
        'ml_predictions',
        sa.Column('date', sa.Date(), primary_key=True),
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('probability', sa.Float()),
        sa.Column('confidence', sa.Float())
    )

    op.create_table(
        'hypotheses',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('date', sa.Date()),
        sa.Column('hypothesis', sa.Text()),
        sa.Column('confidence', sa.Float()),
        sa.Column('status', sa.String())
    )

    op.create_table(
        'autonomous_actions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('date', sa.Date()),
        sa.Column('action', sa.Text()),
        sa.Column('reason', sa.Text()),
        sa.Column('result', sa.String())
    )

    op.create_table(
        'learning_history',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('date', sa.Date()),
        sa.Column('prediction', sa.Float()),
        sa.Column('actual', sa.Float()),
        sa.Column('error', sa.Float()),
        sa.Column('adjustment', sa.Float())
    )


def downgrade() -> None:
    op.drop_table('learning_history')
    op.drop_table('autonomous_actions')
    op.drop_table('hypotheses')
    op.drop_table('ml_predictions')
    op.drop_table('ml_training_data')
    op.drop_table('factor_performance')
    op.drop_table('backtest_runs')
    op.drop_table('rebalance_history')
    op.drop_table('portfolio_history')
    op.drop_table('llm_analysis')
    op.drop_table('alternative_signals')
    op.drop_table('bulk_deals')
    op.drop_table('market_microstructure')
    op.drop_table('ticker_mapping')
    op.drop_table('corporate_filings')
    op.drop_table('shareholding_pattern')
    op.drop_table('price_history')
    op.drop_table('quarterly_financials')
    op.drop_table('stocks_master')
