"""Capital stress test — simulates system scaling across AUM levels."""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'
from datetime import date, timedelta
from collections import defaultdict
import numpy as np
from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.portfolio_position import PortfolioPosition
from app.models.price_history import PriceHistory
from app.portfolio.execution import get_cost_tier, total_cost_bps

AUM_SCENARIOS = [
    ("10 Lakh", 10_00_000),
    ("50 Lakh", 50_00_000),
    ("1 Crore", 1_00_00_000),
    ("5 Crore", 5_00_00_000),
    ("10 Crore", 10_00_00_000),
]


def get_portfolio_data():
    session = SessionLocal()
    try:
        stocks = session.query(Stock).filter(Stock.market_cap.isnot(None)).all()
        cutoff = date.today() - timedelta(days=40)
        price_rows = session.query(
            PriceHistory.symbol, PriceHistory.close, PriceHistory.date, PriceHistory.volume
        ).filter(PriceHistory.date >= cutoff).all()

        daily_values = defaultdict(list)
        for row in price_rows:
            if row.close and row.volume:
                daily_values[row.symbol].append(row.close * row.volume)

        data = []
        for s in stocks:
            dv = daily_values.get(s.symbol, [])
            avg_dv = float(np.mean(dv)) if dv else 1_00_00_000
            data.append({
                "symbol": s.symbol,
                "market_cap": s.market_cap,
                "tier": get_cost_tier(s.market_cap),
                "avg_daily_value": avg_dv,
            })
        return data
    finally:
        session.close()


def compute_slippage(position_size, avg_daily_value):
    if avg_daily_value <= 0:
        return 200
    pct = (position_size / avg_daily_value) * 100
    if pct < 1:
        return 5
    elif pct < 5:
        return 15
    elif pct < 10:
        return 30
    elif pct < 20:
        return 60
    return 200


def compute_cost_drag(turnover_pct, cost_bps, slippage_bps):
    execution_drag = turnover_pct * cost_bps / 10000
    slippage_drag = turnover_pct * slippage_bps / 10000
    total_drag = execution_drag + slippage_drag
    return round(execution_drag, 2), round(slippage_drag, 2), round(total_drag, 2)


