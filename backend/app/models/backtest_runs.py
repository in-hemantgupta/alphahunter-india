from sqlalchemy import Column, Integer, String, Float, Date
from app.db.base import Base


class BacktestRun(Base):

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True)

    date = Column(Date)

    portfolio_return = Column(Float)

    benchmark_return = Column(Float)

    drawdown = Column(Float)

    sharpe = Column(Float)
