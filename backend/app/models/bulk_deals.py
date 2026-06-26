from sqlalchemy import Column, String, Integer, Date
from app.db.base import Base


class BulkDeal(Base):
    __tablename__ = "bulk_deals"

    id = Column(String, primary_key=True)
    symbol = Column(String)
    buyer = Column(String)
    seller = Column(String)
    quantity = Column(Integer)
    date = Column(Date)
