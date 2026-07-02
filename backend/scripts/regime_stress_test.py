"""Regime stress testing — P6.

Segments historical backtest by market regime and measures alpha
stability across: COVID crash 2020, Ukraine war 2022, small-cap bull 2024,
high inflation periods, FII selloff periods.

Requires: score_snapshots populated (run historical_backfill.py first).

Usage:
    python scripts/regime_stress_test.py
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from datetime import datetime, date
from collections import defaultdict
from scipy.stats import spearmanr
from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.portfolio_history import PortfolioHistory
from app.models.market_regime import MarketRegime

DB_SESSION = SessionLocal()

# Load all market regimes into memory
regime_rows = DB_SESSION.query(MarketRegime).order_by(MarketRegime.date).all()
print(f"Loaded {len(regime_rows)} regime records")
regime_map = {r.date: r.regime for r in regime_rows}

HORIZONS = [30, 60, 90, 120]

# Load snapshots and price data
snap_dates = [r[0] for r in DB_SESSION.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()]
all_prices = DB_SESSION.query(
    PriceHistory.symbol, PriceHistory.date, PriceHistory.close
).order_by(PriceHistory.symbol, PriceHistory.date).all()

# Load all snapshots into memory
snap_data = defaultdict(list)
for s in DB_SESSION.query(ScoreSnapshot).order_by(ScoreSnapshot.date).all():
    snap_data[s.date].append(s)

DB_SESSION.close()

price_map = defaultdict(list)
for sym, dt, close in all_prices:
    price_map[sym].append((dt, close))

print(f"Snapshot dates: {len(snap_dates)} — {snap_dates[0]} to {snap_dates[-1]}")


def get_future_return(symbol, as_of, trading_days=30):
    prices = price_map.get(symbol, [])
    start_idx = None
    for i, (dt, close) in enumerate(prices):
        if dt >= as_of:
            start_idx = i
            break
    if start_idx is None or start_idx + trading_days >= len(prices):
        return None
    entry = prices[start_idx][1]
    exit_ = prices[start_idx + trading_days][1]
    if entry is None or entry == 0:
        return None
    return (exit_ - entry) / entry


def regime_for_date(d):
    """Classify a date into a regime label using market_regime table, then fallback."""
    reg = regime_map.get(d)
    if reg:
        return reg
    return "Unknown"


RESULTS = {}

for trading_days in HORIZONS:
    print(f"\n{'='*60}")
    print(f"HORIZON: {trading_days} trading days")
    print(f"{'='*60}")

    by_regime = defaultdict(lambda: {
        "returns": [], "benchmark_returns": [], "ics": [], "hit_rates": []
    })

    for as_of in snap_dates:
        snaps = snap_data.get(as_of, [])
        if not snaps:
            continue
        stock_data = [(s.symbol, s.total_score or 0) for s in snaps]
        stock_data.sort(key=lambda x: -x[1])
        if len(stock_data) < 50:
            continue

        regime = regime_for_date(as_of)

        # Top 50 portfolio
        top_50 = [s for s in stock_data[:50]]
        bench = [s for s in stock_data]

        # Compute returns
        top_rets = []
        for sym, _ in top_50:
            r = get_future_return(sym, as_of, trading_days)
            if r is not None:
                top_rets.append(r)

        bench_rets = []
        for sym, _ in bench:
            r = get_future_return(sym, as_of, trading_days)
            if r is not None:
                bench_rets.append(r)

        if top_rets and bench_rets:
            by_regime[regime]["returns"].append(np.mean(top_rets))
            by_regime[regime]["benchmark_returns"].append(np.mean(bench_rets))

        # IC
        scores = [x[1] for x in stock_data]
        fwd_rets = []
        for sym, _ in stock_data:
            r = get_future_return(sym, as_of, trading_days)
            fwd_rets.append(r if r is not None else 0)
        mask = [r is not None for r in fwd_rets]
        if sum(mask) > 20:
            ic, _ = spearmanr([s for s, m in zip(scores, mask) if m],
                              [r for r, m in zip(fwd_rets, mask) if m])
            by_regime[regime]["ics"].append(ic)

        # Hit rate (top 20)
        top_20 = [get_future_return(sym, as_of, trading_days) for sym, _ in stock_data[:20]]
        top_20 = [r for r in top_20 if r is not None]
        if top_20:
            hit = sum(1 for r in top_20 if r > 0) / len(top_20)
            by_regime[regime]["hit_rates"].append(hit)

    # Print regime breakdown
    print(f"\n{'Regime':25s} {'Months':>6s} {'Port Return':>10s} {'Bench Return':>10s} {'Excess':>8s} {'Mean IC':>8s} {'Hit Rate':>8s}")
    for regime, data in sorted(by_regime.items()):
        n_m = len(data["returns"])
        if n_m < 2:
            continue
        p_ret = np.mean(data["returns"]) * 12 * 100  # annualized
        b_ret = np.mean(data["benchmark_returns"]) * 12 * 100
        excess = p_ret - b_ret
        mean_ic = np.mean(data["ics"]) if data["ics"] else 0
        hit = np.mean(data["hit_rates"]) * 100 if data["hit_rates"] else 0
        print(f"{regime:25s} {n_m:>6d} {p_ret:>9.1f}% {b_ret:>9.1f}% {excess:>7.1f}% {mean_ic:>7.3f} {hit:>7.1f}%")

    RESULTS[trading_days] = dict(by_regime)

# Save results
os.makedirs("reports", exist_ok=True)
summary = {}
for horizon, regimes in RESULTS.items():
    summary[horizon] = {}
    for regime, data in regimes.items():
        if len(data["returns"]) >= 2:
            summary[horizon][regime] = {
                "months": len(data["returns"]),
                "portfolio_return_annualized": round(float(np.mean(data["returns"])) * 12 * 100, 2),
                "benchmark_return_annualized": round(float(np.mean(data["benchmark_returns"])) * 12 * 100, 2),
                "excess_return": round(float(np.mean(data["returns"]) - float(np.mean(data["benchmark_returns"]))) * 12 * 100, 2),
                "mean_ic": round(float(np.mean(data["ics"])), 4),
                "hit_rate_pct": round(float(np.mean(data["hit_rates"])) * 100, 1),
                "volatility_annualized": round(float(np.std(data["returns"])) * math.sqrt(12) * 100, 2),
            }

with open("reports/regime_stress_test.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)
print(f"\nResults saved to reports/regime_stress_test.json")
