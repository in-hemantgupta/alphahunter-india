from sqlalchemy import Column, Integer, String, Float
from app.db.base import Base


class FactorPerformance(Base):
    __tablename__ = "factor_performance"

    id = Column(Integer, primary_key=True)
    factor = Column(String)
    contribution = Column(Float)
    importance = Column(Float)
