from sqlalchemy import Column, Integer, String, Float, Date, DateTime, func
from app.db.base import Base


class FactorValue(Base):
    __tablename__ = "factor_values"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    factor_name = Column(String, nullable=False)
    raw_value = Column(Float, nullable=True)
    normalized_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=True)
    freshness_days = Column(Integer, nullable=True)
    as_of_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
