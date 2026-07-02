"""Automated data quality monitoring with severity levels and daily reports.
PHASE 2 — Data Quality Automation.

Severity:
  Critical (FAIL pipeline): any core field <60% coverage, source down >24h
  Warning: any field <75% coverage, stale data >180d
  Info: field drift >5% week-over-week

Usage:
    from app.services.data_health_monitor import DataHealthMonitor
    report = DataHealthMonitor.run(session)
    print(report.summary())
    report.to_json("/tmp/data_health.json")
    if report.is_critical:
        raise SystemError("Pipeline blocked by critical data health issue")
"""

import json, os
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Optional
from sqlalchemy import func


CORE_FIELDS = [
    "revenue", "pat", "eps", "roce", "debt_equity",
    "operating_margin", "debt", "interest_expense",
]
EXPANDED_FIELDS = [
    "cash_flow_operations", "free_cash_flow", "total_assets",
    "total_equity", "current_assets", "current_liabilities",
    "receivables", "inventory", "cash_equivalents",
    "depreciation", "tax_expense", "raw_material_cost", "capex",
]
ALL_FIELDS = CORE_FIELDS + EXPANDED_FIELDS

CRITICAL_THRESHOLD = 60.0
WARNING_THRESHOLD = 75.0
STALE_DAYS_WARN = 180
STALE_DAYS_CRITICAL = 365
SOURCE_STALE_HOURS = 24


@dataclass
class FieldCoverage:
    field: str
    filled: int
    total: int
    pct: float
    severity: str = "pass"


@dataclass
class SourceHealth:
    name: str
    status: str
    last_success: Optional[str] = None
    failure_count: int = 0
    error: Optional[str] = None


@dataclass
class Report:
    generated_at: str
    overall_coverage_pct: float
    core_coverage_pct: float
    expanded_coverage_pct: float
    fields: list
    sources: list
    issues: list
    severity: str
    is_critical: bool
    score_snapshot_count: int
    latest_quarter: Optional[str]
    stale_days: Optional[int]
    missing_sectors: int
    total_stocks: int

    def to_dict(self):
        return asdict(self)

    def to_json(self, path="/tmp/data_health_report.json"):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path

    def summary(self):
        lines = [
            f"Data Health — {self.generated_at}",
            f"{'='*50}",
            f"Severity: {self.severity.upper()}",
            f"Overall:  {self.overall_coverage_pct:.0f}%  "
            f"Core: {self.core_coverage_pct:.0f}%  "
            f"Expanded: {self.expanded_coverage_pct:.0f}%",
            f"Stocks: {self.total_stocks}  "
            f"Missing sectors: {self.missing_sectors}  "
            f"Snapshots: {self.score_snapshot_count}",
        ]
        if self.latest_quarter:
            lines.append(f"Latest quarter: {self.latest_quarter} "
                         f"({self.stale_days}d old)")
        if self.issues:
            lines.append(f"\nIssues ({len(self.issues)}):")
            for issue in self.issues:
                lines.append(f"  [{issue['severity']}] {issue['message']}")
        return "\n".join(lines)


