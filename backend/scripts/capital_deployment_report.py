"""Capital Deployment Report — final verdict on real money readiness.
Produces quantitative grade across 5 deployability categories.
Run after 60+ trading days of shadow fund data.
"""
import sys, os, json
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from app.db.database import SessionLocal
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.fund_nav import FundNav
from app.models.portfolio_position import PortfolioPosition
from app.models.rebalance_history import RebalanceHistory
from app.models.stock import Stock
from app.portfolio.shadow_fund import ShadowFund
from sqlalchemy import text

REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')

GRADE_THRESHOLDS = {
    "sharpe": {"Retail": 0.5, "PMS": 0.8, "AIF": 1.0, "Family Office": 1.2, "Institutional": 1.5},
    "alpha_pct": {"Retail": 3, "PMS": 5, "AIF": 8, "Family Office": 10, "Institutional": 12},
    "max_drawdown_pct": {"Retail": 25, "PMS": 20, "AIF": 15, "Family Office": 12, "Institutional": 10},
    "turnover_pct": {"Retail": 300, "PMS": 200, "AIF": 150, "Family Office": 120, "Institutional": 100},
    "data_coverage_pct": {"Retail": 50, "PMS": 60, "AIF": 70, "Family Office": 80, "Institutional": 90},
}


def load_shadow_fund_data():
    try:
        fund = ShadowFund()
        curve = fund.get_nav_curve()
        fund.close()
        return curve
    except Exception:
        return []


def load_metrics():
    try:
        session = SessionLocal()
        metrics = session.query(PortfolioMetrics).order_by(PortfolioMetrics.date).all()
        session.close()
        return metrics
    except Exception:
        return []


def compute_live_sharpe(metrics):
    returns = [m.daily_return for m in metrics if m.daily_return is not None]
    if len(returns) < 20:
        return None
    mean_ret = np.mean(returns)
    std_ret = np.std(returns)
    if std_ret == 0:
        return 0.0
    return round(float(mean_ret / std_ret * np.sqrt(252)), 2)


def compute_live_cagr(fund_curve):
    if not fund_curve or len(fund_curve) < 2:
        return None, None
    start_nav = fund_curve[0]["nav"]
    end_nav = fund_curve[-1]["nav"]
    start_date = fund_curve[0]["date"]
    end_date = fund_curve[-1]["date"]
    days = (end_date - start_date).days
    if days < 30:
        return None, None
    cagr = (end_nav / start_nav) ** (365 / days) - 1
    b_start = fund_curve[0]["benchmark_nav"]
    b_end = fund_curve[-1]["benchmark_nav"]
    bench_cagr = (b_end / b_start) ** (365 / days) - 1
    return round(float(cagr * 100), 2), round(float(bench_cagr * 100), 2)


def compute_alpha(cagr, bench_cagr):
    if cagr is None or bench_cagr is None:
        return None
    return round(cagr - bench_cagr, 2)


def compute_max_drawdown(fund_curve):
    navs = [r["nav"] for r in fund_curve if r["nav"]]
    if len(navs) < 5:
        return None
    peak = navs[0]
    max_dd = 0.0
    for n in navs:
        if n > peak:
            peak = n
        dd = (peak - n) / peak * 100
        max_dd = max(max_dd, dd)
    return round(float(max_dd), 2)


def compute_avg_turnover(metrics):
    turnovers = [m.turnover_annual for m in metrics if m.turnover_annual is not None]
    if not turnovers:
        return None
    return round(float(np.mean(turnovers)), 1)


def compute_hit_rate(metrics):
    returns = [m.daily_return for m in metrics if m.daily_return is not None]
    if not returns:
        return None
    positive = sum(1 for r in returns if r > 0)
    return round(positive / len(returns) * 100, 1)


