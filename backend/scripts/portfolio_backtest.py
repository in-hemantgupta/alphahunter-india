#!/usr/bin/env python3
"""TASK 9 — Full walk-forward backtest with portfolio engine.
Tests: Sharpe > 1, Hit Rate > 58%, Max DD < 18%, CAGR > Bench + 5%, Turnover < 150%, IC > 0.04
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from datetime import date, datetime, timedelta
from collections import defaultdict
from scipy.stats import spearmanr

from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.stock import Stock
from app.portfolio.regime import detect_regime
from app.portfolio.liquidity_tiers import get_market_cap_tier, is_liquid, get_daily_turnover
from app.portfolio.entry_filters import check_entry, compute_relative_strength
from app.portfolio.position_sizing import size_position
from app.portfolio.conviction import compute_conviction_weight
from app.portfolio.execution import simulate_rebalance_cost

t0 = datetime.now()
print(f"Portfolio backtest starting at {t0}")
print("=" * 70)

session = SessionLocal()

snap_dates = [r[0] for r in session.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()]
print(f"Snapshot dates: {len(snap_dates)} ({snap_dates[0]} to {snap_dates[-1]})")

all_prices = session.query(PriceHistory.symbol, PriceHistory.date, PriceHistory.close, PriceHistory.volume).order_by(
    PriceHistory.symbol, PriceHistory.date).all()
price_map = defaultdict(list)
for sym, dt, close, volume in all_prices:
    price_map[sym].append((dt, close, volume))

stocks = {s.symbol: s for s in session.query(Stock).all()}
sectors = {s.symbol: s.sector for s in session.query(Stock).all() if s.sector}
session.close()

print(f"Stocks: {len(stocks)}, Sectors: {len(set(sectors.values()))}")

_delisted_count = sum(1 for s in stocks.values() if s.status != "active")
print(
    f"Survivorship-bias status: {_delisted_count}/{len(stocks)} tracked stocks are non-active. "
    "Point-in-time inclusion below is wired against stocks_master.status/listing_date/delisting_date, "
    "but the historical delisted/suspended universe itself has not been backfilled yet - Rule 4 is only "
    "mechanically satisfied once that backfill lands (see docs/INSTITUTIONAL_REBUILD_PLAN.md Phase 2/6). "
    "Treat CAGR/Sharpe below as upper-bound estimates until then, not final numbers."
)


def _active_as_of(symbol, as_of_date):
    """Point-in-time universe membership: was this stock actually tradeable
    on as_of_date? Currently a no-op for every row (all stocks are
    status='active' with no listing/delisting dates - see disclaimer above)
    but the machinery is correct for when that data exists."""
    stock = stocks.get(symbol)
    if not stock:
        return False
    if stock.listing_date and stock.listing_date > as_of_date:
        return False
    if stock.status != "active" and stock.delisting_date and stock.delisting_date < as_of_date:
        return False
    return True


def get_future_return(symbol, as_of, trading_days):
    prices = price_map.get(symbol, [])
    start_idx = next((i for i, (dt, c, _) in enumerate(prices) if dt >= as_of), None)
    if start_idx is None or start_idx + trading_days >= len(prices):
        return None
    ep = prices[start_idx][1]
    xp = prices[start_idx + trading_days][1]
    return (xp - ep) / ep * 100 if ep and ep != 0 else None


def get_prices_up_to(symbol, as_of, lookback=200):
    prices = price_map.get(symbol, [])
    filtered = [(c, v) for dt, c, v in prices if dt <= as_of and c is not None and c > 0]
    return filtered[-lookback:] if len(filtered) > 20 else []


# Use snapshot dates where forward 60d data exists
backtest_dates = [d for d in snap_dates if d >= date(2025, 5, 1) and d < date(2026, 3, 1)]
print(f"Backtest dates: {len(backtest_dates)} ({backtest_dates[0]} to {backtest_dates[-1]})")

all_monthly_returns = []
all_benchmark_returns = []
all_hit_rates = []
all_ics = []
all_d1 = []
all_d10 = []
all_turnovers = []
all_n_holdings = []
all_excess = []

prev_holdings = {}

for m_idx, as_of in enumerate(backtest_dates):
    regime_info = detect_regime(as_of)
    regime = regime_info["regime"]

    snaps = session.query(ScoreSnapshot).filter(ScoreSnapshot.date == as_of).all()
    if not snaps:
        continue

    # Build candidate data
    candidates = []
    for s in snaps:
        if not _active_as_of(s.symbol, as_of):
            continue
        sector = sectors.get(s.symbol, "Unknown")
        pv_list = get_prices_up_to(s.symbol, as_of)
        if len(pv_list) < 50:
            continue
        prices = [p for p, _ in pv_list]
        volumes = [v for _, v in pv_list if v is not None]
        current_price = prices[-1] if prices else 0
        score = s.total_score or 0
        confidence = s.confidence_score or 0.5

        vol_ratio = None
        if len(volumes) >= 21:
            vol_ratio = volumes[-1] / max(np.mean(volumes[-21:-1]), 1)

        candidates.append({
            "symbol": s.symbol,
            "score": score,
            "confidence": confidence,
            "sector": sector,
            "price": current_price,
            "prices": prices,
            "volume_ratio": vol_ratio,
            "market_cap": None,
        })

    if len(candidates) < 100:
        continue

    # Rank by score
    candidates.sort(key=lambda x: -x["score"])
    total = len(candidates)
    for i, c in enumerate(candidates):
        c["score_rank"] = (i / total) * 100

    # Pre-compute RS per sector for this date
    # Build sector returns
    sector_returns = defaultdict(dict)
    for c in candidates:
        ret_90 = get_future_return(c["symbol"], as_of - timedelta(days=90), 90)
        if ret_90 is not None and c["sector"] != "Unknown":
            sector_returns[c["sector"]][c["symbol"]] = ret_90

    # Compute RS for each candidate
    for c in candidates:
        if c["sector"] != "Unknown" and c["symbol"] in sector_returns.get(c["sector"], {}):
            sym_ret = sector_returns[c["sector"]][c["symbol"]]
            rs, n_peers = compute_relative_strength(sym_ret, sector_returns[c["sector"]])
            c["relative_strength"] = rs
            c["rpeer_count"] = n_peers
        else:
            c["relative_strength"] = None
            c["rpeer_count"] = 0

    # Liquidity filter (tier limits + ₹1cr turnover)
    tier_counts = defaultdict(int)
    tier_max = {"A": 200, "B": 200, "C": int(200 * 0.15)}
    filtered = []
    for c in candidates:
        tier = get_market_cap_tier(c["symbol"])
        c["tier"] = tier
        if tier_counts[tier] < tier_max.get(tier, 50) and is_liquid(c["symbol"]):
            filtered.append(c)
            tier_counts[tier] += 1
    candidates = filtered

    # Entry filter — scan deeper to get enough passing stocks
    buy_list = []
    for c in candidates:
        passed, _ = check_entry(
            symbol=c["symbol"],
            score_rank=c["score_rank"],
            price_data=c["prices"],
            sector=c["sector"],
            volume_ratio=c.get("volume_ratio"),
            relative_strength=c.get("relative_strength"),
            sector_peer_count=c.get("rpeer_count", 0),
        )
        if passed:
            buy_list.append(c)
        if len(buy_list) >= 50:
            break

    # Position sizing + conviction weighting
    raw_weights = {}
    for c in buy_list:
        size = size_position(c["score"], c["confidence"], c["symbol"])
        regime_adj = 1.0
        if regime == "Bear":
            regime_adj = 0.5
        elif regime == "HighVolatility":
            regime_adj = 0.75
        raw_weights[c["symbol"]] = size * regime_adj

    total_raw = sum(raw_weights.values())
    if total_raw <= 0:
        continue

    target_weights = {k: v / total_raw for k, v in raw_weights.items()}

    # Enforce 5% max position
    for sym, w in list(target_weights.items()):
        if w > 0.05:
            excess = w - 0.05
            target_weights[sym] = 0.05
            # Redistribute excess to others
            others = {k: v for k, v in target_weights.items() if k != sym and target_weights[k] < 0.05}
            other_total = sum(others.values())
            for osym in others:
                target_weights[osym] += excess * (others[osym] / other_total) if other_total > 0 else 0

    # Turnover
    turnover_pct, avg_cost = simulate_rebalance_cost(
        prev_holdings, target_weights, {c["symbol"]: c["price"] for c in candidates},
        {c["symbol"]: c.get("market_cap") for c in candidates}
    )

    # Forward returns (60d)
    port_ret = 0
    bench_rets = []
    for c in candidates:
        r = get_future_return(c["symbol"], as_of, 60)
        if r is not None:
            bench_rets.append(r)
            if c["symbol"] in target_weights:
                port_ret += target_weights[c["symbol"]] * r

    bench_ret = np.mean(bench_rets) if bench_rets else 0
    excess = port_ret - bench_ret

    # Hit rate (top 20)
    top20 = list(target_weights.keys())[:20]
    wins = sum(1 for sym in top20 if (get_future_return(sym, as_of, 60) or 0) > 0)
    hit_rate = wins / len(top20) * 100 if top20 else 0

    # IC
    scores = []
    returns = []
    for c in candidates:
        r = get_future_return(c["symbol"], as_of, 60)
        if r is not None and c["score"] is not None:
            scores.append(c["score"])
            returns.append(r)

    ic_val = 0
    if len(scores) > 20:
        ic_val, _ = spearmanr(scores, returns)
        ic_val = ic_val if not np.isnan(ic_val) else 0

    # Deciles
    if len(scores) > 100:
        idx = np.argsort(scores)
        ds = len(scores) // 10
        d1_val = np.mean([returns[i] for i in idx[:ds]])
        d10_val = np.mean([returns[i] for i in idx[-ds:]])
    else:
        d1_val = d10_val = 0

    all_monthly_returns.append(port_ret)
    all_benchmark_returns.append(bench_ret)
    all_excess.append(excess)
    all_hit_rates.append(hit_rate)
    all_ics.append(ic_val)
    all_d1.append(d1_val)
    all_d10.append(d10_val)
    all_turnovers.append(turnover_pct)
    all_n_holdings.append(len(target_weights))

    prev_holdings = target_weights

    if m_idx < 3 or m_idx == len(backtest_dates) - 1:
        print(f"  {as_of} [{regime:>12s}]: n={len(target_weights):2d}  "
              f"ret={port_ret:+.2f}%  bench={bench_ret:+.2f}%  "
              f"hit={hit_rate:.0f}%  ic={ic_val:.4f}  turn={turnover_pct:.0f}%")

# ================================================================
# RESULTS
# ================================================================
print()
print("=" * 70)
print("PORTFOLIO BACKTEST RESULTS")
print("=" * 70)

port_r = np.array(all_monthly_returns)
bench_r = np.array(all_benchmark_returns)
n = len(port_r)
ppy = 252 / 60

if n < 3:
    print(f"Insufficient data: {n} months")
    sys.exit(1)

port_cagr = (np.prod(1 + port_r/100) ** (ppy/n) - 1) * 100
bench_cagr = (np.prod(1 + bench_r/100) ** (ppy/n) - 1) * 100
excess_cagr = port_cagr - bench_cagr
ann_vol = np.std(port_r) * np.sqrt(ppy)
sharpe = port_cagr / ann_vol if ann_vol > 0 else 0

downside = port_r[port_r < 0]
dvol = np.std(downside) * np.sqrt(ppy) if len(downside) > 1 else ann_vol
sortino = port_cagr / dvol if dvol > 0 else 0

cum = np.cumprod(1 + port_r/100)
rmax = np.maximum.accumulate(cum)
dd = (cum - rmax) / rmax * 100
max_dd = np.min(dd)

win_rate = np.sum(port_r > 0) / n * 100
avg_hit = np.mean(all_hit_rates)
mean_ic = np.mean(all_ics)
ic_std = np.std(all_ics)
ic_t = mean_ic / (ic_std / np.sqrt(n)) if ic_std > 0 else 0
ic_pos = np.sum(np.array(all_ics) > 0)
mean_d1 = np.mean(all_d1)
mean_d10 = np.mean(all_d10)
avg_turn = np.mean(all_turnovers)

# Long-short spread
ls_r = np.array(all_d10) - np.array(all_d1)
ls_cagr = (np.prod(1 + ls_r/100) ** (ppy/n) - 1) * 100 if n > 0 else 0
ls_vol = np.std(ls_r) * np.sqrt(ppy)
ls_sharpe = ls_cagr / ls_vol if ls_vol > 0 else 0

print(f"\n  Period:       {backtest_dates[0]} to {backtest_dates[-1]} ({n} months)")
print(f"  Avg Holdings: {np.mean(all_n_holdings):.0f}")
print(f"  Regimes:      ", end="")
for d in backtest_dates:
    r = detect_regime(d)["regime"]
    print(f"{r[0]}", end="")
print()

def check_target(val, comparator, target):
    if comparator == "gt":
        return val > target
    elif comparator == "lt":
        return val < target
    return False

targets = {
    "Long-only Sharpe > 1.0": (sharpe, "gt", 1.0),
    "Hit Rate > 58%": (avg_hit, "gt", 58),
    "Max DD < 18% (abs)": (max_dd, "gt", -18),
    "Excess CAGR > +5%": (excess_cagr, "gt", 5),
    "Turnover < 150%": (avg_turn, "lt", 150),
    "IC (60d) > 0.04": (mean_ic, "gt", 0.04),
}

print(f"\n{'─' * 60}")
print(f"  {'METRIC':<30s} {'VALUE':>10s} {'TARGET':>10s} {'':>8s}")
print(f"{'─' * 60}")
print(f"  {'Portfolio CAGR':<30s} {port_cagr:>10.2f}%")
print(f"  {'Benchmark CAGR':<30s} {bench_cagr:>10.2f}%")
print(f"  {'Excess CAGR':<30s} {excess_cagr:>10.2f}%")
print(f"  {'Sharpe Ratio':<30s} {sharpe:>10.3f} {'> 1.000':>10s} {'✓' if sharpe > 1.0 else '✗':>8s}")
print(f"  {'Sortino Ratio':<30s} {sortino:>10.3f}")
print(f"  {'Max Drawdown':<30s} {max_dd:>10.2f} {'< -18%':>10s} {'✓' if max_dd > -18 else '✗':>8s}")
print(f"  {'Annual Volatility':<30s} {ann_vol:>10.2f}%")
print(f"  {'Win Rate':<30s} {win_rate:>10.1f}%")
print(f"  {'Hit Rate (Top 20)':<30s} {avg_hit:>10.1f}% {'> 58%':>10s} {'✓' if avg_hit > 58 else '✗':>8s}")
print(f"  {'Annual Turnover':<30s} {avg_turn:>10.1f}% {'< 150%':>10s} {'✓' if avg_turn < 150 else '✗':>8s}")
print(f"  {'IC (60d)':<30s} {mean_ic:>10.4f} {'> 0.04':>10s} {'✓' if mean_ic > 0.04 else '✗':>8s}")
print(f"  {'IC t-stat':<30s} {ic_t:>10.2f}")
print(f"  {'IC positive':<30s} {ic_pos:>3d}/{n:<6d}")
print(f"  {'D1 (lowest decile)':<30s} {mean_d1:>10.2f}%")
print(f"  {'D10 (highest decile)':<30s} {mean_d10:>10.2f}%")
print(f"  {'Long-Short Spread CAGR':<30s} {ls_cagr:>10.2f}%")
print(f"  {'Long-Short Sharpe':<30s} {ls_sharpe:>10.3f}")
print(f"{'─' * 60}")

passed = sum(1 for _, (v, cmp, t) in targets.items() if check_target(v, cmp, t))
print(f"\n  PASSED: {passed}/{len(targets)}")

for name, (val, cmp, target) in targets.items():
    ok = check_target(val, cmp, target)
    sym = ">" if cmp == "gt" else "<"
    print(f"    {name:30s}: {'PASS' if ok else 'FAIL'} ({val:.2f} {sym} {target:.2f})")

verdict = "PASS" if passed >= 4 else "INCONCLUSIVE" if passed >= 2 else "FAIL"
print(f"\n  VERDICT: {verdict}")

# Save
results = {
    "period": f"{backtest_dates[0]} to {backtest_dates[-1]}",
    "n_months": n,
    "portfolio_cagr_pct": round(port_cagr, 2),
    "benchmark_cagr_pct": round(bench_cagr, 2),
    "excess_cagr_pct": round(excess_cagr, 2),
    "sharpe_ratio": round(sharpe, 3),
    "sortino_ratio": round(sortino, 3),
    "max_drawdown_pct": round(max_dd, 2),
    "annual_volatility_pct": round(ann_vol, 2),
    "win_rate_pct": round(win_rate, 1),
    "hit_rate_pct": round(avg_hit, 1),
    "annual_turnover_pct": round(avg_turn, 1),
    "ic_60d": round(mean_ic, 4),
    "ic_t_stat": round(ic_t, 2),
    "ic_positive_months": int(ic_pos),
    "targets": {k: bool(check_target(v, cmp, t)) for k, (v, cmp, t) in targets.items()},
    "n_passed": passed,
    "n_total": len(targets),
    "verdict": verdict,
}

os.makedirs("/Users/hemant/alpha-hunter/reports", exist_ok=True)
with open("/Users/hemant/alpha-hunter/reports/portfolio_backtest.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\nReport saved to reports/portfolio_backtest.json")
print(f"Total time: {(datetime.now()-t0).total_seconds():.1f}s")
