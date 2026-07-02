from sqlalchemy import Column, String, Float, DateTime, Text, Integer
from app.db.base import Base


class DataHealthAudit(Base):
    __tablename__ = "data_health_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False)
    field_name = Column(String, nullable=False)
    coverage_pct = Column(Float)
    source = Column(String)
    status = Column(String)
    failure_reason = Column(Text, nullable=True)