def compute_execution_cost_drag(metrics):
    try:
        session = SessionLocal()
        rebalances = session.query(RebalanceHistory).filter(
            RebalanceHistory.date >= date.today() - timedelta(days=90)
        ).all()
        session.close()
        if not rebalances:
            return None
        total_change = sum(abs((r.new_weight or 0) - (r.old_weight or 0)) for r in rebalances)
        turnover = total_change * (365 / 90) * 100
        session = SessionLocal()
        stocks = dict((s.symbol, s.market_cap) for s in session.query(Stock).all())
        session.close()
        from app.portfolio.execution import total_cost_bps
        avg_cost = 60
        mcs = [stocks.get(s.symbol) for s in rebalances if s.symbol in stocks]
        if mcs:
            valid = [mc for mc in mcs if mc]
            if valid:
                avg_cost = int(np.mean([total_cost_bps(mc) for mc in valid]))
        drag = turnover * avg_cost / 10000
        return round(float(drag), 2), round(float(avg_cost), 1), round(float(turnover), 1)
    except Exception:
        return None


def compute_factor_persistence():
    session = SessionLocal()
    dates = [r[0] for r in session.execute(
        text("SELECT DISTINCT date FROM score_snapshots ORDER BY date DESC LIMIT 10")
    ).fetchall()]
    if len(dates) < 2:
        session.close()
        return None
    from scipy.stats import spearmanr
    factors = ["quality_score", "growth_score", "technical_score",
               "value_score", "forensic_score"]
    persistence = {}
    for f in factors:
        ranks = []
        for d in dates:
            rows = session.execute(text(
                f"SELECT symbol, {f} FROM score_snapshots WHERE date = :d ORDER BY {f} DESC"
            ), {"d": d}).fetchall()
            rank_map = {r[0]: i for i, r in enumerate(rows)}
            ranks.append(rank_map)
        correlations = []
        for i in range(len(ranks) - 1):
            common = set(ranks[i].keys()) & set(ranks[i + 1].keys())
            if len(common) > 10:
                r1 = [ranks[i][s] for s in common]
                r2 = [ranks[i + 1][s] for s in common]
                corr, _ = spearmanr(r1, r2)
                correlations.append(corr)
        if correlations:
            persistence[f.replace("_score", "")] = round(float(np.mean(correlations)), 2)
    session.close()
    return persistence


def compute_data_coverage():
    session = SessionLocal()
    snap_count = session.execute(text(
        "SELECT COUNT(DISTINCT symbol) FROM score_snapshots"
    )).scalar() or 0
    stock_count = session.execute(text(
        "SELECT COUNT(*) FROM stock"
    )).scalar() or 1
    session.close()
    return round(snap_count / stock_count * 100, 1)


def grade_deployability(metrics):
    grades = {}
    for metric, thresholds in GRADE_THRESHOLDS.items():
        grades[metric] = {}
        for level, threshold in thresholds.items():
            grades[metric][level] = threshold
    return grades


def assign_grade(value, thresholds):
    levels = ["Institutional", "Family Office", "AIF", "PMS", "Retail"]
    if value is None:
        return "Insufficient Data"
    for level in levels:
        if value >= thresholds[level]:
            return level
    return "Below Threshold"


