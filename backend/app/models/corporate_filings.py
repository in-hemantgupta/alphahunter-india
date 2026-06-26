from sqlalchemy import Column, String, Date, Text
from app.db.base import Base


class CorporateFiling(Base):
    __tablename__ = "corporate_filings"

    id = Column(String, primary_key=True)
    symbol = Column(String)
    date = Column(Date)
    announcement_type = Column(String)
    text = Column(Text)
