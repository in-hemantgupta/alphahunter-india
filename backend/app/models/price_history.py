from sqlalchemy import Column, String, Float, Date
from app.db.base import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    delivery_pct = Column(Float)
