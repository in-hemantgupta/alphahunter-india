from datetime import datetime
from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.models.data_source_health import DataSourceHealth


SOURCES = [
    "yfinance_prices",
    "yfinance_financials",
    "nse_financial",
    "bse_pdf",
    "screener_in",
]


class DataFreshnessMonitor:
    def __init__(self):
        self.session = SessionLocal()
        self._ensure_table()
        self._seed_sources()

    def _ensure_table(self):
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS data_source_health (
                    id SERIAL PRIMARY KEY,
                    source_name VARCHAR(100) UNIQUE NOT NULL,
                    last_successful_fetch TIMESTAMP,
                    last_failed_attempt TIMESTAMP,
                    consecutive_failures INTEGER DEFAULT 0,
                    total_failures INTEGER DEFAULT 0,
                    health_score FLOAT DEFAULT 1.0,
                    is_stale BOOLEAN DEFAULT FALSE,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_source_name ON data_source_health(source_name)"))
            conn.commit()

    def _seed_sources(self):
        for source in SOURCES:
            existing = self.session.query(DataSourceHealth).filter_by(source_name=source).first()
            if not existing:
                record = DataSourceHealth(source_name=source)
                self.session.add(record)
        self.session.commit()

    def record_success(self, source_name):
        record = self.session.query(DataSourceHealth).filter_by(source_name=source_name).first()
        if record:
            record.last_successful_fetch = datetime.now()
            record.consecutive_failures = 0
            record.last_error = None
            record.health_score = self.compute_health_score(source_name)
            self.session.commit()

    def record_failure(self, source_name, error_msg):
        record = self.session.query(DataSourceHealth).filter_by(source_name=source_name).first()
        if record:
            record.last_failed_attempt = datetime.now()
            record.consecutive_failures = (record.consecutive_failures or 0) + 1
            record.total_failures = (record.total_failures or 0) + 1
            record.last_error = str(error_msg)[:500]
            record.health_score = self.compute_health_score(source_name)
            self.session.commit()

    def compute_health_score(self, source_name):
        record = self.session.query(DataSourceHealth).filter_by(source_name=source_name).first()
        if not record:
            return 1.0
        cf = record.consecutive_failures or 0
        if cf >= 5:
            return 0.0
        return max(0.0, 1.0 - cf * 0.2)

    def check_stale(self, source_name, critical_hours=48, warning_hours=24):
        record = self.session.query(DataSourceHealth).filter_by(source_name=source_name).first()
        if not record or not record.last_successful_fetch:
            return {"is_stale": True, "stale_hours": None, "severity": "critical", "status": "never_fetched"}
        hours = (datetime.now() - record.last_successful_fetch).total_seconds() / 3600
        if hours >= critical_hours:
            return {"is_stale": True, "stale_hours": round(hours, 1), "severity": "critical", "status": "stale"}
        if hours >= warning_hours:
            return {"is_stale": True, "stale_hours": round(hours, 1), "severity": "warning", "status": "aging"}
        return {"is_stale": False, "stale_hours": round(hours, 1), "severity": "ok", "status": "fresh"}

    def get_all_source_health(self):
        records = self.session.query(DataSourceHealth).all()
        result = []
        for r in records:
            stale_info = self.check_stale(r.source_name)
            result.append({
                "source_name": r.source_name,
                "last_successful_fetch": r.last_successful_fetch,
                "last_failed_attempt": r.last_failed_attempt,
                "consecutive_failures": r.consecutive_failures,
                "total_failures": r.total_failures,
                "health_score": r.health_score,
                "is_stale": stale_info["is_stale"],
                "stale_hours": stale_info["stale_hours"],
                "severity": stale_info["severity"],
                "status": stale_info["status"],
                "last_error": r.last_error,
            })
        return result

    def get_stale_sources(self, critical_hours=48):
        all_health = self.get_all_source_health()
        stale = []
        for h in all_health:
            if h["is_stale"] and h["severity"] == "critical":
                stale.append(h)
        return stale

    def reject_if_stale(self, source_name):
        record = self.session.query(DataSourceHealth).filter_by(source_name=source_name).first()
        if record and record.is_stale:
            raise ValueError(f"Data source {source_name} is stale")

    def run_health_check(self):
        report = {"checked_at": datetime.now(), "sources": []}
        for source in SOURCES:
            stale_info = self.check_stale(source)
            self.session.query(DataSourceHealth).filter_by(source_name=source).update(
                {"is_stale": stale_info["is_stale"]}
            )
            self.session.commit()
            report["sources"].append(stale_info)
        stale_count = sum(1 for s in report["sources"] if s["is_stale"])
        report["stale_sources"] = stale_count
        report["status"] = "degraded" if stale_count > 0 else "healthy"
        return report

    def close(self):
        self.session.close()
