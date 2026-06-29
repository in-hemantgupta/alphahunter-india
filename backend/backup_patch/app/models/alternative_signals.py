from sqlalchemy import Column, String, Float, Date
from app.db.base import Base


class AlternativeSignal(Base):
    __tablename__ = "alternative_signals"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    google_trend_score = Column(Float)
    contract_score = Column(Float)
    shipment_score = Column(Float)
    hiring_score = Column(Float)
    patent_score = Column(Float)
    news_score = Column(Float)
