"""Historical replay engine. Replays 60 trading days from historical snapshots."""
import sys, os, json, time
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
import yfinance as yf
from app.db.database import SessionLocal, engine
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.portfolio_position import PortfolioPosition
from app.models.fund_nav import FundNav
from app.models.stock import Stock
from app.portfolio.execution import execute_trade, total_cost_bps, get_cost_tier, simulate_rebalance_cost
from app.portfolio.entry_filters import check_entry, get_sma, compute_volume_ratio
from app.portfolio.exit_rules import check_exit, price_below_sma, trailing_stop_triggered
from app.portfolio.position_sizing import size_position
from sqlalchemy import text


class HistoricalReplayEngine:
    def __init__(self, initial_capital=1_00_00_000):
        self.initial_capital = initial_capital
        self.session = SessionLocal()
        self._ensure_tables()

    def _ensure_tables(self):
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS fund_nav (
                    date DATE PRIMARY KEY,
                    nav FLOAT,
                    cash FLOAT,
                    invested_capital FLOAT,
                    realized_pnl FLOAT,
                    unrealized_pnl FLOAT,
                    benchmark_nav FLOAT,
                    daily_return FLOAT,
                    benchmark_return FLOAT,
                    alpha FLOAT,
                    n_holdings INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS portfolio_positions (
                    symbol VARCHAR NOT NULL,
                    date DATE NOT NULL,
                    score FLOAT,
                    rank INTEGER,
                    entry_price FLOAT,
                    current_price FLOAT,
                    allocation FLOAT,
                    pnl_pct FLOAT,
                    sector VARCHAR,
                    confidence FLOAT,
                    entry_date DATE,
                    regime VARCHAR,
                    beta FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (symbol, date)
                )
            """))
            conn.commit()

    def get_available_dates(self):
        rows = self.session.execute(
            text("SELECT DISTINCT date FROM score_snapshots ORDER BY date")
        ).fetchall()
        return [r[0] for r in rows]

    def get_snapshot(self, replay_date):
        rows = self.session.execute(
            text("""SELECT symbol, total_score, confidence_score
                    FROM score_snapshots WHERE date = :d
                    ORDER BY total_score DESC"""),
            {"d": replay_date}
        ).fetchall()
        result = []
        for r in rows:
            stock = self.session.execute(
                text("SELECT sector FROM stocks_master WHERE symbol = :s"),
                {"s": r[0]}
            ).fetchone()
            sector = stock[0] if stock else "Unknown"
            result.append({
                "symbol": r[0],
                "total_score": r[1],
                "confidence_score": r[2],
                "sector": sector,
            })
        return result

    def get_price_data(self, symbol, replay_date, days=200):
        rows = self.session.execute(
            text("""SELECT close, volume, date FROM price_history
                    WHERE symbol = :s AND date <= :d
                    ORDER BY date DESC LIMIT :n"""),
            {"s": symbol, "d": replay_date, "n": days}
        ).fetchall()
        rows.reverse()
        closes = [float(r[0]) for r in rows if r[0] is not None and r[0] > 0]
        volumes = [int(r[1]) for r in rows if r[1] is not None and r[1] > 0] if len(rows) > 0 and rows[0][1] is not None else []
        return closes, volumes

    def get_price_at_date(self, symbol, replay_date):
        row = self.session.execute(
            text("""SELECT close FROM price_history
                    WHERE symbol = :s AND date <= :d
                    ORDER BY date DESC LIMIT 1"""),
            {"s": symbol, "d": replay_date}
        ).fetchone()
        return float(row[0]) if row else None

    def get_market_cap(self, symbol):
        row = self.session.execute(
            text("SELECT market_cap FROM stocks_master WHERE symbol = :s"),
            {"s": symbol}
        ).fetchone()
        return float(row[0]) if row and row[0] else None

    def get_benchmark_value(self, replay_date):
        try:
            nf = yf.Ticker("^NSEI")
            hist = nf.history(start=replay_date - timedelta(days=5),
                              end=replay_date + timedelta(days=1),
                              auto_adjust=True)
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        return None

    def build_portfolio(self, replay_date, top_n=50):
        snapshot = self.get_snapshot(replay_date)
        candidates = []
        for s in snapshot:
            closes, volumes = self.get_price_data(s["symbol"], replay_date)
            if len(closes) < 50:
                continue
            current_price = closes[-1]
            sma_50 = get_sma(closes, 50)
            if sma_50 is None or current_price <= sma_50:
                continue
            vol_ratio = compute_volume_ratio(closes, volumes, 20) if volumes else None
            if vol_ratio is not None and vol_ratio <= 1.0:
                continue
            score_rank = s["total_score"] if s["total_score"] is not None else 0
            mc = self.get_market_cap(s["symbol"])
            weight = size_position(score_rank, s.get("confidence_score", 0.5) or 0.5,
                                   symbol=s["symbol"], method="equal")
            candidates.append({
                "symbol": s["symbol"],
                "score": score_rank,
                "confidence": s.get("confidence_score", 0.5) or 0.5,
                "sector": s["sector"],
                "price": current_price,
                "weight": min(weight, 0.04),
                "market_cap": mc,
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        candidates = candidates[:top_n]
        total_weight = sum(c["weight"] for c in candidates)
        if total_weight > 0:
            for c in candidates:
                c["weight"] = c["weight"] / total_weight
        return candidates

    def get_current_holdings(self, replay_date):
        prev = self.session.execute(
            text("""SELECT DISTINCT date FROM portfolio_positions
                    WHERE date < :d ORDER BY date DESC LIMIT 1"""),
            {"d": replay_date}
        ).fetchone()
        if not prev:
            return {}, None
        prev_date = prev[0]
        rows = self.session.execute(
            text("""SELECT symbol, entry_price, allocation, sector, entry_date, score, confidence
                    FROM portfolio_positions WHERE date = :d"""),
            {"d": prev_date}
        ).fetchall()
        holdings = {}
        for r in rows:
            holdings[r[0]] = {
                "entry_price": float(r[1]) if r[1] else None,
                "allocation": float(r[2]) if r[2] else 0,
                "sector": r[3],
                "entry_date": r[4],
                "score": float(r[5]) if r[5] else None,
                "confidence": float(r[6]) if r[6] else 0.5,
            }
        return holdings, prev_date

    def compute_holdings_value(self, holdings, replay_date):
        total = 0.0
        for symbol, data in holdings.items():
            price = self.get_price_at_date(symbol, replay_date)
            if price is not None and data["allocation"] > 0:
                alloc = data["allocation"]
                if data["entry_price"] and data["entry_price"] > 0:
                    total += alloc * (price / data["entry_price"])
                else:
                    total += alloc
        return total

    def replay_day(self, replay_date, cash, prev_nav, prev_bnav):
        portfolio = self.build_portfolio(replay_date, top_n=50)
        current_holdings, prev_date = self.get_current_holdings(replay_date)
        holding_symbols = set(current_holdings.keys())
        target_symbols = {p["symbol"] for p in portfolio}
        buys = [p for p in portfolio if p["symbol"] not in holding_symbols]
        sells = [s for s in holding_symbols if s not in target_symbols]
        holds = target_symbols & holding_symbols
        total_trade_cost = 0.0
        realized_pnl = 0.0
        self.session.execute(
            text("DELETE FROM portfolio_positions WHERE date = :d"),
            {"d": replay_date}
        )
        new_holdings = {}
        if not portfolio:
            merged = {}
            for sym in holding_symbols:
                prev = current_holdings[sym]
                price = self.get_price_at_date(sym, replay_date)
                if price and prev["allocation"] > 0 and price < 100000:
                    merged[sym] = {"allocation": prev["allocation"], "price": price}
            return merged, cash, prev_nav, prev_bnav, {
                "date": str(replay_date), "nav": round(prev_nav, 4),
                "cash": round(cash, 4), "invested": sum(m["allocation"] for m in merged.values()),
                "benchmark_nav": round(prev_bnav, 4),
                "daily_return": 0.0, "benchmark_return": 0.0, "alpha": 0.0,
                "n_holdings": len(merged), "n_buys": 0, "n_sells": 0, "trade_cost": 0.0,
            }
        current_value_of_holdings = 0.0
        for sym in holding_symbols:
            prev = current_holdings[sym]
            price = self.get_price_at_date(sym, replay_date)
            if price and prev["entry_price"] and prev["entry_price"] > 0 and price < 100000:
                current_value = prev["allocation"] * (price / prev["entry_price"])
                current_value_of_holdings += current_value
        total_portfolio_value = cash + current_value_of_holdings
        if total_portfolio_value <= 0:
            total_portfolio_value = prev_nav or self.initial_capital
            cash = total_portfolio_value
        total_weight = sum(p["weight"] for p in portfolio)
        if total_weight <= 0:
            total_weight = 1.0
        investable = total_portfolio_value * 0.98
        invested = 0.0
        for p in portfolio:
            sym = p["symbol"]
            price = self.get_price_at_date(sym, replay_date)
            if price is None or price >= 100000:
                continue
            mc = p.get("market_cap")
            cost_bps = total_cost_bps(mc)
            cost_pct = cost_bps / 10000
            entry_price = price * (1 + cost_pct)
            target_value = investable * (p["weight"] / total_weight)
            if sym in holds:
                prev = current_holdings[sym]
                if prev["entry_price"] and prev["entry_price"] > 0:
                    current_value = prev["allocation"] * (price / prev["entry_price"])
                    pnl_pct = (price - prev["entry_price"]) / prev["entry_price"] * 100
                    delta = target_value - current_value
                    if delta > 0:
                        total_trade_cost += delta * cost_pct
                        allocation = target_value
                    else:
                        allocation = current_value
                    invested += allocation
                    self.session.execute(text("""
                        INSERT INTO portfolio_positions
                            (symbol, date, score, rank, entry_price, current_price,
                             allocation, pnl_pct, sector, confidence, entry_date)
                        VALUES (:s, :d, :sc, :rk, :ep, :cp, :al, :pnl, :sec, :cf, :ed)
                    """), {
                        "s": sym, "d": replay_date, "sc": p["score"],
                        "rk": len(new_holdings) + 1,
                        "ep": prev["entry_price"],
                        "cp": price, "al": allocation, "pnl": pnl_pct,
                        "sec": p["sector"], "cf": p["confidence"],
                        "ed": prev["entry_date"],
                    })
                    new_holdings[sym] = {
                        "entry_price": prev["entry_price"],
                        "allocation": allocation,
                        "current_price": price,
                        "quantity": allocation / price if price > 0 else 0,
                    }
                    continue
            allocation = target_value
            invested += allocation
            total_trade_cost += allocation * cost_pct
            self.session.execute(text("""
                INSERT INTO portfolio_positions
                    (symbol, date, score, rank, entry_price, current_price,
                     allocation, pnl_pct, sector, confidence, entry_date)
                VALUES (:s, :d, :sc, :rk, :ep, :cp, :al, :pnl, :sec, :cf, :ed)
            """), {
                "s": sym, "d": replay_date, "sc": p["score"],
                "rk": len(new_holdings) + 1, "ep": entry_price,
                "cp": price, "al": allocation,
                "pnl": 0, "sec": p["sector"], "cf": p["confidence"],
                "ed": replay_date,
            })
            new_holdings[sym] = {
                "entry_price": entry_price,
                "allocation": allocation,
                "current_price": price,
                "quantity": allocation / entry_price if entry_price > 0 else 0,
            }
        for sym in sells:
            prev = current_holdings[sym]
            price = self.get_price_at_date(sym, replay_date)
            if price and prev["entry_price"] and prev["entry_price"] > 0 and price < 100000:
                mc = self.get_market_cap(sym)
                cost_bps = total_cost_bps(mc)
                sell_price = price * (1 - cost_bps / 10000)
                prev_alloc_value = prev["allocation"]
                current_value = prev_alloc_value * (price / prev["entry_price"])
                realized = current_value - prev_alloc_value
                cash += current_value
                realized_pnl += realized
                total_trade_cost += current_value * cost_bps / 10000
        cash = cash - invested - total_trade_cost + realized_pnl
        if cash < 0:
            cash = 0.0
        benchmark_value = self.get_benchmark_value(replay_date)
        if benchmark_value is None:
            benchmark_value = prev_bnav or 1.0
        nav = cash + invested
        daily_return = (nav / prev_nav - 1) if prev_nav > 0 else 0.0
        benchmark_return = (benchmark_value / prev_bnav - 1) if prev_bnav and prev_bnav > 0 else 0.0
        alpha = daily_return - benchmark_return
        existing = self.session.execute(
            text("SELECT date FROM fund_nav WHERE date = :d"), {"d": replay_date}
        ).fetchone()
        if existing:
            self.session.execute(text("""
                UPDATE fund_nav SET nav = :nav, cash = :cash, invested_capital = :inv,
                    realized_pnl = :rp, unrealized_pnl = 0, benchmark_nav = :bnav,
                    daily_return = :dr, benchmark_return = :br, alpha = :alpha, n_holdings = :n
                WHERE date = :date
            """), {
                "nav": round(nav, 4), "cash": round(cash, 4), "inv": round(invested, 4),
                "rp": round(realized_pnl, 4),
                "bnav": round(benchmark_value, 4), "dr": round(daily_return, 6),
                "br": round(benchmark_return, 6), "alpha": round(alpha, 6),
                "n": len(new_holdings), "date": replay_date,
            })
        else:
            self.session.execute(text("""
                INSERT INTO fund_nav
                    (date, nav, cash, invested_capital, realized_pnl, unrealized_pnl,
                     benchmark_nav, daily_return, benchmark_return, alpha, n_holdings)
                VALUES (:date, :nav, :cash, :inv, :rp, 0, :bnav, :dr, :br, :alpha, :n)
            """), {
                "date": replay_date,
                "nav": round(nav, 4), "cash": round(cash, 4), "inv": round(invested, 4),
                "rp": round(realized_pnl, 4),
                "bnav": round(benchmark_value, 4), "dr": round(daily_return, 6),
                "br": round(benchmark_return, 6), "alpha": round(alpha, 6),
                "n": len(new_holdings),
            })
        self.session.commit()
        nav_data = {
            "date": str(replay_date),
            "nav": round(nav, 4),
            "cash": round(cash, 4),
            "invested": round(invested, 4),
            "benchmark_nav": round(benchmark_value, 4),
            "daily_return": round(daily_return, 6),
            "benchmark_return": round(benchmark_return, 6),
            "alpha": round(alpha, 6),
            "n_holdings": len(new_holdings),
            "n_buys": len(buys),
            "n_sells": len(sells),
            "trade_cost": round(total_trade_cost, 4),
        }
        return new_holdings, cash, nav, benchmark_value, nav_data

    def run(self, start_date=None, end_date=None, n_days=60):
        dates = self.get_available_dates()
        if not dates:
            print("No snapshot dates found.")
            return None
        if end_date:
            end_dt = end_date if isinstance(end_date, date) else date.fromisoformat(end_date)
            dates = [d for d in dates if d <= end_dt]
        if start_date:
            start_dt = start_date if isinstance(start_date, date) else date.fromisoformat(start_date)
            dates = [d for d in dates if d >= start_dt]
        if len(dates) > n_days:
            dates = dates[-n_days:]
        dates = [d for d in dates if d.day in (28, 29, 30, 31, 1, 2)]
        seen = set()
        unique = []
        for d in dates:
            mk = d.strftime("%Y-%m")
            if mk not in seen:
                seen.add(mk)
                unique.append(d)
        dates = sorted(unique)
        if len(dates) < 3:
            dates = self.get_available_dates()
            if len(dates) > n_days:
                dates = dates[-n_days:]
        print(f"Replaying {len(dates)} snapshot months: {dates[0]} to {dates[-1]}")
        benchmark_value = self.get_benchmark_value(dates[0])
        if benchmark_value is None:
            benchmark_value = 25000.0
        initial_nav = self.initial_capital
        prev_nav = initial_nav
        prev_bnav = benchmark_value
        cash = self.initial_capital
        holdings = {}
        nav_curve = []
        initial_entry = {
            "date": str(dates[0]),
            "nav": round(initial_nav, 4),
            "cash": round(initial_nav, 4),
            "invested": 0.0,
            "benchmark_nav": round(benchmark_value, 4),
            "daily_return": 0.0,
            "benchmark_return": 0.0,
            "alpha": 0.0,
            "n_holdings": 0,
            "n_buys": 0,
            "n_sells": 0,
            "trade_cost": 0.0,
        }
        self.session.execute(text("""
            INSERT INTO fund_nav
                (date, nav, cash, invested_capital, realized_pnl, unrealized_pnl,
                 benchmark_nav, daily_return, benchmark_return, alpha, n_holdings)
            VALUES (:date, :nav, :cash, :inv, 0, 0, :bnav, 0, 0, 0, 0)
            ON CONFLICT (date) DO NOTHING
        """), {
            "date": dates[0], "nav": round(initial_nav, 4),
            "cash": round(initial_nav, 4), "inv": 0,
            "bnav": round(benchmark_value, 4),
        })
        self.session.commit()
        nav_curve.append(initial_entry)
        for i, d in enumerate(dates[1:], 1):
            t0 = time.time()
            holdings, cash, prev_nav, prev_bnav, nd = self.replay_day(d, cash, prev_nav, prev_bnav)
            nav_curve.append(nd)
            elapsed = time.time() - t0
            if i % 5 == 0 or i == len(dates) - 1:
                print(f"  Day {i}/{len(dates)-1} | {d} | NAV={nd['nav']:.2f} | "
                      f"H={nd['n_holdings']} | Ret={nd['daily_return']*100:.2f}% | "
                      f"{elapsed:.1f}s")
        results = {
            "period": {
                "start": str(dates[0]),
                "end": str(dates[-1]),
                "n_days": len(dates),
            },
            "nav_curve": nav_curve,
        }
        results["summary"] = self.compute_summary(results)
        return results

    def compute_summary(self, results):
        navs = results["nav_curve"]
        if len(navs) < 2:
            return {"error": "insufficient data"}
        start_nav = navs[0]["nav"]
        end_nav = navs[-1]["nav"]
        start_bnav = navs[0]["benchmark_nav"]
        end_bnav = navs[-1]["benchmark_nav"]
        total_days = len(navs) - 1
        calendar_days = (date.fromisoformat(navs[-1]["date"]) - date.fromisoformat(navs[0]["date"])).days
        years = max(calendar_days / 365.25, 1 / 365.25)
        if end_nav <= 0 or start_nav <= 0:
            cagr = -100.0
        else:
            cagr = ((end_nav / start_nav) ** (1 / years) - 1) * 100 if years > 0 else 0
        bm_cagr = ((end_bnav / start_bnav) ** (1 / years) - 1) * 100 if years > 0 and end_bnav > 0 and start_bnav > 0 else 0
        alpha_pct = cagr - bm_cagr
        daily_rets = [n["daily_return"] for n in navs[1:] if n["daily_return"] is not None]
        if len(daily_rets) > 1 and np.std(daily_rets) > 0:
            sharpe = float(np.mean(daily_rets) / np.std(daily_rets) * np.sqrt(252))
        else:
            sharpe = 0.0
        nav_vals = [n["nav"] for n in navs]
        peak = nav_vals[0]
        max_dd = 0.0
        for v in nav_vals:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        positive_days = sum(1 for r in daily_rets if r > 0)
        hit_rate = positive_days / len(daily_rets) * 100 if daily_rets else 0
        total_turnover = 0.0
        trade_cost_days = [n.get("trade_cost", 0) for n in navs[1:]]
        avg_daily_cost = np.mean(trade_cost_days) if trade_cost_days else 0
        turnover_est = 0.0
        n_holdings_list = [n.get("n_holdings", 0) for n in navs[1:]]
        avg_holdings = np.mean(n_holdings_list) if n_holdings_list else 0
        monthly_rets = defaultdict(list)
        for n in navs[1:]:
            if n["daily_return"] is not None:
                month_key = n["date"][:7]
                monthly_rets[month_key].append(n["daily_return"])
        monthly_returns = {}
        for mk, rets in sorted(monthly_rets.items()):
            monthly_returns[mk] = round((np.prod([1 + r for r in rets]) - 1) * 100, 2)
        n_trades = sum(n.get("n_buys", 0) + n.get("n_sells", 0) for n in navs[1:])
        avg_turnover = min(n_trades / avg_holdings * 100 if avg_holdings > 0 else 0, 200)
        summary = {
            "cagr_pct": round(cagr, 2),
            "benchmark_cagr_pct": round(bm_cagr, 2),
            "alpha_pct": round(alpha_pct, 2),
            "sharpe": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "hit_rate_pct": round(hit_rate, 1),
            "avg_turnover_pct": round(avg_turnover, 1),
            "n_trades": n_trades,
            "avg_holdings": round(avg_holdings, 1),
        }
        results["summary"] = summary
        results["monthly_returns"] = monthly_returns
        rs_text = []
        if sharpe >= 1.0:
            rs_text.append("Sharpe>=1.0 PASS")
        else:
            rs_text.append(f"Sharpe={sharpe:.3f}<1.0")
        if max_dd < 18:
            rs_text.append("MaxDD<18% PASS")
        else:
            rs_text.append(f"MaxDD={max_dd:.1f}%>18%")
        if hit_rate >= 50:
            rs_text.append("HitRate>=50% PASS")
        else:
            rs_text.append(f"HitRate={hit_rate:.1f}%<50%")
        if alpha_pct > 0:
            rs_text.append("PositiveAlpha PASS")
        else:
            rs_text.append(f"Alpha={alpha_pct:.1f}% negative")
        results["final_verdict"] = " | ".join(rs_text)
        return summary

    def print_report(self, results):
        if not results:
            print("No results to report.")
            return
        s = results.get("summary", {})
        print("\n" + "=" * 60)
        print("HISTORICAL REPLAY REPORT")
        print("=" * 60)
        print(f"Period:       {results['period']['start']} → {results['period']['end']} ({results['period']['n_days']} days)")
        print(f"Start NAV:    {results['nav_curve'][0]['nav']:,.2f}")
        print(f"End NAV:      {results['nav_curve'][-1]['nav']:,.2f}")
        print(f"CAGR:         {s.get('cagr_pct', 'N/A'):>8}%")
        print(f"Benchmark:    {s.get('benchmark_cagr_pct', 'N/A'):>8}%")
        print(f"Alpha:        {s.get('alpha_pct', 'N/A'):>8}%")
        print(f"Sharpe:       {s.get('sharpe', 'N/A'):>8}")
        print(f"Max DD:       {s.get('max_drawdown_pct', 'N/A'):>8}%")
        print(f"Hit Rate:     {s.get('hit_rate_pct', 'N/A'):>8}%")
        print(f"Avg Turnover: {s.get('avg_turnover_pct', 'N/A'):>8}%")
        print(f"Avg Holdings: {s.get('avg_holdings', 'N/A'):>8}")
        print(f"Total Trades: {s.get('n_trades', 'N/A'):>8}")
        print(f"\nMonthly Returns:")
        for mk, ret in results.get("monthly_returns", {}).items():
            print(f"  {mk}: {ret:+.2f}%")
        print(f"\nVerdict: {results.get('final_verdict', 'N/A')}")
        print("=" * 60)
        json_path = os.path.join(os.path.dirname(__file__), '..', '..', 'reports', 'historical_replay_results.json')
        json_path = os.path.abspath(json_path)
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        clean = {
            "period": results["period"],
            "summary": results["summary"],
            "nav_curve": results["nav_curve"],
            "monthly_returns": results["monthly_returns"],
            "final_verdict": results["final_verdict"],
        }
        with open(json_path, "w") as f:
            json.dump(clean, f, indent=2, default=str)
        print(f"\nResults saved to {json_path}")

    def close(self):
        self.session.close()


if __name__ == "__main__":
    engine = HistoricalReplayEngine()
    try:
        results = engine.run(n_days=60)
        if results:
            engine.print_report(results)
    finally:
        engine.close()
