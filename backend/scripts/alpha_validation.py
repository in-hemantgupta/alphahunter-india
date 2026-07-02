"""Alpha validation — Tasks 3-6
Walk-forward backtest, decile test, IC, hit rate.
Uses historical score_snapshots."""
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
print(f"Alpha validation starting at {t0}")

# Load all snapshot dates
session = SessionLocal()
snap_dates = [r[0] for r in session.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()]
print(f"Snapshot dates: {len(snap_dates)} — {snap_dates[0]} to {snap_dates[-1]}")

# Load ALL price data into memory
all_prices = session.query(
    PriceHistory.symbol, PriceHistory.date, PriceHistory.close
).order_by(PriceHistory.symbol, PriceHistory.date).all()
print(f"Price records loaded: {len(all_prices)}")

# Index prices: {symbol: [(date, close), ...]}
price_map = defaultdict(list)
for sym, dt, close in all_prices:
    price_map[sym].append((dt, close))
session.close()
print(f"Symbols with prices: {len(price_map)}")


def get_future_return(symbol, as_of, trading_days=30):
    """Get forward return for `trading_days` trading days after as_of."""
    prices = price_map.get(symbol, [])
    # Find the price on or after as_of
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


HORIZONS = [30, 60, 90, 120]

# ============================================================
# Process each horizon
# ============================================================
all_horizon_reports = {}

