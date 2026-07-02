from sqlalchemy import Column, String, Float, Date, PrimaryKeyConstraint, DateTime
from app.db.base import Base


class MarketRegime(Base):
    __tablename__ = "market_regime"
    __table_args__ = (
        PrimaryKeyConstraint("date"),
    )

    date = Column(Date, nullable=False)
    regime = Column(String, nullable=False)
    nifty_200dma_pct = Column(Float)
    vix_percentile = Column(Float)
    ad_ratio = Column(Float)
    fiil_net_flow = Column(Float)
    diil_net_flow = Column(Float)
    created_at = Column(DateTime, server_default="now()")
