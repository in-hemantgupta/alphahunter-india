from sqlalchemy import \

    Column, String, Integer

from app.db.base import Base


class Stock(Base):

    __tablename__ = \
        "stocks_master"

    symbol = Column(

        String,

        primary_key=True
    )

    company_name = Column(
        String
    )

    sector = Column(
        String
    )

    exchange = Column(
        String
    )

    isin = Column(
        String
    )

    market_cap = Column(
        Integer
    )
