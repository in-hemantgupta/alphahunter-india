import json
from datetime import date, timedelta, datetime

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError

from app.db.database import SessionLocal, engine
from app.models.kill_switch_state import KillSwitchState
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.data_source_health import DataSourceHealth
from app.services.audit_logger import AuditLogger


class KillSwitch:
    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self._ensure_table()
        self._load_state()

    def _ensure_table(self):
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

    def _load_state(self):
        row = self.session.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
        self.state = row

    def _safe_query(self, func, default=None):
        try:
            return func()
        except (ProgrammingError, OperationalError):
            self.session.rollback()
            return default

    def check_conditions(self, as_of=None):
        check_date = as_of or date.today()
        violations = []

        latest = self._safe_query(
            lambda: self.session.query(PortfolioMetrics).order_by(PortfolioMetrics.date.desc()).first()
        )

        sharpe_val = latest.sharpe_30d if latest else None
        violations.append({
            "condition": "sharpe_30d",
            "current_value": sharpe_val,
            "threshold": 0,
            "breached": sharpe_val is not None and sharpe_val < 0
        })

        dd_val = latest.drawdown if latest else None
        violations.append({
            "condition": "drawdown",
            "current_value": dd_val,
            "threshold": 20,
            "breached": dd_val is not None and dd_val > 20
        })

        rebalance_dates = self._safe_query(
            lambda: self.session.execute(
                text("SELECT DISTINCT date FROM rebalance_history ORDER BY date DESC LIMIT 5")
            ).fetchall(),
            default=[],
        )
        dates = [r[0] for r in rebalance_dates]
        neg_streak = 0
        max_streak = 0
        for d in dates:
            pm = self._safe_query(
                lambda d=d: self.session.query(PortfolioMetrics).filter(PortfolioMetrics.date == d).first()
            )
            if pm and pm.alpha is not None and pm.alpha < 0:
                neg_streak += 1
                max_streak = max(max_streak, neg_streak)
            else:
                neg_streak = 0
        violations.append({
            "condition": "3_consecutive_bad_rebalances",
            "current_value": max_streak,
            "threshold": 3,
            "breached": max_streak >= 3
        })

        recent_alphas = self._safe_query(
            lambda: self.session.query(PortfolioMetrics).order_by(
                PortfolioMetrics.date.desc()
            ).limit(30).all(),
            default=[],
        )
        all_negative = (
            len(recent_alphas) >= 30
            and all(pm.alpha is not None and pm.alpha < 0 for pm in recent_alphas)
        )
        neg_count = sum(1 for pm in recent_alphas if pm.alpha is not None and pm.alpha < 0)
        violations.append({
            "condition": "alpha_negative_30_days",
            "current_value": neg_count,
            "threshold": 30,
            "breached": all_negative
        })

        stale_sources = self._safe_query(
            lambda: self.session.query(DataSourceHealth).filter(
                DataSourceHealth.is_stale == True
            ).all(),
            default=[],
        )
        violations.append({
            "condition": "data_stale",
            "current_value": len(stale_sources),
            "threshold": 0,
            "breached": len(stale_sources) > 0
        })

        since_24h = datetime.now() - timedelta(hours=24)
        failures = self._safe_query(
            lambda: self.session.execute(text("""
                SELECT COUNT(*) FROM system_audit_log
                WHERE status = 'FAILURE' AND timestamp >= :since
            """), {"since": since_24h}).scalar(),
            default=0,
        )
        violations.append({
            "condition": "circuit_breakers_failing",
            "current_value": failures or 0,
            "threshold": 5,
            "breached": (failures or 0) > 5
        })

        breached_count = sum(1 for v in violations if v["breached"])
        return {
            "is_safe": breached_count == 0,
            "violations": violations,
            "breached_count": breached_count,
        }

    def engage(self, triggered_by, conditions):
        now = datetime.now()
        auto_disarm = now + timedelta(days=7)
        state = KillSwitchState(
            is_engaged=True,
            engaged_at=now,
            triggered_by=triggered_by,
            conditions_json=json.dumps(conditions, default=str),
            auto_disarm_at=auto_disarm,
        )
        self.session.add(state)
        self.session.commit()
        self._load_state()

        audit = AuditLogger()
        audit.log(
            "kill_switch_engaged", "kill_switch", "CRITICAL",
            details=f"Kill switch triggered by {triggered_by}",
            source="kill_switch",
        )
        audit.close()

        print(f"*** KILL SWITCH ENGAGED ***")
        print(f"Triggered by: {triggered_by}")
        print(f"Auto-disarm at: {auto_disarm}")

    def disengage(self):
        if not self.state:
            return
        self.session.execute(
            text("UPDATE kill_switch_state SET is_engaged = False, disarmed_at = :now WHERE id = :id"),
            {"now": datetime.now(), "id": self.state.id},
        )
        self.session.commit()
        self._load_state()

        audit = AuditLogger()
        audit.log(
            "kill_switch_disengaged", "kill_switch", "INFO",
            details="Kill switch manually disarmed",
            source="kill_switch",
        )
        audit.close()

        print("*** KILL SWITCH DISENGAGED ***")

    def is_trading_suspended(self):
        if not self.state or not self.state.is_engaged:
            return False
        if self.state.auto_disarm_at and datetime.now() > self.state.auto_disarm_at:
            return False
        return True

    def get_state(self):
        if not self.state:
            return {"is_engaged": False}
        return {
            "is_engaged": self.state.is_engaged,
            "engaged_at": str(self.state.engaged_at) if self.state.engaged_at else None,
            "triggered_by": self.state.triggered_by,
            "auto_disarm_at": str(self.state.auto_disarm_at) if self.state.auto_disarm_at else None,
            "disarmed_at": str(self.state.disarmed_at) if self.state.disarmed_at else None,
            "created_at": str(self.state.created_at) if self.state.created_at else None,
        }

    def check_and_engage(self, as_of=None):
        result = self.check_conditions(as_of=as_of)
        if result["breached_count"] > 0:
            breached = [v for v in result["violations"] if v["breached"]]
            triggered_by = breached[0]["condition"] if breached else "unknown"
            self.engage(triggered_by=triggered_by, conditions=result)
            result["action_taken"] = "engaged"
        else:
            result["action_taken"] = "none"
        return result

    def close(self):
        self.session.close()
