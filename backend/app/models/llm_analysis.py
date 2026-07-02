from sqlalchemy import Column, String, Float, Date
from app.db.base import Base


class LLMAnalysis(Base):
    __tablename__ = "llm_analysis"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    annual_score = Column(Float)
    concall_score = Column(Float)
    governance_score = Column(Float)
    narrative_score = Column(Float)
    risk_score = Column(Float)
    sentiment_score = Column(Float)
    management_confidence = Column(Float)
    final_score = Column(Float)
