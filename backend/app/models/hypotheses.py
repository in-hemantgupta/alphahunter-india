from sqlalchemy import Column, String, Float, Date, Text
from app.db.base import Base


class Hypothesis(Base):

    __tablename__ = "hypotheses"

    id = Column(String, primary_key=True)

    date = Column(Date)

    hypothesis = Column(Text)

    confidence = Column(Float)

    status = Column(String)
