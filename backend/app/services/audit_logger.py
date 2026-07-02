from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.database import SessionLocal, engine


class AuditLogger:
    def __init__(self):
        self.session = SessionLocal()
        self._ensure_table()

    def _ensure_table(self):
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
            conn.commit()

    def log(self, action, category, status='INFO', details=None, source=None, duration_ms=None, symbol=None, error_message=None):
        self.session.execute(text("""
            INSERT INTO system_audit_log (timestamp, action, category, status, details, source, duration_ms, symbol, error_message)
            VALUES (:timestamp, :action, :category, :status, :details, :source, :duration_ms, :symbol, :error_message)
        """), {
            "timestamp": datetime.now(),
            "action": action,
            "category": category,
            "status": status,
            "details": details,
            "source": source,
            "duration_ms": duration_ms,
            "symbol": symbol,
            "error_message": error_message,
        })
        self.session.commit()

    def log_success(self, action, category, details=None, source=None, duration_ms=None, symbol=None):
        self.log(action, category, 'SUCCESS', details, source, duration_ms, symbol)

    def log_failure(self, action, category, error_message, details=None, source=None, symbol=None):
        self.log(action, category, 'FAILURE', details, source, None, symbol, error_message)

    def log_warning(self, action, category, details=None, source=None, symbol=None):
        self.log(action, category, 'WARNING', details, source, None, symbol)

    def query(self, category=None, action=None, status=None, limit=100):
        conditions = []
        params = {}
        if category:
            conditions.append("category = :category")
            params["category"] = category
        if action:
            conditions.append("action = :action")
            params["action"] = action
        if status:
            conditions.append("status = :status")
            params["status"] = status
        where = " AND ".join(conditions) if conditions else "TRUE"
        sql = f"SELECT * FROM system_audit_log WHERE {where} ORDER BY timestamp DESC LIMIT :limit"
        params["limit"] = limit
        return self.session.execute(text(sql), params).fetchall()

    def get_recent_failures(self, hours=24):
        since = datetime.now() - timedelta(hours=hours)
        return self.session.execute(text("""
            SELECT * FROM system_audit_log
            WHERE status = 'FAILURE' AND timestamp >= :since
            ORDER BY timestamp DESC
        """), {"since": since}).fetchall()

    def get_action_count(self, action, since):
        return self.session.execute(text("""
            SELECT COUNT(*) FROM system_audit_log
            WHERE action = :action AND timestamp >= :since
        """), {"action": action, "since": since}).scalar()

    def close(self):
        self.session.close()
