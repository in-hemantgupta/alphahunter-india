from sqlalchemy import Column, String
from app.db.base import Base


class TickerMapping(Base):
    __tablename__ = "ticker_mapping"

    symbol = Column(String, primary_key=True)
    nse_symbol = Column(String)
    bse_code = Column(String)
    isin = Column(String)
    yahoo_symbol = Column(String)