def run_stress_test():
    portfolio = get_portfolio_data()
    session = SessionLocal()
    try:
        latest_pos = session.query(PortfolioPosition.date).order_by(PortfolioPosition.date.desc()).first()
        if latest_pos:
            pos_count = session.query(PortfolioPosition).filter(
                PortfolioPosition.date == latest_pos[0]
            ).count()
        else:
            pos_count = 30
    except Exception:
        pos_count = 30
    finally:
        session.close()

    scenarios = {}
    for label, aum in AUM_SCENARIOS:
        avg_pos_size = aum / pos_count if pos_count > 0 else 0
        days_list, slip_list, cost_list = [], [], []
        tier_counts = defaultdict(int)
        high_slip_count = 0

        for p in portfolio:
            tier_counts[p["tier"]] += 1
            slip = compute_slippage(avg_pos_size, p["avg_daily_value"])
            days_list.append(avg_pos_size / p["avg_daily_value"])
            slip_list.append(slip)
            cost_list.append(total_cost_bps(p["market_cap"]))
            if slip >= 100:
                high_slip_count += 1

        avg_days = float(np.mean(days_list)) if days_list else 0
        avg_slip = float(np.mean(slip_list)) if slip_list else 0
        avg_cost = float(np.mean(cost_list)) if cost_list else 0
        exec_drag, slip_drag, total_drag = compute_cost_drag(150.0, avg_cost, avg_slip)

        constraints = []
        capacity_ok = avg_days < 10 and avg_slip < 100
        if avg_days > 10:
            constraints.append(f"Avg days to build ({avg_days:.1f}) exceeds 10-day limit")
        micro_ratio = tier_counts.get("D", 0) / len(portfolio) if portfolio else 0
        if micro_ratio > 0.30:
            constraints.append(f"Micro-cap (Tier D) at {micro_ratio*100:.0f}% exceeds 30% limit")
        if high_slip_count > 0:
            pct_breached = high_slip_count / len(portfolio) * 100 if portfolio else 0
            constraints.append(f"{high_slip_count}/{len(portfolio)} ({pct_breached:.1f}%) positions exceed 20% of daily volume (slippage >= 100bps)")

        scenarios[label] = {
            "aum": aum,
            "position_count": pos_count,
            "avg_position_size": round(avg_pos_size, 2),
            "tier_breakdown": dict(tier_counts),
            "avg_days_to_build": round(avg_days, 2),
            "avg_slippage_bps": round(avg_slip, 1),
            "avg_cost_bps": round(avg_cost, 1),
            "execution_drag_pct": exec_drag,
            "slippage_drag_pct": slip_drag,
            "total_drag_pct": total_drag,
            "capacity_ok": capacity_ok,
            "constraints": constraints,
        }

    max_deployable = 0
    max_reason = ""
    for label, aum in reversed(AUM_SCENARIOS):
        if scenarios[label]["capacity_ok"]:
            max_deployable = aum
            break

    if max_deployable == 0:
        max_deployable = AUM_SCENARIOS[0][1]
        max_reason = "All AUM scenarios breached capacity constraints. Deploy minimum capital only."
    elif max_deployable >= 10_00_00_000:
        max_reason = "Bottleneck: mid/small-cap position sizing relative to daily trading volume limits further scaling."
    elif max_deployable >= 5_00_00_000:
        pct_breached = scenarios[label].get("constraints", [])
        max_reason = "Bottleneck: days-to-build threshold for micro-cap holdings at higher AUM."
    else:
        max_reason = "Bottleneck: limited by low position count and micro-cap liquidity depth."

    recommendation = (
        f"Deploy up to Rs {max_deployable/1e7:.1f} Crore. "
        f"To scale further: increase position count above {pos_count}, "
        f"filter out Tier D micro-caps, or accept longer build periods (>10 days)."
    )

    return {
        "generated_at": str(date.today()),
        "current_portfolio_value": None,
        "nifty_benchmark_value": None,
        "scenarios": scenarios,
        "maximum_deployable_capital": max_deployable,
        "capacity_limit_reason": max_reason,
        "recommendation": recommendation,
    }


def print_report(result):
    print("\n" + "=" * 72)
    print("  CAPITAL STRESS TEST REPORT")
    print("=" * 72)
    print(f"  Generated: {result['generated_at']}")
    print(f"  Maximum Deployable Capital: Rs {result['maximum_deployable_capital']/1e7:.1f} Crore")
    print(f"  Capacity Limit: {result['capacity_limit_reason']}")

    print("\n  AUM vs Cost & Liquidity")
    print("  " + "-" * 72)
    print(f"  {'Scenario':18s} {'AUM':>10s} {'Pos':>5s} {'Days2B':>8s} {'Slip(bp)':>9s} {'Cost(bp)':>9s} {'Drag%':>7s} {'OK':>5s}")
    print("  " + "-" * 72)
    for label, sc in result["scenarios"].items():
        aum_str = f"Rs {sc['aum']/1e7:.1f}C"
        ok_str = "YES" if sc["capacity_ok"] else "NO"
        print(f"  {label:18s} {aum_str:>10s} {sc['position_count']:>5d} "
              f"{sc['avg_days_to_build']:>8.2f} {sc['avg_slippage_bps']:>8.1f} "
              f"{sc['avg_cost_bps']:>8.1f} {sc['total_drag_pct']:>6.2f} {ok_str:>5s}")

    print("\n  " + "-" * 72)
    print("  CONSTRAINTS")
    print("  " + "-" * 72)
    any_constraints = False
    for label, sc in result["scenarios"].items():
        if sc["constraints"]:
            any_constraints = True
            print(f"\n  {label}:")
            for c in sc["constraints"]:
                print(f"    ! {c}")
    if not any_constraints:
        print("  No constraints breached at any AUM level.")

    print(f"\n  {'-'*72}")
    print("  RECOMMENDATION")
    print(f"  {'-'*72}")
    print(f"  {result['recommendation']}")
    print()


if __name__ == "__main__":
    result = run_stress_test()
    print_report(result)
    output_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'capital_stress_test.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Report saved to {output_path}")
