from sqlalchemy import Column, String, Float, Date, DateTime, Integer, Text
from app.db.base import Base


class TradeDecisionLog(Base):
    __tablename__ = "trade_decision_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)
    score = Column(Float)
    rank = Column(Integer)
    confidence = Column(Float)
    factors_responsible = Column(Text)
    exit_trigger = Column(String)
    allocation = Column(Float)
    price = Column(Float)
    reason = Column(Text)
    sector = Column(String)
    regime = Column(String)
    created_at = Column(DateTime, server_default="now()")
