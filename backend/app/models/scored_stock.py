from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean
from sqlalchemy.sql import func
from app.db.base import Base


class ScoredStock(Base):
    __tablename__ = "scored_stocks"

    symbol = Column(String, primary_key=True)
    company_name = Column(String)
    total_score = Column(Float)
    current_price = Column(Float)
    returns_6m = Column(Float)
    returns_1y = Column(Float)
    volume_ratio = Column(Float)
    delivery_ratio = Column(Float)
    roce = Column(Float)
    roe = Column(Float)
    debt_equity = Column(Float)
    revenue_acceleration = Column(Float)
    pat_acceleration = Column(Float)
    margin_expansion = Column(Float)
    promoter_change = Column(Float)
    pledge_percent = Column(Float)
    relative_strength = Column(Float)
    trend_strength = Column(Float)
    compression_pattern = Column(Boolean)
    breakout_probability = Column(Float)
    volume_confirmation = Column(Boolean)
    google_trend_score = Column(Float)
    contract_score = Column(Float)
    hiring_score = Column(Float)
    patent_score = Column(Float)
    news_score = Column(Float)
    annual_report_score = Column(Float)
    concall_score = Column(Float)
    governance_score = Column(Float)
    narrative_score = Column(Float)
    risk_score = Column(Float)
    management_confidence = Column(Float)
    elimination_stages = Column(String)
    passed_elimination = Column(Boolean, default=False)
    scored_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
