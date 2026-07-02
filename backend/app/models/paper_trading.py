from sqlalchemy import Column, String, Float, Date, DateTime, Integer, PrimaryKeyConstraint
from app.db.base import Base


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (PrimaryKeyConstraint("symbol"),)

    symbol = Column(String, nullable=False)
    entry_date = Column(Date, nullable=False)
    entry_price = Column(Float)
    quantity = Column(Integer)
    weight = Column(Float)
    current_price = Column(Float)
    unrealized_pnl_pct = Column(Float)
    last_updated = Column(DateTime, server_default="now()")


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    entry_date = Column(Date, nullable=False)
    exit_date = Column(Date)
    entry_price = Column(Float)
    exit_price = Column(Float)
    return_pct = Column(Float)
    quantity = Column(Integer)
    trade_type = Column(String)
    exit_reason = Column(String)
    pnl = Column(Float)
    created_at = Column(DateTime, server_default="now()")
