from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Text
from sqlalchemy.sql import func
from app.db.base import Base


class DataSourceHealth(Base):
    __tablename__ = "data_source_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String, unique=True, nullable=False)
    last_successful_fetch = Column(DateTime, nullable=True)
    last_failed_attempt = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    total_failures = Column(Integer, default=0)
    health_score = Column(Float, default=1.0)
    is_stale = Column(Boolean, default=False)
    last_error = Column(Text, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    total_requests = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
