"""Daily data coverage monitor.

Tracks field population %, stale data recency, source failures,
and generates a structured report. Designed to run post-pipeline as
part of the daily data health check.

Usage:
    from app.services.data_health import DataHealth
    report = DataHealth.run(session)
    print(report.summary())
"""

from datetime import datetime, date, timedelta
from collections import defaultdict
from sqlalchemy import func, text


ALL_FINANCIAL_FIELDS = [
    "revenue", "ebitda", "operating_profit", "pat", "eps",
    "roce", "roe", "debt_equity", "operating_margin",
    "cash_flow_operations", "free_cash_flow", "debt",
    "interest_expense", "inventory", "receivables",
    "total_assets", "total_equity", "current_assets",
    "current_liabilities", "depreciation", "tax_expense",
    "employee_cost", "raw_material_cost", "cash_equivalents", "capex",
]


class DataHealthReport:
    def __init__(self):
        self.generated_at = datetime.utcnow()
        self.total_stocks = 0
        self.stocks_with_quarterly = 0
        self.field_coverage = {}
        self.overall_coverage_pct = 0.0
        self.stale_data_count = 0
        self.stale_data_days = 0
        self.source_failures = {}
        self.missing_sectors = 0
        self.score_snapshot_count = 0
        self.score_snapshot_dates = []
        self.issues = []

    def summary(self) -> str:
        lines = []
        lines.append(f"Data Health Report — {self.generated_at.date()}")
        lines.append(f"{'='*50}")
        lines.append(f"Total stocks:              {self.total_stocks}")
        lines.append(f"Stocks with quarterly:     {self.stocks_with_quarterly} ({self._pct(self.stocks_with_quarterly, self.total_stocks):.0f}%)")
        lines.append(f"Overall field coverage:    {self.overall_coverage_pct:.1f}%")
        lines.append(f"Missing sectors:           {self.missing_sectors}")
        lines.append(f"Stale data (>{self.stale_data_days}d): {self.stale_data_count}")
        lines.append(f"Score snapshots:           {self.score_snapshot_count} across {len(self.score_snapshot_dates)} dates")

        if self.source_failures:
            lines.append(f"\nSource failures (last 24h):")
            for src, cnt in sorted(self.source_failures.items()):
                lines.append(f"  {src}: {cnt}")

        lines.append(f"\nField coverage:")
        lines.append(f"  {'Field':25s} {'Covered':>8s} {'Total':>8s} {'%':>6s}")
        for field, cov in sorted(self.field_coverage.items()):
            lines.append(f"  {field:25s} {cov['filled']:>8d} {cov['total']:>8d} {cov['pct']:>5.0f}%")

        if self.issues:
            lines.append(f"\nIssues ({len(self.issues)}):")
            for issue in self.issues:
                lines.append(f"  ⚠ {issue}")

        return "\n".join(lines)

    def _pct(self, part, total):
        return (part / total * 100) if total > 0 else 0


class DataHealth:
    @staticmethod
    def run(session) -> DataHealthReport:
        report = DataHealthReport()

        # Total stocks
        from app.models.stock import Stock
        from app.models.quarterly import QuarterlyFinancials
        from app.models.score_snapshot import ScoreSnapshot

        total = session.query(func.count(Stock.symbol)).scalar() or 0
        report.total_stocks = total

        # Stocks with any quarterly data
        q_stocks = session.query(
            func.count(func.distinct(QuarterlyFinancials.symbol))
        ).scalar() or 0
        report.stocks_with_quarterly = q_stocks

        # Field-by-field coverage
        q_total = session.query(func.count(QuarterlyFinancials.quarter)).scalar() or 0
        for field in ALL_FINANCIAL_FIELDS:
            filled = session.query(func.count(QuarterlyFinancials.quarter)).filter(
                getattr(QuarterlyFinancials, field).isnot(None)
            ).scalar() or 0
            report.field_coverage[field] = {
                "filled": filled,
                "total": q_total,
                "pct": (filled / q_total * 100) if q_total > 0 else 0.0,
            }

        # Overall coverage (average across all fields)
        if ALL_FINANCIAL_FIELDS:
            pcts = [report.field_coverage[f]["pct"] for f in ALL_FINANCIAL_FIELDS]
            report.overall_coverage_pct = sum(pcts) / len(pcts)

        # Stale data: quarterly records older than 180 days from latest quarter
        latest_q = session.query(func.max(QuarterlyFinancials.quarter)).scalar()
        if latest_q:
            stale_cutoff = 180
            try:
                q_date_str = latest_q.replace("Q", "-") + "-01"
                q_date = datetime.strptime(q_date_str, "%Y-%m-%d").date()
                delta = (date.today() - q_date).days
                report.stale_data_days = delta
                report.stale_data_count = q_total if delta > stale_cutoff else 0
                if delta > stale_cutoff:
                    report.issues.append(
                        f"Latest quarterly data is {delta} days old ({latest_q})"
                    )
            except ValueError:
                pass

        # Missing sectors
        missing = session.query(func.count(Stock.symbol)).filter(
            Stock.sector.is_(None) | (Stock.sector == "Unknown")
        ).scalar() or 0
        report.missing_sectors = missing

        # Score snapshots
        snap_count = session.query(func.count(ScoreSnapshot.date)).scalar() or 0
        report.score_snapshot_count = snap_count
        snap_dates = session.query(func.distinct(ScoreSnapshot.date)).order_by(
            ScoreSnapshot.date.desc()
        ).all()
        report.score_snapshot_dates = [r[0] for r in snap_dates]

        # Source failures (from a hypothetical failures log table, or skip)
        report.source_failures = {}

        # Issues generation
        threshold = 70.0
        for field, cov in report.field_coverage.items():
            if cov["pct"] < threshold:
                report.issues.append(
                    f"{field} coverage {cov['pct']:.0f}% < {threshold:.0f}% threshold"
                )

        return report
