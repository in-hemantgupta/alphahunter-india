from sqlalchemy import Column, String, Float, Date, DateTime, Integer
from app.db.base import Base


class FundNav(Base):
    __tablename__ = "fund_nav"

    date = Column(Date, primary_key=True)
    nav = Column(Float)
    cash = Column(Float)
    invested_capital = Column(Float)
    realized_pnl = Column(Float)
    unrealized_pnl = Column(Float)
    benchmark_nav = Column(Float)
    daily_return = Column(Float)
    benchmark_return = Column(Float)
    alpha = Column(Float)
    n_holdings = Column(Integer)
    created_at = Column(DateTime, server_default="now()")
