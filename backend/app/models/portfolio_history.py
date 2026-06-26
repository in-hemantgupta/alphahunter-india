from sqlalchemy import \

    Column, String, Float, Date

from app.db.base import Base


class PortfolioHistory(Base):

    __tablename__ = \

        "portfolio_history"

    date = Column(

        Date,

        primary_key=True
    )

    symbol = Column(

        String,

        primary_key=True
    )

    allocation = Column(
        Float
    )

    score = Column(
        Float
    )
