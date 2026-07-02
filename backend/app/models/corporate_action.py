from sqlalchemy import Column, String, Float, Date, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    action_type = Column(String, nullable=False)
    dividend = Column(Float)
    split_ratio = Column(String)
    bonus_ratio = Column(String)
    buyback_size = Column(Float)
    rights_issue = Column(String)
    created_at = Column(DateTime, server_default=func.now())
