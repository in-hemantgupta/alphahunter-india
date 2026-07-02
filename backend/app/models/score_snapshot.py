from sqlalchemy import Column, String, Float, DateTime, Date, PrimaryKeyConstraint
from app.db.base import Base


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("date", "symbol"),
    )

    date = Column(Date, nullable=False)
    symbol = Column(String, nullable=False)
    total_score = Column(Float)
    quality_score = Column(Float)
    growth_score = Column(Float)
    technical_score = Column(Float)
    microstructure_score = Column(Float)
    management_score = Column(Float)
    forensic_score = Column(Float)
    lowvol_score = Column(Float)
    value_score = Column(Float)
    confidence_score = Column(Float)
    layer_breakdown_json = Column(String)
    created_at = Column(DateTime, server_default="now()")
