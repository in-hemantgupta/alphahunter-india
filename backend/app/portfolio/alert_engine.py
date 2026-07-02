from datetime import date, timedelta, datetime

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError

from app.db.database import SessionLocal
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.portfolio_position import PortfolioPosition
from app.models.rebalance_history import RebalanceHistory
from app.models.data_source_health import DataSourceHealth
from app.services.audit_logger import AuditLogger


class AlertEngine:
    def __init__(self):
        self.session = SessionLocal()
        self.ALERT_THRESHOLDS = {
            "drawdown_major": 15.0,
            "stale_data_hours": 24,
            "abnormal_turnover": 200,
            "sector_concentration": 25,
            "beta_breach": 1.2,
            "alpha_collapse_days": 21,
            "execution_slippage_bps": 50,
        }

    def _safe_query(self, func, default=None):
        try:
            return func()
        except (ProgrammingError, OperationalError):
            self.session.rollback()
            return default

    def check_drawdown(self):
        pm = self._safe_query(
            lambda: self.session.query(PortfolioMetrics).order_by(PortfolioMetrics.date.desc()).first()
        )
        if not pm or pm.drawdown is None:
            return None
        if pm.drawdown > self.ALERT_THRESHOLDS["drawdown_major"]:
            return {
                "category": "drawdown",
                "severity": "WARNING",
                "message": f"Drawdown at {pm.drawdown:.1f}%",
                "value": pm.drawdown,
                "threshold": self.ALERT_THRESHOLDS["drawdown_major"],
            }
        return None

    def check_stale_data(self):
        alerts = []
        sources = self._safe_query(
            lambda: self.session.query(DataSourceHealth).all(),
            default=[],
        )
        for src in sources:
            is_stale = bool(src.is_stale)
            if src.last_successful_fetch:
                hours_since = (datetime.now() - src.last_successful_fetch).total_seconds() / 3600
                if hours_since > self.ALERT_THRESHOLDS["stale_data_hours"]:
                    is_stale = True
            if src.health_score is not None and src.health_score < 0.5:
                is_stale = True
            if is_stale:
                severity = "CRITICAL" if (src.is_stale or (src.health_score is not None and src.health_score < 0.3)) else "WARNING"
                alerts.append({
                    "category": "stale_data",
                    "severity": severity,
                    "message": f"{src.source_name} stale (health={src.health_score}, is_stale={src.is_stale})",
                    "value": src.health_score,
                    "threshold": 0.5,
                })
        return alerts if alerts else None

    def check_turnover(self):
        since = date.today() - timedelta(days=30)
        rebalances = self._safe_query(
            lambda: self.session.query(RebalanceHistory).filter(
                RebalanceHistory.date >= since
            ).all(),
            default=[],
        )
        if not rebalances:
            return None
        total_change = sum(
            abs(r.new_weight - r.old_weight)
            for r in rebalances
            if r.new_weight is not None and r.old_weight is not None
        )
        annualized = (total_change / 2) * (365 / 30) * 100
        if annualized > self.ALERT_THRESHOLDS["abnormal_turnover"]:
            return {
                "category": "turnover",
                "severity": "WARNING",
                "message": f"Annualized turnover at {annualized:.0f}%",
                "value": round(annualized, 1),
                "threshold": self.ALERT_THRESHOLDS["abnormal_turnover"],
            }
        return None

    def check_sector_concentration(self):
        today = date.today()
        positions = self._safe_query(
            lambda: self.session.query(PortfolioPosition).filter(
                PortfolioPosition.date == today
            ).all(),
            default=[],
        )
        if not positions:
            return None
        sector_alloc = {}
        for p in positions:
            if p.allocation and p.sector:
                sector_alloc[p.sector] = sector_alloc.get(p.sector, 0) + p.allocation * 100
        alerts = []
        for sector, pct in sector_alloc.items():
            if pct > self.ALERT_THRESHOLDS["sector_concentration"]:
                alerts.append({
                    "category": "sector_concentration",
                    "severity": "WARNING",
                    "message": f"Sector {sector} at {pct:.1f}%",
                    "value": round(pct, 1),
                    "threshold": self.ALERT_THRESHOLDS["sector_concentration"],
                })
        return alerts if alerts else None

    def check_beta(self):
        today = date.today()
        positions = self._safe_query(
            lambda: self.session.query(PortfolioPosition).filter(
                PortfolioPosition.date == today,
                PortfolioPosition.beta.isnot(None),
            ).all(),
            default=[],
        )
        if not positions:
            return None
        total_alloc = sum(p.allocation for p in positions if p.allocation) or 0
        if total_alloc == 0:
            return None
        weighted_beta = (
            sum(p.beta * p.allocation for p in positions if p.allocation and p.beta) / total_alloc
        )
        if weighted_beta > self.ALERT_THRESHOLDS["beta_breach"]:
            return {
                "category": "beta",
                "severity": "WARNING",
                "message": f"Portfolio beta at {weighted_beta:.2f}",
                "value": round(weighted_beta, 2),
                "threshold": self.ALERT_THRESHOLDS["beta_breach"],
            }
        return None

    def check_alpha_collapse(self):
        metrics = self._safe_query(
            lambda: self.session.query(PortfolioMetrics).order_by(
                PortfolioMetrics.date.desc()
            ).limit(30).all(),
            default=[],
        )
        if len(metrics) < self.ALERT_THRESHOLDS["alpha_collapse_days"]:
            return None
        consecutive_neg = 0
        for pm in metrics:
            if pm.alpha is not None and pm.alpha < 0:
                consecutive_neg += 1
                if consecutive_neg >= self.ALERT_THRESHOLDS["alpha_collapse_days"]:
                    return {
                        "category": "alpha_collapse",
                        "severity": "CRITICAL",
                        "message": f"Alpha negative for {consecutive_neg} consecutive days",
                        "value": consecutive_neg,
                        "threshold": self.ALERT_THRESHOLDS["alpha_collapse_days"],
                    }
            else:
                consecutive_neg = 0
        return None

    def check_all(self):
        alerts = []

        drawdown = self.check_drawdown()
        if drawdown:
            alerts.append(drawdown)

        stale = self.check_stale_data()
        if stale:
            alerts.extend(stale)

        turnover = self.check_turnover()
        if turnover:
            alerts.append(turnover)

        sector = self.check_sector_concentration()
        if sector:
            alerts.extend(sector)

        beta = self.check_beta()
        if beta:
            alerts.append(beta)

        alpha_col = self.check_alpha_collapse()
        if alpha_col:
            alerts.append(alpha_col)

        audit = AuditLogger()
        for alert in alerts:
            status = alert["severity"].upper()
            audit.log(
                f"alert_{alert['category']}", "alert", status,
                details=alert["message"], source="alert_engine",
            )
        audit.close()

        return alerts

    def get_recent_alerts(self, hours=24):
        since = datetime.now() - timedelta(hours=hours)
        rows = self._safe_query(
            lambda: self.session.execute(text("""
                SELECT * FROM system_audit_log
                WHERE category = 'alert' AND timestamp >= :since
                ORDER BY timestamp DESC
            """), {"since": since}).fetchall(),
            default=[],
        )
        return [dict(r._mapping) for r in rows]

    def close(self):
        self.session.close()
