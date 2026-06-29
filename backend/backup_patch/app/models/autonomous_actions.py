from sqlalchemy import Column, String, Date, Text
from app.db.base import Base


class AutonomousAction(Base):

    __tablename__ = "autonomous_actions"

    id = Column(String, primary_key=True)

    date = Column(Date)

    action = Column(Text)

    reason = Column(Text)

    result = Column(String)