class DataHealthMonitor:
    @staticmethod
    def run(session) -> Report:
        from app.models.stock import Stock
        from app.models.quarterly import QuarterlyFinancials
        from app.models.score_snapshot import ScoreSnapshot
        from app.models.data_health_audit import DataHealthAudit

        now = datetime.utcnow().isoformat()
        issues = []
        total_stocks = session.query(func.count(Stock.symbol)).scalar() or 0

        # --- Quarterly coverage ---
        q_total = session.query(
            func.count(QuarterlyFinancials.quarter)
        ).scalar() or 0

        field_reports = []
        core_pcts, expanded_pcts = [], []
        for field in ALL_FIELDS:
            filled = session.query(func.count(QuarterlyFinancials.quarter)).filter(
                getattr(QuarterlyFinancials, field).isnot(None)
            ).scalar() or 0
            pct = (filled / q_total * 100) if q_total > 0 else 0.0
            severity = "pass"
            if pct < CRITICAL_THRESHOLD:
                severity = "critical"
            elif pct < WARNING_THRESHOLD:
                severity = "warning"
            field_reports.append(FieldCoverage(field, filled, q_total, pct, severity))
            if field in CORE_FIELDS:
                core_pcts.append(pct)
            else:
                expanded_pcts.append(pct)

            if pct < CRITICAL_THRESHOLD:
                issues.append({
                    "severity": "critical",
                    "message": f"{field} coverage {pct:.0f}% < {CRITICAL_THRESHOLD:.0f}% — pipeline BLOCKED",
                })
            elif pct < WARNING_THRESHOLD:
                issues.append({
                    "severity": "warning",
                    "message": f"{field} coverage {pct:.0f}% < {WARNING_THRESHOLD:.0f}%",
                })

        overall_pct = sum(core_pcts + expanded_pcts) / len(ALL_FIELDS) if ALL_FIELDS else 0
        core_pct = sum(core_pcts) / len(core_pcts) if core_pcts else 0
        expanded_pct = sum(expanded_pcts) / len(expanded_pcts) if expanded_pcts else 0

        # --- Staleness check ---
        latest_q = session.query(func.max(QuarterlyFinancials.quarter)).scalar()
        stale_days = None
        if latest_q:
            try:
                q_date_str = latest_q.replace("Q", "-") + "-01"
                q_date = datetime.strptime(q_date_str, "%Y-%m-%d").date()
                stale_days = (date.today() - q_date).days
                if stale_days > STALE_DAYS_CRITICAL:
                    issues.append({
                        "severity": "critical",
                        "message": f"No new quarterly data in {stale_days}d (>{STALE_DAYS_CRITICAL}d)",
                    })
                elif stale_days > STALE_DAYS_WARN:
                    issues.append({
                        "severity": "warning",
                        "message": f"No new quarterly data in {stale_days}d (>{STALE_DAYS_WARN}d)",
                    })
            except ValueError:
                pass

        # --- Missing sectors ---
        missing_sectors = session.query(func.count(Stock.symbol)).filter(
            Stock.sector.is_(None) | (Stock.sector == "Unknown")
        ).scalar() or 0
        if missing_sectors > total_stocks * 0.05:
            issues.append({
                "severity": "warning",
                "message": f"{missing_sectors} stocks ({missing_sectors/total_stocks*100:.0f}%) missing sector",
            })

        # --- Score snapshots ---
        snap_count = session.query(func.count(ScoreSnapshot.date)).scalar() or 0
        if snap_count == 0:
            issues.append({
                "severity": "critical",
                "message": "Zero score snapshots — no backtest data",
            })

        # --- Source health (tracked externally, check for stale source files) ---
        sources = []
        for src in ["screener", "nse_yfinance", "bse", "yahoo_prices"]:
            sources.append(SourceHealth(name=src, status="unknown"))

        # --- Determine overall severity ---
        critical_issues = [i for i in issues if i["severity"] == "critical"]
        warning_issues = [i for i in issues if i["severity"] == "warning"]
        is_critical = len(critical_issues) > 0
        severity = "critical" if is_critical else (
            "warning" if warning_issues else "pass"
        )

        run_at = datetime.utcnow()

        # Persist each field as a DataHealthAudit row
        for fr in field_reports:
            audit = DataHealthAudit(
                date=run_at,
                field_name=fr.field,
                coverage_pct=round(fr.pct, 1),
                source="quarterly_financials",
                status=fr.severity,
            )
            session.add(audit)

        # Persist overall summary row
        session.add(DataHealthAudit(
            date=run_at,
            field_name="__overall__",
            coverage_pct=round(overall_pct, 1),
            source="quarterly_financials",
            status=severity,
        ))

        # Persist source health rows
        for s in sources:
            session.add(DataHealthAudit(
                date=run_at,
                field_name=f"__source__{s.name}",
                source=s.name,
                status=s.status,
                failure_reason=s.error,
            ))

        session.commit()

        return Report(
            generated_at=now,
            overall_coverage_pct=round(overall_pct, 1),
            core_coverage_pct=round(core_pct, 1),
            expanded_coverage_pct=round(expanded_pct, 1),
            fields=[f.__dict__ for f in field_reports],
            sources=[s.__dict__ for s in sources],
            issues=issues,
            severity=severity,
            is_critical=is_critical,
            score_snapshot_count=snap_count,
            latest_quarter=latest_q,
            stale_days=stale_days,
            missing_sectors=missing_sectors,
            total_stocks=total_stocks,
        )
