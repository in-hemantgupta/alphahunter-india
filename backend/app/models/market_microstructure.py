from sqlalchemy import Column, String, Float, Date, Boolean
from app.db.base import Base


class MarketMicrostructure(Base):
    __tablename__ = "market_microstructure"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    delivery_percent = Column(Float)
    volume = Column(Float)
    avg_volume_30d = Column(Float)
    vwap = Column(Float)
    atr = Column(Float)
    oi = Column(Float)
    bulk_deal_flag = Column(Boolean)
