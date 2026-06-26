from sqlalchemy import \

    Column, String, Float, Date

from app.db.base import Base


class RebalanceHistory(Base):

    __tablename__ = \

        "rebalance_history"

    date = Column(

        Date,

        primary_key=True
    )

    symbol = Column(

        String,

        primary_key=True
    )

    old_weight = Column(
        Float
    )

    new_weight = Column(
        Float
    )

    reason = Column(
        String
    )
