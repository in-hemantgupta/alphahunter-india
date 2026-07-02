from sqlalchemy import Column, String, Float, Date, DateTime, Integer, PrimaryKeyConstraint
from app.db.base import Base


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (PrimaryKeyConstraint("symbol", "date"),)

    symbol = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    score = Column(Float)
    rank = Column(Integer)
    entry_price = Column(Float)
    current_price = Column(Float)
    allocation = Column(Float)
    pnl_pct = Column(Float)
    sector = Column(String)
    confidence = Column(Float)
    entry_date = Column(Date)
    regime = Column(String)
    beta = Column(Float)
    created_at = Column(DateTime, server_default="now()")
