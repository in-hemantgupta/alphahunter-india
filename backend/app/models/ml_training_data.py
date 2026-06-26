from sqlalchemy import Column, String, Float, Date, JSON
from app.db.base import Base


class MLTrainingData(Base):

    __tablename__ = "ml_training_data"

    date = Column(

        Date,

        primary_key=True

    )

    symbol = Column(

        String,

        primary_key=True

    )

    features = Column(JSON)

    label = Column(Float)
