from sqlalchemy import text
from app.db.database import SessionLocal

CORE_FIELDS = [
    "roce",
    "roe",
    "debt_equity",
    "operating_margin",
    "revenue",
    "pat",
    "receivables",
    "inventory",
    "interest_expense",
    "operating_profit",
    "eps",
    "debt",
]


def validate_data_coverage(session) -> dict:
    """Check data coverage for core financial fields.
    Returns dict with field-level percentages and overall pass/fail status.
    Pipeline should reject if >30% missing in any core field."""
    qtotal = session.execute(text("SELECT COUNT(*) FROM quarterly_financials")).scalar()
    if not qtotal:
        return {"status": "fail", "reason": "No quarterly financials data", "fields": {}}

    results = {}
    all_ok = True
    for field in CORE_FIELDS:
        filled = session.execute(
            text(
                f"SELECT COUNT(*) FROM quarterly_financials "
                f"WHERE {field} IS NOT NULL AND {field} != 0"
            )
        ).scalar()
        pct = round(filled / qtotal * 100, 1)
        missing_pct = round(100 - pct, 1)
        ok = missing_pct <= 30
        if not ok:
            all_ok = False
        results[field] = {
            "filled": filled,
            "total": qtotal,
            "covered_pct": pct,
            "missing_pct": missing_pct,
            "ok": ok,
        }

    unique_stocks = session.execute(text("SELECT COUNT(DISTINCT symbol) FROM quarterly_financials")).scalar()
    total_stocks = session.execute(text("SELECT COUNT(*) FROM stocks_master")).scalar()

    return {
        "status": "pass" if all_ok else "fail",
        "stocks_with_data": unique_stocks,
        "total_stocks": total_stocks,
        "quarterly_records": qtotal,
        "fields": results,
    }


def validate_score_distribution(scored_stocks: list) -> dict:
    """Verify score distribution is statistically healthy.
    Raises ValueError if spread is too narrow."""
    if not scored_stocks:
        return {"status": "fail", "reason": "No scored stocks"}

    scores = [s.get("total_score", 0) for s in scored_stocks]
    scores_sorted = sorted(scores)
    n = len(scores_sorted)

    min_s = min(scores_sorted)
    max_s = max(scores_sorted)
    avg_s = round(sum(scores_sorted) / n, 2)

    p5 = scores_sorted[int(n * 0.05)]
    p25 = scores_sorted[int(n * 0.25)]
    p50 = scores_sorted[int(n * 0.50)]
    p75 = scores_sorted[int(n * 0.75)]
    p95 = scores_sorted[int(n * 0.95)]

    zeros = sum(1 for s in scores_sorted if s == 0)
    zero_pct = round(zeros / n * 100, 1)
    low_scores = sum(1 for s in scores_sorted if 0 < s <= 10)
    low_pct = round(low_scores / n * 100, 1)

    spread = max_s - min_s
    healthy_spread = spread >= 50
    not_too_many_zeros = zero_pct <= 40
    not_too_many_low = low_pct <= 60

    issues = []
    if not healthy_spread:
        issues.append(f"Spread too narrow: {spread} (need >=50)")
    if not not_too_many_zeros:
        issues.append(f"Too many zeros: {zero_pct}% (need <=40%)")
    if not not_too_many_low:
        issues.append(f"Too many low scores (0-10): {low_pct}% (need <=60%)")

    status = "pass" if not issues else "fail"

    return {
        "status": status,
        "issues": issues,
        "min": min_s,
        "max": max_s,
        "avg": avg_s,
        "p5": p5,
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p95": p95,
        "zero_pct": zero_pct,
        "low_score_pct": low_pct,
        "spread": spread,
        "count": n,
    }
