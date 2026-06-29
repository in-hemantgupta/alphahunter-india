from sqlalchemy import Column, String, Float
from app.db.base import Base


class QuarterlyFinancials(Base):
    __tablename__ = "quarterly_financials"

    symbol = Column(String, primary_key=True)
    quarter = Column(String, primary_key=True)
    revenue = Column(Float)
    ebitda = Column(Float)
    pat = Column(Float)
    roce = Column(Float)
    roe = Column(Float)
    debt_equity = Column(Float)