def generate_report():
    os.makedirs(REPORT_DIR, exist_ok=True)
    print("=" * 60)
    print("  CAPITAL DEPLOYMENT READINESS REPORT")
    print("=" * 60)

    fund_curve = load_shadow_fund_data()
    metrics = load_metrics()
    thresholds = GRADE_THRESHOLDS

    if len(fund_curve) < 20:
        print(f"\n  WARNING: Only {len(fund_curve)} trading days of data.")
        print("  Report requires 60+ days for reliable verdict.")
        print("  Running with available data for framework validation.\n")

    cagr, bench_cagr = compute_live_cagr(fund_curve)
    alpha = compute_alpha(cagr, bench_cagr)
    sharpe = compute_live_sharpe(metrics)
    max_dd = compute_max_drawdown(fund_curve)
    turnover = compute_avg_turnover(metrics)
    hit_rate = compute_hit_rate(metrics)
    cost_drag = compute_execution_cost_drag(metrics)
    factor_pers = compute_factor_persistence()
    data_cov = compute_data_coverage()

    print(f"  {'Metric':<30} {'Value':<15} {'Grade':<20}")
    print(f"  {'-'*65}")

    def grade_line(label, value, grade_key, fmt=".2f"):
        thresholds_dict = thresholds.get(grade_key, {})
        g = assign_grade(value, thresholds_dict) if value is not None else "N/A"
        val_str = f"{value:{fmt}}" if value is not None else "N/A"
        print(f"  {label:<30} {val_str:<15} {g:<20}")
        return g

    sharpe_grade = grade_line("Sharpe Ratio", sharpe, "sharpe")
    alpha_grade = grade_line("Alpha (CAGR %)", alpha, "alpha_pct")
    dd_grade = grade_line("Max Drawdown %", max_dd, "max_drawdown_pct")
    to_grade = grade_line("Turnover (ann %)", turnover, "turnover_pct")
    dc_grade = grade_line("Data Coverage %", data_cov, "data_coverage_pct")

    print(f"\n  Additional Metrics:")
    print(f"    {'Portfolio CAGR':<30} {cagr or 'N/A'}")
    print(f"    {'Benchmark CAGR':<30} {bench_cagr or 'N/A'}")
    print(f"    {'Hit Rate %':<30} {hit_rate or 'N/A'}")
    if cost_drag:
        print(f"    {'Execution Cost Drag %':<30} {cost_drag[0]}")
        print(f"    {'Avg Cost bps':<30} {cost_drag[1]}")
        print(f"    {'Turnover (90d ann %)':<30} {cost_drag[2]}")
    if factor_pers:
        print(f"    {'Factor Persistence (avg rank corr)':<30}")
        for f, c in sorted(factor_pers.items(), key=lambda x: -x[1]):
            print(f"      {f:<25} {c:.2f}")

    grades = {
        "sharpe": sharpe_grade, "alpha": alpha_grade,
        "drawdown": dd_grade, "turnover": to_grade,
        "data_coverage": dc_grade,
    }
    level_order = ["Institutional", "Family Office", "AIF", "PMS", "Retail", "Below Threshold", "Insufficient Data"]
    level_scores = {l: 0 for l in level_order}
    for g in grades.values():
        if g in level_scores:
            level_scores[g] += 1

    overall = "Retail"
    for l in level_order:
        if level_scores[l] >= 3:
            overall = l

    print(f"\n  {'='*60}")
    print(f"  OVERALL VERDICT: {overall.upper()} DEPLOYABLE")
    print(f"  {'='*60}")

    verdict_map = {
        "Institutional": "Suitable for institutional capital (>₹100Cr). Full compliance grade.",
        "Family Office": "Suitable for family office / HNI capital (₹10-100Cr). Minor gaps.",
        "AIF": "Suitable for AIF / PMS structure (₹1-10Cr). Category 3 AIF ready.",
        "PMS": "Suitable for PMS deployment (₹50L-₹1Cr). Additional monitoring needed.",
        "Retail": "Suitable for retail deployment (<₹50L). Not institutional grade.",
        "Below Threshold": "Not deployable. Multiple metrics below minimum thresholds.",
        "Insufficient Data": "Cannot determine. Collect 60+ trading days of data.",
    }
    print(f"  {verdict_map.get(overall, 'Unknown')}")

    cost_drag_dict = None
    if cost_drag:
        cost_drag_dict = {"drag_pct": cost_drag[0], "avg_cost_bps": cost_drag[1], "turnover_pct": cost_drag[2]}

    report = {
        "generated_at": str(date.today()),
        "n_days_data": len(fund_curve),
        "metrics": {
            "cagr_pct": cagr,
            "benchmark_cagr_pct": bench_cagr,
            "alpha_pct": alpha,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd,
            "turnover_annual_pct": turnover,
            "hit_rate_pct": hit_rate,
            "execution_cost_drag": cost_drag_dict,
            "factor_persistence": factor_pers,
            "data_coverage_pct": data_cov,
        },
        "grades": grades,
        "overall_verdict": overall,
        "verdict_description": verdict_map.get(overall, ""),
        "deployment_categories": {
            "retail": overall in ["Retail", "PMS", "AIF", "Family Office", "Institutional"],
            "pms": overall in ["PMS", "AIF", "Family Office", "Institutional"],
            "aif": overall in ["AIF", "Family Office", "Institutional"],
            "family_office": overall in ["Family Office", "Institutional"],
            "institutional": overall == "Institutional",
        },
    }

    report_path = os.path.join(REPORT_DIR, "capital_deployment_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_path}")
    return report


if __name__ == "__main__":
    generate_report()
