"""Factor decay analysis — tests alpha at 7d, 15d, 30d, 60d, 90d, 180d.
Reuses snapshot/price infra from alpha_validation.py.
Reports where alpha peaks and where signal dies."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from datetime import datetime, date, timedelta
from collections import defaultdict
from scipy.stats import spearmanr
from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory

t0 = datetime.now()
print(f"Factor decay analysis starting at {t0}")

HORIZONS = [7, 15, 30, 60, 90, 180]

session = SessionLocal()

# Load snapshot dates
snap_dates = [r[0] for r in session.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()]
print(f"Snapshot dates: {len(snap_dates)} — {snap_dates[0]} to {snap_dates[-1]}")

# Load ALL price data
all_prices = session.query(
    PriceHistory.symbol, PriceHistory.date, PriceHistory.close
).order_by(PriceHistory.symbol, PriceHistory.date).all()
print(f"Price records loaded: {len(all_prices)}")

price_map = defaultdict(list)
for sym, dt, close in all_prices:
    price_map[sym].append((dt, close))
session.close()
print(f"Symbols with prices: {len(price_map)}")


def get_future_return(symbol, as_of, trading_days=30):
    prices = price_map.get(symbol, [])
    start_idx = None
    for i, (dt, close) in enumerate(prices):
        if dt >= as_of:
            start_idx = i
            break
    if start_idx is None or start_idx + trading_days >= len(prices):
        return None
    entry_price = prices[start_idx][1]
    exit_price = prices[start_idx + trading_days][1]
    if entry_price is None or entry_price == 0:
        return None
    return (exit_price - entry_price) / entry_price


# Use snapshots where forward data is available for longest horizon
# Exclude the last enough snapshots to measure the longest horizon
usable_dates = snap_dates[:-1]  # at minimum exclude the last
print(f"Usable dates (pre-filter): {len(usable_dates)}")

all_horizon_results = {}

for trading_days in HORIZONS:
    print(f"\n{'='*60}")
    print(f"HORIZON: {trading_days} trading days")
    print(f"{'='*60}")

    session = SessionLocal()
    monthly_ics = []
    monthly_ls_returns = []
    monthly_hit_rates = []
    monthly_top50_returns = []
    monthly_benchmark_returns = []
    all_month_data = []

    # For each snapshot, compute forward returns at this horizon
    for m_idx, as_of in enumerate(usable_dates):
        snaps = session.query(ScoreSnapshot).filter(ScoreSnapshot.date == as_of).all()
        if not snaps:
            continue

        stock_data = [(s.symbol, s.total_score or 0) for s in snaps]
        if len(stock_data) < 50:
            continue

        stock_data.sort(key=lambda x: -x[1])
        n_stocks = len(stock_data)

        fwd_returns = []
        for sym, score in stock_data:
            fwd_ret = get_future_return(sym, as_of, trading_days=trading_days)
            fwd_returns.append(fwd_ret)

        returns_arr = np.array(fwd_returns, dtype=float)
        scores_arr = np.array([sd[1] for sd in stock_data])

        valid_mask = ~np.isnan(returns_arr)
        n_valid_returns = np.sum(valid_mask)
        if n_valid_returns < 50:
            print(f"  SKIP {as_of}: only {n_valid_returns} valid forward returns")
            continue

        # Skip if too many zero returns from missing data
        non_zero_mask = ~np.isclose(returns_arr[valid_mask], 0)
        if np.sum(non_zero_mask) < 10:
            print(f"  SKIP {as_of}: only {np.sum(non_zero_mask)} non-zero returns")
            continue

        scores_valid = scores_arr[valid_mask]
        returns_valid = returns_arr[valid_mask]

        # IC
        ic, ic_p = spearmanr(scores_valid, returns_valid)
        ic = float(ic) if not np.isnan(ic) else 0

        # Decile test
        sorted_idx = np.argsort(scores_valid)
        n_valid = len(scores_valid)
        decile_size = max(1, n_valid // 10)

        # Top decile
        d1_idx = sorted_idx[-decile_size:] if len(sorted_idx) >= decile_size else sorted_idx[-10:]
        # Bottom decile
        d10_idx = sorted_idx[:decile_size] if len(sorted_idx) >= decile_size else sorted_idx[:10]
        d1_returns = returns_valid[d1_idx]
        d10_returns = returns_valid[d10_idx]
        ls_ret = (float(np.mean(d1_returns)) - float(np.mean(d10_returns))) * 100

        # Hit rate (top 20)
        top20_idx = sorted_idx[-20:] if len(sorted_idx) >= 20 else sorted_idx
        top20_returns = returns_valid[top20_idx]
        hit_rate = float(np.sum(top20_returns > 0) / len(top20_returns)) * 100

        # Top 50 portfolio
        top50_idx = sorted_idx[-50:] if len(sorted_idx) >= 50 else sorted_idx
        top50_ret = float(np.mean(returns_valid[top50_idx])) * 100

        # Benchmark
        bench_ret = float(np.mean(returns_valid)) * 100

        monthly_ics.append(ic)
        monthly_ls_returns.append(ls_ret)
        monthly_hit_rates.append(hit_rate)
        monthly_top50_returns.append(top50_ret)
        monthly_benchmark_returns.append(bench_ret)

        all_month_data.append({
            "date": str(as_of),
            "n_stocks": n_valid,
            "ic": round(ic, 4),
            "long_short_return_pct": round(ls_ret, 2),
            "hit_rate_pct": round(hit_rate, 1),
            "portfolio_return_pct": round(top50_ret, 2),
            "benchmark_return_pct": round(bench_ret, 2),
        })

        if m_idx < 3 or m_idx == len(usable_dates) - 1:
            print(f"  {as_of}: IC={ic:.4f} LS={ls_ret:.1f}% Hit={hit_rate:.1f}%")

    session.close()

    n_months = len(monthly_ics)
    if n_months < 2:
        print(f"  INSUFFICIENT DATA: only {n_months} months")
        all_horizon_results[trading_days] = {"n_months": n_months, "error": "insufficient data"}
        continue

    ics = np.array(monthly_ics)
    ls_rets = np.array(monthly_ls_returns)
    hit_rets = np.array(monthly_hit_rates)
    port_rets = np.array(monthly_top50_returns)
    bench_rets = np.array(monthly_benchmark_returns)

    # IC metrics
    mean_ic = float(np.mean(ics))
    ic_std = float(np.std(ics))
    ic_tstat = mean_ic / (ic_std / math.sqrt(n_months)) if ic_std > 0 else 0
    ic_positive_pct = float(np.sum(ics > 0) / n_months) * 100

    # Long-short Sharpe (CAGR-based, matching alpha_validation.py)
    ls_mean = float(np.mean(ls_rets))
    ls_std = float(np.std(ls_rets))
    annualization = math.sqrt(252 / trading_days)
    ls_cagr = ls_mean * (252 / trading_days) * 12
    ls_vol = ls_std * math.sqrt(252 / trading_days) * math.sqrt(12)
    ls_sharpe = ls_cagr / max(ls_vol, 1e-6)

    # Top 50 portfolio Sharpe (CAGR-based)
    port_mean = float(np.mean(port_rets))
    port_std = float(np.std(port_rets))
    port_cagr = port_mean * (252 / trading_days) * 12
    port_vol = port_std * math.sqrt(252 / trading_days) * math.sqrt(12)
    port_sharpe = port_cagr / max(port_vol, 1e-6)
    excess_mean = float(np.mean(port_rets - bench_rets))

    # Hit rate
    avg_hit_rate = float(np.mean(hit_rets))
    hit_positive_months = float(np.sum(hit_rets > 50) / n_months) * 100

    # Win rate (portfolio positive)
    win_rate = float(np.sum(port_rets > 0) / n_months) * 100

    result = {
        "n_months": n_months,
        "date_range": f"{usable_dates[0]} to {usable_dates[-1]}",
        "information_coefficient": {
            "mean_ic": round(mean_ic, 4),
            "ic_std": round(ic_std, 4),
            "ic_tstat": round(ic_tstat, 4),
            "ic_positive_months_pct": round(ic_positive_pct, 1),
        },
        "long_short": {
            "mean_monthly_return_pct": round(ls_mean, 2),
            "vol_monthly_pct": round(ls_std, 2),
            "sharpe_ratio": round(ls_sharpe, 4),
        },
        "portfolio": {
            "mean_monthly_return_pct": round(port_mean, 2),
            "mean_excess_return_pct": round(excess_mean, 2),
            "sharpe_ratio": round(port_sharpe, 4),
            "win_rate_pct": round(win_rate, 1),
        },
        "hit_rate": {
            "mean_hit_rate_pct": round(avg_hit_rate, 1),
            "months_above_50pct_pct": round(hit_positive_months, 1),
        },
        "signal_quality": {
            "significant": abs(ic_tstat) > 2.0,
            "ic_positive": mean_ic > 0.03,
            "ls_sharpe_gt_1": ls_sharpe > 1.0,
            "hit_rate_gt_50": avg_hit_rate > 50,
        },
    }

    all_horizon_results[trading_days] = result

    print(f"\n  RESULTS ({trading_days}d):")
    print(f"    Months tested:          {n_months}")
    print(f"    Mean IC:                {mean_ic:.4f}")
    print(f"    IC t-stat:              {ic_tstat:.3f}")
    print(f"    IC > 0 months:          {ic_positive_pct:.0f}%")
    print(f"    Long-Short Sharpe:      {ls_sharpe:.3f}")
    print(f"    Top 50 Sharpe:          {port_sharpe:.3f}")
    print(f"    Excess return (month):  {excess_mean:.2f}%")
    print(f"    Avg Hit Rate:           {avg_hit_rate:.1f}%")
    print(f"    Signal significant:     {'YES' if abs(ic_tstat) > 2.0 else 'NO'}")

# Find peak alpha horizon
print(f"\n{'='*60}")
print(f"FACTOR DECAY PROFILE")
print(f"{'='*60}")

peak_ls = -999
peak_horizon_ls = None
peak_ic = -999
peak_horizon_ic = None

print(f"{'Horizon':>8s}  {'IC':>8s}  {'IC t':>8s}  {'Sig':>5s}  {'LS Sharpe':>10s}  {'HitRate':>8s}  {'WinRate':>8s}")
for h in HORIZONS:
    r = all_horizon_results.get(h, {})
    if r.get("error"):
        print(f"{h:>8d}d  ERROR: {r['error']}")
        continue
    ic_v = r["information_coefficient"]["mean_ic"]
    ic_t = r["information_coefficient"]["ic_tstat"]
    sig = "YES" if r["information_coefficient"]["ic_tstat"] > 2.0 else "NO"
    ls_s = r["long_short"]["sharpe_ratio"]
    hit = r["hit_rate"]["mean_hit_rate_pct"]
    win = r["portfolio"]["win_rate_pct"]
    print(f"{h:>8d}d  {ic_v:>8.4f}  {ic_t:>8.3f}  {sig:>5s}  {ls_s:>10.3f}  {hit:>7.1f}%  {win:>7.1f}%")

    if ls_s > peak_ls:
        peak_ls = ls_s
        peak_horizon_ls = h
    if ic_v > peak_ic:
        peak_ic = ic_v
        peak_horizon_ic = h

# Determine where signal dies
active_horizons = []
dead_horizons = []
for h in HORIZONS:
    r = all_horizon_results.get(h, {})
    if r.get("error"):
        continue
    ic_t = r["information_coefficient"]["ic_tstat"]
    ls_s = r["long_short"]["sharpe_ratio"]
    hit = r["hit_rate"]["mean_hit_rate_pct"]
    if abs(ic_t) > 2.0 and ls_s > 0.5:
        active_horizons.append(h)
    else:
        dead_horizons.append(h)

print(f"\n  Peak alpha (IC):          {peak_horizon_ic}d (IC={peak_ic:.4f})")
print(f"  Peak alpha (LS Sharpe):   {peak_horizon_ls}d (Sharpe={peak_ls:.3f})")
print(f"  Active horizons:          {active_horizons}")
print(f"  Dead horizons:            {dead_horizons}")
print(f"  Alpha death point:        {dead_horizons[0]}d" if dead_horizons else "  Alpha death point:        None detected")

# Summary
summary = {
    "methodology": "Monthly snapshot rebalance, Spearman IC, decile long-short, multiple horizons. Source: score_snapshots + price_history.",
    "horizons_tested": HORIZONS,
    "peak_alpha_horizon_ic": peak_horizon_ic,
    "peak_alpha_ic": round(peak_ic, 4),
    "peak_alpha_horizon_ls_sharpe": peak_horizon_ls,
    "peak_alpha_ls_sharpe": round(peak_ls, 4),
    "active_horizons": active_horizons,
    "dead_horizons": dead_horizons,
    "alpha_death_horizon": dead_horizons[0] if dead_horizons else None,
    "horizon_results": {str(k): v for k, v in all_horizon_results.items()},
    "monthly_data": {str(h): [m for m in all_horizon_results.get(h, {}).get("monthly_data", [])]
                     for h in HORIZONS},
}

with open("/tmp/factor_decay.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)

print(f"\nReport saved to /tmp/factor_decay.json")
print(f"Total time: {(datetime.now()-t0).total_seconds():.1f}s")
