from sqlalchemy import Column, String, Float, Date
from app.db.base import Base


class LearningHistory(Base):

    __tablename__ = "learning_history"

    id = Column(String, primary_key=True)

    date = Column(Date)

    prediction = Column(Float)

    actual = Column(Float)

    error = Column(Float)

    adjustment = Column(Float)
