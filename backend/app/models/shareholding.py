from sqlalchemy import \

    Column, String, Float

from app.db.base import Base


class ShareholdingPattern(Base):

    __tablename__ = \

        "shareholding_pattern"

    symbol = Column(

        String,

        primary_key=True
    )

    quarter = Column(

        String,

        primary_key=True
    )

    promoter = Column(
        Float
    )

    fii = Column(
        Float
    )

    dii = Column(
        Float
    )

    pledge = Column(
        Float
    )
