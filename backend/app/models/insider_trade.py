from sqlalchemy import Column, String, Float, Integer, Date, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class InsiderTrade(Base):
    __tablename__ = "insider_trades"

    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    insider_name = Column(String)
    transaction_type = Column(String)
    quantity = Column(Integer)
    avg_price = Column(Float)
    insider_role = Column(String)
    value = Column(Float)
    source = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
