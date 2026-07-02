from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import settings
from app.db.base import Base

# Import all models so they're registered with Base
from app.models.stock import Stock
from app.models.quarterly import QuarterlyFinancials
from app.models.price_history import PriceHistory
from app.models.shareholding import ShareholdingPattern
from app.models.corporate_filings import CorporateFiling
from app.models.ticker_mapping import TickerMapping
from app.models.market_microstructure import MarketMicrostructure
from app.models.bulk_deals import BulkDeal
from app.models.alternative_signals import AlternativeSignal
from app.models.llm_analysis import LLMAnalysis
from app.models.portfolio_history import PortfolioHistory
from app.models.rebalance_history import RebalanceHistory
from app.models.backtest_runs import BacktestRun
from app.models.factor_performance import FactorPerformance
from app.models.ml_training_data import MLTrainingData
from app.models.ml_predictions import MLPrediction
from app.models.hypotheses import Hypothesis
from app.models.autonomous_actions import AutonomousAction
from app.models.learning_history import LearningHistory
from app.models.score_snapshot import ScoreSnapshot
from app.models.scored_stock import ScoredStock
from app.models.market_regime import MarketRegime
from app.models.paper_trading import PaperPosition, PaperTrade

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
