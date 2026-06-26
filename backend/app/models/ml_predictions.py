from sqlalchemy import Column, String, Float, Date
from app.db.base import Base


class MLPrediction(Base):

    __tablename__ = "ml_predictions"

    date = Column(

        Date,

        primary_key=True

    )

    symbol = Column(

        String,

        primary_key=True

    )

    probability = Column(Float)

    confidence = Column(Float)
