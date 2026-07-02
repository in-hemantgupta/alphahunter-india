from sqlalchemy import Column, Integer, Boolean, DateTime, String, Text
from app.db.base import Base
from app.db.database import engine
from sqlalchemy import text


class KillSwitchState(Base):
    __tablename__ = "kill_switch_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_engaged = Column(Boolean, default=False)
    engaged_at = Column(DateTime, nullable=True)
    triggered_by = Column(String, nullable=True)
    conditions_json = Column(Text, nullable=True)
    auto_disarm_at = Column(DateTime, nullable=True)
    disarmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default="now()")


with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS kill_switch_state (
            id SERIAL PRIMARY KEY,
            is_engaged BOOLEAN DEFAULT FALSE,
            engaged_at TIMESTAMP,
            triggered_by VARCHAR(255),
            conditions_json TEXT,
            auto_disarm_at TIMESTAMP,
            disarmed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.commit()
