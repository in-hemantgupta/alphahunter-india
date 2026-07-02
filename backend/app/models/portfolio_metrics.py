from sqlalchemy import Column, String, Float, Date, DateTime
from app.db.base import Base


class PortfolioMetrics(Base):
    __tablename__ = "portfolio_metrics"

    date = Column(Date, primary_key=True)
    nav = Column(Float)
    benchmark_nav = Column(Float)
    daily_return = Column(Float)
    benchmark_return = Column(Float)
    alpha = Column(Float)
    sharpe_30d = Column(Float)
    sharpe_90d = Column(Float)
    drawdown = Column(Float)
    volatility_30d = Column(Float)
    turnover_annual = Column(Float)
    n_holdings = Column(Float)
    created_at = Column(DateTime, server_default="now()")