for trading_days in HORIZONS:
    print(f"\n{'='*60}")
    print(f"HORIZON: {trading_days} trading days")
    print(f"{'='*60}")

    results = []
    decile_returns = defaultdict(list)
    monthly_ics = []
    monthly_portfolio_returns = []
    monthly_benchmark_returns = []
    monthly_hit_rates = []
    monthly_ls_returns = []
    all_month_data = []

    # Use snapshots where we can measure forward returns
    usable_dates = snap_dates[:-1]  # last one has no forward data
    print(f"Usable dates for backtest: {len(usable_dates)}")

    for m_idx, as_of in enumerate(usable_dates):
        # Load snapshot data
        snaps = session.query(ScoreSnapshot).filter(ScoreSnapshot.date == as_of).all()
        if not snaps:
            continue

        # Get scores and symbols
        stock_data = []
        for s in snaps:
            score = s.total_score or 0
            stock_data.append((s.symbol, score))

        if len(stock_data) < 50:
            continue

        # Sort by score descending
        stock_data.sort(key=lambda x: -x[1])
        n_stocks = len(stock_data)

        # Compute forward returns
        fwd_returns = []
        for sym, score in stock_data:
            fwd_ret = get_future_return(sym, as_of, trading_days=trading_days)
            fwd_returns.append(fwd_ret if fwd_ret is not None else 0)

        returns_arr = np.array(fwd_returns)
        scores_arr = np.array([sd[1] for sd in stock_data])

        # Filter out NaN returns
        valid_mask = ~np.isnan(returns_arr)
        if np.sum(valid_mask) < 50:
            continue

        scores_valid = scores_arr[valid_mask]
        returns_valid = returns_arr[valid_mask]

        # --- DECILE TEST ---
        sorted_idx = np.argsort(scores_valid)
        n_valid = len(scores_valid)
        decile_size = max(1, n_valid // 10)

        month_deciles = {}
        for d in range(10):
            start = d * decile_size
            end = min((d + 1) * decile_size, n_valid)
            if d == 9:
                end = n_valid
            decile_returns_d = returns_valid[sorted_idx[start:end]]
            mean_ret = float(np.mean(decile_returns_d)) * 100
            month_deciles[f"D{d+1}"] = round(mean_ret, 2)
            decile_returns[d].append(mean_ret)

        d_means = [month_deciles[f"D{d+1}"] for d in range(10)]
        monotonic = all(d_means[i] >= d_means[i+1] for i in range(9))

        # --- TOP 50 PORTFOLIO ---
        top50_idx = sorted_idx[-50:] if len(sorted_idx) >= 50 else sorted_idx
        top50_returns = returns_valid[top50_idx]
        portfolio_ret = float(np.mean(top50_returns)) * 100

        # --- BENCHMARK (all stocks avg) ---
        benchmark_ret = float(np.mean(returns_valid)) * 100

        # --- LONG-SHORT DECILE SPREAD ---
        d1_idx = sorted_idx[-decile_size:] if len(sorted_idx) >= decile_size else sorted_idx[-10:]
        d10_idx = sorted_idx[:decile_size] if len(sorted_idx) >= decile_size else sorted_idx[:10]
        d1_returns = returns_valid[d1_idx]
        d10_returns = returns_valid[d10_idx]
        ls_ret = (float(np.mean(d1_returns)) - float(np.mean(d10_returns))) * 100
        monthly_ls_returns.append(ls_ret)

        # --- HIT RATE ---
        top20_idx = sorted_idx[-20:] if len(sorted_idx) >= 20 else sorted_idx
        top20_returns = returns_valid[top20_idx]
        hit_rate = float(np.sum(top20_returns > 0) / len(top20_returns)) * 100

        # --- INFORMATION COEFFICIENT ---
        ic, ic_p = spearmanr(scores_valid, returns_valid)
        ic = float(ic) if not np.isnan(ic) else 0
        ic_p = float(ic_p) if not np.isnan(ic_p) else 1

        monthly_ics.append(ic)
        monthly_portfolio_returns.append(portfolio_ret)
        monthly_benchmark_returns.append(benchmark_ret)
        monthly_hit_rates.append(hit_rate)

        entry = {
            "date": str(as_of),
            "n_stocks": n_valid,
            "portfolio_return_pct": round(portfolio_ret, 2),
            "benchmark_return_pct": round(benchmark_ret, 2),
            "excess_return_pct": round(portfolio_ret - benchmark_ret, 2),
            "long_short_return_pct": round(ls_ret, 2),
            "ic": round(ic, 4),
            "ic_p_value": round(ic_p, 4),
            "hit_rate_pct": round(hit_rate, 1),
            "deciles": month_deciles,
            "monotonic": monotonic,
        }
        all_month_data.append(entry)

        if m_idx < 3 or m_idx == len(usable_dates) - 1:
            print(f"  {as_of}: IC={ic:.4f} Port={portfolio_ret:.1f}% LS={ls_ret:.1f}% Hit={hit_rate:.1f}%")

    # ============================================================
    # AGGREGATE RESULTS
    # ============================================================
    print(f"\n  AGGREGATE RESULTS ({trading_days}d)")
    print(f"  Months tested: {len(all_month_data)}")

    port_returns = np.array(monthly_portfolio_returns)
    bench_returns = np.array(monthly_benchmark_returns)
    ls_returns = np.array(monthly_ls_returns)

    n_months = len(port_returns)
    if n_months > 1:
        port_cagr = float(np.mean(port_returns) * (252 / trading_days) * 12)
        bench_cagr = float(np.mean(bench_returns) * (252 / trading_days) * 12)
        excess_cagr = port_cagr - bench_cagr
        port_vol = float(np.std(port_returns) * np.sqrt(252 / trading_days) * np.sqrt(12))
        bench_vol = float(np.std(bench_returns) * np.sqrt(252 / trading_days) * np.sqrt(12))
        sharpe = port_cagr / port_vol if port_vol > 0 else 0

        # Long-short metrics
        ls_cagr = float(np.mean(ls_returns) * (252 / trading_days) * 12)
        ls_vol = float(np.std(ls_returns) * np.sqrt(252 / trading_days) * np.sqrt(12))
        ls_sharpe = ls_cagr / ls_vol if ls_vol > 0 else 0

        downside = port_returns[port_returns < 0]
        downside_vol = float(np.std(downside) * np.sqrt(252 / trading_days) * np.sqrt(12)) if len(downside) > 1 else port_vol
        sortino = port_cagr / downside_vol if downside_vol > 0 else 0

        cumulative = np.cumprod(1 + port_returns / 100)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max * 100
        max_dd = float(np.min(drawdown))

        calmar = port_cagr / abs(max_dd) if max_dd < 0 else 0
        win_rate = float(np.sum(port_returns > 0) / n_months) * 100
        avg_hit_rate = float(np.mean(monthly_hit_rates))
        mean_ic = float(np.mean(monthly_ics))
        ic_positive_pct = float(np.sum(np.array(monthly_ics) > 0) / n_months) * 100
        ic_vol = float(np.std(monthly_ics))

        print(f"    Portfolio CAGR:           {port_cagr:>8.2f}%")
        print(f"    Benchmark CAGR:           {bench_cagr:>8.2f}%")
        print(f"    Excess CAGR:              {excess_cagr:>8.2f}%")
        print(f"    Sharpe:                    {sharpe:>8.3f}")
        print(f"    Sortino:                   {sortino:>8.3f}")
        print(f"    Max DD:                    {max_dd:>8.2f}%")
        print(f"    Long-Short CAGR:           {ls_cagr:>8.2f}%")
        print(f"    Long-Short Sharpe:         {ls_sharpe:>8.3f}")
        print(f"    Win Rate:                  {win_rate:>8.1f}%")
        print(f"    Hit Rate:                  {avg_hit_rate:>8.1f}%")
        print(f"    Mean IC:                   {mean_ic:>8.4f}")
        print(f"    IC > 0 months:             {ic_positive_pct:>8.1f}%")

        # Decile test
        decile_avg = {}
        for d in range(10):
            vals = decile_returns[d]
            avg_ret = float(np.mean(vals)) if vals else 0
            decile_avg[f"D{d+1}"] = round(avg_ret, 2)

        for d in range(10):
            bar = '█' * max(1, int(abs(decile_avg[f"D{d+1}"]) * 3))
            if decile_avg[f"D{d+1}"] > 0:
                print(f"    D{d+1:2d}: {decile_avg[f'D{d+1}']:>6.2f}% +{bar}")
            else:
                print(f"    D{d+1:2d}: {decile_avg[f'D{d+1}']:>6.2f}% {bar}")

        all_monotonic = sum(1 for m in all_month_data if m["monotonic"])
        d1 = decile_avg.get("D1", 0)
        d10 = decile_avg.get("D10", 0)

        passes = []
        passes.append(("Sharpe > 1", sharpe > 1))
        passes.append(("LS Sharpe > 1", ls_sharpe > 1))
        passes.append(("IC > 0.03", mean_ic > 0.03))
        passes.append(("Hit Rate > 60%", avg_hit_rate > 60))
        passes.append(("D1 > D10", d1 > d10))
        passes.append(("Win Rate > 50%", win_rate > 50))

        for name, passed in passes:
            print(f"    {name:20s}: {'PASS' if passed else 'FAIL'}")

        n_pass = sum(1 for _, p in passes)
        print(f"    Passed {n_pass}/{len(passes)} criteria")

        all_horizon_reports[trading_days] = {
            "n_months": n_months,
            "date_range": f"{usable_dates[0]} to {usable_dates[-1]}",
            "portfolio": {
                "cagr_pct": round(port_cagr, 2),
                "benchmark_cagr_pct": round(bench_cagr, 2),
                "excess_cagr_pct": round(excess_cagr, 2),
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "max_drawdown_pct": round(max_dd, 2),
                "win_rate_pct": round(win_rate, 1),
                "avg_hit_rate_pct": round(avg_hit_rate, 1),
            },
            "long_short": {
                "cagr_pct": round(ls_cagr, 2),
                "volatility_pct": round(ls_vol, 2),
                "sharpe_ratio": round(ls_sharpe, 3),
            },
            "information_coefficient": {
                "mean_ic": round(mean_ic, 4),
                "ic_positive_months_pct": round(ic_positive_pct, 1),
                "ic_volatility": round(ic_vol, 4),
            },
            "decile_test": {
                "decile_avg_returns": decile_avg,
                "d1_gt_d10": d1 > d10,
                "monotonic_months": f"{all_monotonic}/{n_months}",
            },
            "verdict": {
                "sharpe_gt_1": sharpe > 1,
                "ls_sharpe_gt_1": ls_sharpe > 1,
                "ic_gt_003": mean_ic > 0.03,
                "hit_rate_gt_60": avg_hit_rate > 60,
                "d1_gt_d10": d1 > d10,
                "win_rate_gt_50": win_rate > 50,
                "n_passed": n_pass,
                "n_total": len(passes),
            },
            "monthly_data": all_month_data,
        }

# Save consolidated report
report = {
    "methodology": f"Monthly rebalance, top 50 equal-weight, horizons: {HORIZONS}d, score_snapshots backfill",
    "horizon_results": all_horizon_reports,
}

os.makedirs("/Users/hemant/alpha-hunter/reports", exist_ok=True)
with open("/Users/hemant/alpha-hunter/reports/alpha_validation.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

# Print cross-horizon summary
print(f"\n{'='*60}")
print(f"CROSS-HORIZON SUMMARY")
print(f"{'='*60}")
print(f"{'Horizon':>8s}  {'IC':>6s}  {'IC>0%':>6s}  {'Sharpe':>7s}  {'LS Sharpe':>9s}  {'HitRate':>7s}  {'WinRate':>7s}")
for h in HORIZONS:
    hr = all_horizon_reports.get(h, {})
    ic = hr.get("information_coefficient", {}).get("mean_ic", 0)
    ic_pos = hr.get("information_coefficient", {}).get("ic_positive_months_pct", 0)
    sharpe = hr.get("portfolio", {}).get("sharpe_ratio", 0)
    ls_sharpe = hr.get("long_short", {}).get("sharpe_ratio", 0)
    hit = hr.get("portfolio", {}).get("avg_hit_rate_pct", 0)
    win = hr.get("portfolio", {}).get("win_rate_pct", 0)
    print(f"{h:>8d}d  {ic:>6.4f}  {ic_pos:>5.1f}%  {sharpe:>7.3f}  {ls_sharpe:>9.3f}  {hit:>6.1f}%  {win:>6.1f}%")

print(f"\nReport saved to reports/alpha_validation.json")
print(f"Total time: {(datetime.now()-t0).total_seconds():.1f}s")
