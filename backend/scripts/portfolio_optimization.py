#!/usr/bin/env python3
"""ALPHAHUNTER — FINAL OPTIMIZATION PHASE
TASK 1: Concentration test (top 5/10/20/30/50)
TASK 3: Profit distribution (avg winner/loser, profit factor)
TASK 4: Conviction weighting (score² × confidence / vol)
TASK 5: Exit rule optimization (stops, rank drops)
TASK 2: Turnover reduction (min hold, thresholds)
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
from app.portfolio.liquidity_tiers import get_market_cap_tier, is_liquid
from app.portfolio.entry_filters import check_entry, compute_relative_strength
from app.portfolio.execution import simulate_rebalance_cost

t0 = datetime.now()
print(f"Optimization starting at {t0}")
print("=" * 60)

session = SessionLocal()
snap_dates = [r[0] for r in session.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()]
all_prices = session.query(PriceHistory.symbol, PriceHistory.date, PriceHistory.close, PriceHistory.volume).order_by(
    PriceHistory.symbol, PriceHistory.date).all()
price_map = defaultdict(list)
for sym, dt, close, volume in all_prices:
    price_map[sym].append((dt, close, volume))
stocks = {s.symbol: s for s in session.query(Stock).all()}
sectors = {s.symbol: s.sector for s in session.query(Stock).all() if s.sector}
session.close()

backtest_dates = [d for d in snap_dates if d >= date(2025, 5, 1) and d < date(2026, 3, 1)]
print(f"Loaded: {len(price_map)} stocks, {len(backtest_dates)} dates")


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


def get_volatility(symbol, as_of, lookback=60):
    prices = price_map.get(symbol, [])
    closes = [c for dt, c, _ in prices if dt <= as_of and c is not None and c > 0]
    if len(closes) < 10:
        return 0.4
    rets = np.diff(closes[-lookback:]) / np.array(closes[-lookback:-1])
    return float(np.std(rets) * np.sqrt(252)) if len(rets) > 1 else 0.4


def run_backtest(top_n=50, conviction_method="score_confidence",
                 min_hold_days=0, trailing_stop_pct=0, exit_rank_drop=0):
    monthly_rets, bench_rets, hit_rates, ics, turnovers, n_holdings = [], [], [], [], [], []
    stock_trades = []
    prev_holdings = {}
    hold_dates = {}

    for m_idx, as_of in enumerate(backtest_dates):
        rinfo = detect_regime(as_of)
        regime = rinfo["regime"]
        snaps = session.query(ScoreSnapshot).filter(ScoreSnapshot.date == as_of).all()
        if not snaps:
            continue

        candidates = []
        for s in snaps:
            sector = sectors.get(s.symbol, "Unknown")
            pv = get_prices_up_to(s.symbol, as_of)
            if len(pv) < 50:
                continue
            prices = [p for p, _ in pv]
            volumes = [v for _, v in pv if v is not None]
            score = s.total_score or 0
            confidence = s.confidence_score or 0.5
            vr = volumes[-1] / max(float(np.mean(volumes[-21:-1])), 1) if len(volumes) >= 21 else None
            vol = get_volatility(s.symbol, as_of)
            candidates.append(dict(symbol=s.symbol, score=score, confidence=confidence,
                                   sector=sector, price=prices[-1], prices=prices,
                                   volume_ratio=vr, volatility=vol))

        if len(candidates) < 100:
            continue
        candidates.sort(key=lambda x: -x["score"])
        total = len(candidates)
        for i, c in enumerate(candidates):
            c["score_rank"] = (i / total) * 100

        # RS
        sec_rets = defaultdict(dict)
        for c in candidates:
            r90 = get_future_return(c["symbol"], as_of - timedelta(days=90), 90)
            if r90 is not None and c["sector"] != "Unknown":
                sec_rets[c["sector"]][c["symbol"]] = r90
        for c in candidates:
            if c["sector"] != "Unknown" and c["symbol"] in sec_rets.get(c["sector"], {}):
                rs, np_ = compute_relative_strength(sec_rets[c["sector"]][c["symbol"]], sec_rets[c["sector"]])
                c["relative_strength"] = rs
                c["rpeer_count"] = np_
            else:
                c["relative_strength"] = None
                c["rpeer_count"] = 0

        # Liquidity filter
        tc = defaultdict(int)
        tm = {"A": 200, "B": 200, "C": int(200 * 0.15)}
        filtered = []
        for c in candidates:
            t = get_market_cap_tier(c["symbol"])
            c["tier"] = t
            if tc[t] < tm.get(t, 200) and is_liquid(c["symbol"]):
                filtered.append(c)
                tc[t] += 1
        candidates = filtered

        # Entry filter
        buy_list = []
        for c in candidates:
            ok, _ = check_entry(symbol=c["symbol"], score_rank=c["score_rank"], price_data=c["prices"],
                                sector=c["sector"], volume_ratio=c.get("volume_ratio"),
                                relative_strength=c.get("relative_strength"),
                                sector_peer_count=c.get("rpeer_count", 0))
            if ok:
                buy_list.append(c)
            if len(buy_list) >= top_n:
                break

        # Min hold period
        if min_hold_days > 0 and m_idx > 0:
            buy_list = [c for c in buy_list if c["symbol"] not in hold_dates
                        or (as_of - hold_dates[c["symbol"]]).days >= min_hold_days
                        or c["symbol"] not in prev_holdings]

        # Conviction
        raw_weights = {}
        for c in buy_list:
            if conviction_method == "score2":
                w = (c["score"] ** 2 * c["confidence"]) / max(c["volatility"], 0.05)
            else:
                w = c["score"] * c["confidence"]
            ra = 0.5 if regime == "Bear" else (0.75 if regime == "HighVolatility" else 1.0)
            raw_weights[c["symbol"]] = w * ra
        tw = sum(raw_weights.values())
        if tw <= 0:
            continue
        target_weights = {k: v / tw for k, v in raw_weights.items()}

        # 5% cap
        for sym, w in list(target_weights.items()):
            if w > 0.05:
                exc = w - 0.05
                target_weights[sym] = 0.05
                others = {k: v for k, v in target_weights.items() if k != sym and target_weights[k] < 0.05}
                ot = sum(others.values())
                for osym in others:
                    target_weights[osym] += exc * (others[osym] / ot) if ot > 0 else 0

        # Trailing stop exit
        if trailing_stop_pct > 0 and m_idx > 0:
            to_remove = []
            for sym in target_weights:
                if sym in hold_dates:
                    er = get_future_return(sym, hold_dates[sym], 60)
                    if er is not None and er < -trailing_stop_pct:
                        to_remove.append(sym)
            for sym in to_remove:
                del target_weights[sym]
            if target_weights:
                tot = sum(target_weights.values())
                target_weights = {k: v / tot for k, v in target_weights.items()}

        # Turnover
        turnover_pct, _ = simulate_rebalance_cost(
            prev_holdings, target_weights,
            {c["symbol"]: c["price"] for c in candidates},
            {})

        # Forward returns
        port_ret = 0
        bench = []
        for c in candidates:
            r = get_future_return(c["symbol"], as_of, 60)
            if r is not None:
                bench.append(r)
                if c["symbol"] in target_weights:
                    port_ret += target_weights[c["symbol"]] * r

        bench_ret = np.mean(bench) if bench else 0

        # Track trades
        for sym, w in target_weights.items():
            r = get_future_return(sym, as_of, 60)
            if r is not None:
                stock_trades.append({"return_pct": r, "weight": w})

        # Hit rate
        top20 = list(target_weights.keys())[:20]
        wins = sum(1 for sym in top20 if (get_future_return(sym, as_of, 60) or 0) > 0)
        hit_rate = wins / len(top20) * 100 if top20 else 0

        # IC
        scores = []
        rets = []
        for c in candidates:
            r = get_future_return(c["symbol"], as_of, 60)
            if r is not None and c["score"] is not None:
                scores.append(c["score"])
                rets.append(r)
        ic_val = 0
        if len(scores) > 20:
            ic_val, _ = spearmanr(scores, rets)
            ic_val = ic_val if not np.isnan(ic_val) else 0

        monthly_rets.append(port_ret)
        bench_rets.append(bench_ret)
        hit_rates.append(hit_rate)
        ics.append(ic_val)
        turnovers.append(turnover_pct)
        n_holdings.append(len(target_weights))
        prev_holdings = target_weights
        for c in buy_list:
            if c["symbol"] not in hold_dates:
                hold_dates[c["symbol"]] = as_of

    port_r = np.array(monthly_rets)
    bench_r = np.array(bench_rets)
    n = len(port_r)
    ppy = 252 / 60
    if n < 3:
        return None

    port_cagr = (np.prod(1 + port_r/100) ** (ppy/n) - 1) * 100
    bench_cagr = (np.prod(1 + bench_r/100) ** (ppy/n) - 1) * 100
    avol = np.std(port_r) * np.sqrt(ppy)
    sharpe = port_cagr / avol if avol > 0 else 0
    dd_arr = np.minimum.accumulate(1 + port_r/100) / np.maximum.accumulate(1 + port_r/100) - 1
    max_dd = np.min(dd_arr) * 100
    win_rate = np.sum(port_r > 0) / n * 100
    avg_hit = np.mean(hit_rates)
    mean_ic = np.mean(ics)
    avg_turn = np.mean(turnovers)

    # Profit distribution
    tr = [t["return_pct"] for t in stock_trades] or [0]
    winners = [r for r in tr if r > 0]
    losers = [r for r in tr if r < 0]
    avg_w = np.mean(winners) if winners else 0
    avg_l = abs(np.mean(losers)) if losers else 0
    gp = sum(winners)
    gl = abs(sum(losers))
    pf = gp / gl if gl > 0 else 0

    return dict(top_n=top_n, conviction=conviction_method, min_hold_days=min_hold_days,
                trailing_stop=trailing_stop_pct, n_months=n,
                portfolio_cagr=round(port_cagr, 2), benchmark_cagr=round(bench_cagr, 2),
                excess_cagr=round(port_cagr - bench_cagr, 2),
                sharpe=round(sharpe, 3), max_dd=round(max_dd, 2),
                win_rate=round(win_rate, 1), hit_rate=round(avg_hit, 1),
                turnover=round(avg_turn, 1), mean_ic=round(mean_ic, 4),
                avg_winner=round(avg_w, 2), avg_loser=round(avg_l, 2),
                profit_factor=round(pf, 2), avg_n_holdings=round(np.mean(n_holdings), 0))


session = SessionLocal()

# ─── TASK 1: CONCENTRATION TEST ─────────────────────────────
print("\n" + "=" * 60)
print("TASK 1 — CONCENTRATION TEST")
print("=" * 60)
print(f"{'Top N':>6s}  {'CAGR':>7s}  {'Bench':>7s}  {'Sharpe':>7s}  {'MaxDD':>7s}  {'Win%':>6s}  {'Hit%':>6s}  {'IC':>7s}  {'Turn':>6s}")
print("-" * 70)

conc_results = []
for n in [5, 10, 20, 30, 50]:
    r = run_backtest(top_n=n)
    if r:
        conc_results.append(r)
        print(f"{n:>6d}  {r['portfolio_cagr']:>6.2f}%  {r['benchmark_cagr']:>6.2f}%  "
              f"{r['sharpe']:>6.3f}  {r['max_dd']:>6.2f}%  {r['win_rate']:>5.1f}%  "
              f"{r['hit_rate']:>5.1f}%  {r['mean_ic']:>6.4f}  {r['turnover']:>5.0f}%")

best_conc = max(conc_results, key=lambda r: r["sharpe"]) if conc_results else None
best_n = best_conc["top_n"] if best_conc else 20
print(f"\nBest concentration: top_n={best_n}, Sharpe={best_conc['sharpe']}" if best_conc else "No results")

# ─── TASK 3: PROFIT DISTRIBUTION ────────────────────────────
if best_conc:
    print("\n" + "=" * 60)
    print(f"TASK 3 — PROFIT DISTRIBUTION (top {best_n})")
    print("=" * 60)
    print(f"  Avg winner:      {best_conc['avg_winner']:>7.2f}%")
    print(f"  Avg loser:       {best_conc['avg_loser']:>7.2f}%")
    print(f"  Profit factor:   {best_conc['profit_factor']:>7.2f}  (target > 1.8)")

# ─── TASK 4: CONVICTION COMPARISON ──────────────────────────
print("\n" + "=" * 60)
print(f"TASK 4 — CONVICTION COMPARISON (top {best_n})")
print("=" * 60)
print(f"{'Method':>15s}  {'CAGR':>7s}  {'Sharpe':>7s}  {'MaxDD':>7s}  {'Hit%':>6s}  {'PF':>6s}")
print("-" * 55)

for method in ["score_confidence", "score2"]:
    r = run_backtest(top_n=best_n, conviction_method=method)
    if r:
        print(f"{method:>15s}  {r['portfolio_cagr']:>6.2f}%  {r['sharpe']:>6.3f}  "
              f"{r['max_dd']:>6.2f}%  {r['hit_rate']:>5.1f}%  {r['profit_factor']:>5.2f}")

# ─── TASK 5: EXIT OPTIMIZATION ──────────────────────────────
print("\n" + "=" * 60)
print(f"TASK 5 — EXIT OPTIMIZATION (top {best_n})")
print("=" * 60)
print(f"{'Trail%':>6s}  {'CAGR':>7s}  {'Sharpe':>7s}  {'MaxDD':>7s}  {'Hit%':>6s}")
print("-" * 40)

for trail in [0, 7, 10, 12]:
    r = run_backtest(top_n=best_n, trailing_stop_pct=trail)
    if r:
        print(f"{trail:>4d}%   {r['portfolio_cagr']:>6.2f}%  {r['sharpe']:>6.3f}  "
              f"{r['max_dd']:>6.2f}%  {r['hit_rate']:>5.1f}%")

# ─── TASK 2: TURNOVER REDUCTION ─────────────────────────────
print("\n" + "=" * 60)
print(f"TASK 2 — TURNOVER REDUCTION (top {best_n})")
print("=" * 60)
print(f"{'MinHold':>7s}  {'CAGR':>7s}  {'Sharpe':>7s}  {'MaxDD':>7s}  {'Turn':>6s}  {'Hit%':>6s}")
print("-" * 50)

for hold in [0, 30, 45, 60]:
    r = run_backtest(top_n=best_n, min_hold_days=hold)
    if r:
        print(f"{hold:>5d}d   {r['portfolio_cagr']:>6.2f}%  {r['sharpe']:>6.3f}  "
              f"{r['max_dd']:>6.2f}%  {r['turnover']:>5.0f}%  {r['hit_rate']:>5.1f}%")

session.close()

# ─── FINAL BEST ─────────────────────────────────────────────
all_results = conc_results + []
pf_results = [r for r in conc_results if r and r.get("top_n") == best_n]
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
if best_conc:
    print(f"\n  Best Top N:         {best_conc['top_n']}")
    print(f"  Sharpe:             {best_conc['sharpe']:.3f}  (target > 1.2)")
    print(f"  Max DD:             {best_conc['max_dd']:.2f}%  (target < 15%)")
    print(f"  Turnover:           {best_conc['turnover']:.1f}%  (target < 120%)")
    print(f"  Profit Factor:      {best_conc['profit_factor']:.2f}  (target > 1.8)")
    print(f"  Hit Rate:           {best_conc['hit_rate']:.1f}%")
    print(f"  Win Rate:           {best_conc['win_rate']:.1f}%")
    print(f"  Portfolio CAGR:     {best_conc['portfolio_cagr']:.2f}%")
    print(f"  Benchmark CAGR:     {best_conc['benchmark_cagr']:.2f}%")
    print(f"  Excess CAGR:        {best_conc['excess_cagr']:.2f}%")

    hit_checks = []
    hit_checks.append(("Sharpe > 1.2", best_conc['sharpe'] > 1.2))
    hit_checks.append(("Turnover < 120%", best_conc['turnover'] < 120))
    hit_checks.append(("Profit Factor > 1.8", best_conc['profit_factor'] > 1.8))
    hit_checks.append(("Max DD < 15%", best_conc['max_dd'] > -15))
    passed = sum(1 for _, v in hit_checks if v)
    print(f"\n  Deployment checks: {passed}/4")
    for name, ok in hit_checks:
        print(f"    {name:25s}: {'PASS' if ok else 'FAIL'}")
    deploy = "YES" if passed >= 3 else "NO"
    print(f"\n  Deploy capital:      {deploy}")

report = {"task1_concentration": conc_results, "best_config": best_conc}
os.makedirs("/Users/hemant/alpha-hunter/reports", exist_ok=True)
with open("/Users/hemant/alpha-hunter/reports/optimization_results.json", "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"\nTotal time: {(datetime.now()-t0).total_seconds():.1f}s")
