from sqlalchemy import Column, Integer, String, DateTime, Text
from app.db.base import Base
from app.db.database import engine
from sqlalchemy import text


class SystemAuditLog(Base):
    __tablename__ = "system_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    action = Column(String, nullable=False)
    category = Column(String, nullable=False)
    status = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    symbol = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default="now()")


with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS system_audit_log (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            action VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL,
            details TEXT,
            source VARCHAR(100),
            duration_ms INTEGER,
            symbol VARCHAR(20),
            error_message TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON system_audit_log(timestamp)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_category ON system_audit_log(category)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_action ON system_audit_log(action)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_status ON system_audit_log(status)"))
    conn.commit()
