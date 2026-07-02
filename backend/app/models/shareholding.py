from sqlalchemy import Column, String, Float, DateTime, Date
from app.db.base import Base


class ShareholdingPattern(Base):
    __tablename__ = "shareholding_pattern"

    symbol = Column(String, primary_key=True)
    quarter = Column(String, primary_key=True)
    promoter = Column(Float)
    fii = Column(Float)
    dii = Column(Float)
    pledge = Column(Float)

    # Provenance (Rule 2): every value must be traceable to a source with a
    # confidence and a freshness. No naked scalars.
    source = Column(String, nullable=True)          # e.g. "nse_shareholding_filing", "yfinance_legacy_unreliable"
    confidence = Column(Float, nullable=True)        # 0-1, how much this record should be trusted
    filing_date = Column(Date, nullable=True)         # date the underlying filing covers
    fetched_at = Column(DateTime, nullable=True)       # when we pulled it
