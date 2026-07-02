from sqlalchemy import Column, String, Integer, BigInteger, Date
from app.db.base import Base


class Stock(Base):
    __tablename__ = "stocks_master"

    symbol = Column(String, primary_key=True)
    company_name = Column(String)
    sector = Column(String)
    exchange = Column(String)
    isin = Column(String)
    market_cap = Column(BigInteger)

    # Survivorship-bias fix (Rule 4): backtests and universe queries must be
    # able to tell active stocks from delisted/suspended ones instead of only
    # ever seeing today's live universe.
    status = Column(String, nullable=False, server_default="active")  # active | delisted | suspended
    listing_date = Column(Date, nullable=True)
    delisting_date = Column(Date, nullable=True)
