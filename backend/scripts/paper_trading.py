#!/usr/bin/env python3
"""TASK 6 — Paper Trading: 90-day live simulation.
Daily scoring, portfolio construction, PnL tracking.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from datetime import date, datetime, timedelta
from collections import defaultdict

from app.db.database import SessionLocal, engine
from app.models.paper_trading import PaperPosition, PaperTrade
from app.models.scored_stock import ScoredStock
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.stock import Stock
from app.portfolio.regime import detect_regime
from app.portfolio.liquidity_tiers import get_market_cap_tier, is_liquid
from app.portfolio.entry_filters import check_entry, compute_relative_strength


# Create tables
PaperPosition.__table__.create(engine, checkfirst=True)
PaperTrade.__table__.create(engine, checkfirst=True)

print(f"Paper Trading — {'=' * 50}")


def build_portfolio(as_of=None, top_n=50):
    """Build portfolio from latest scores."""
    if as_of is None:
        as_of = date.today()

    session = SessionLocal()

    # Try latest snapshot first, then ScoredStock
    latest_snap = session.query(ScoreSnapshot).filter(
        ScoreSnapshot.date <= as_of
    ).order_by(ScoreSnapshot.date.desc()).first()

    if latest_snap:
        scored = session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == latest_snap.date
        ).order_by(ScoreSnapshot.total_score.desc()).all()
        snap_date = latest_snap.date
    else:
        scored = session.query(ScoredStock).order_by(ScoredStock.total_score.desc()).all()
        snap_date = as_of

    # Load metadata
    stocks = {s.symbol: s for s in session.query(Stock).all()}
    sectors = {s.symbol: s.sector for s in session.query(Stock).all() if s.sector}

    regime_info = detect_regime(as_of)
    regime = regime_info["regime"]

    # Build candidates
    candidates = []
    for s in scored:
        stock = stocks.get(s.symbol)
        sector = sectors.get(s.symbol, "Unknown")
        score = s.total_score or 0
        confidence = s.confidence_score or 0.5

        # Latest price
        price_row = session.query(PriceHistory).filter(
            PriceHistory.symbol == s.symbol
        ).order_by(PriceHistory.date.desc()).first()
        if not price_row or not price_row.close:
            continue
        current_price = price_row.close

        # Price history for SMA
        price_rows = session.query(PriceHistory.close, PriceHistory.volume).filter(
            PriceHistory.symbol == s.symbol,
            PriceHistory.date <= as_of
        ).order_by(PriceHistory.date.desc()).limit(200).all()
        if len(price_rows) < 50:
            continue
        prices = [r[0] for r in price_rows if r[0] is not None and r[0] > 0]
        volumes = [r[1] for r in price_rows if r[1] is not None]
        prices.reverse()
        volumes.reverse()

        # Volume ratio
        vol_ratio = None
        if len(volumes) >= 21:
            vol_ratio = volumes[-1] / max(float(np.mean(volumes[-21:-1])), 1)

        candidates.append(dict(symbol=s.symbol, score=score, confidence=confidence,
                               sector=sector, price=current_price, prices=prices,
                               volume_ratio=vol_ratio))

    session.close()

    if len(candidates) < 50:
        print(f"ERROR: Only {len(candidates)} candidates — cannot build portfolio")
        return {}

    candidates.sort(key=lambda x: -x["score"])
    total = len(candidates)
    for i, c in enumerate(candidates):
        c["score_rank"] = (i / total) * 100

    # Entry filter
    buy_list = []
    for c in candidates:
        ok, _ = check_entry(symbol=c["symbol"], score_rank=c["score_rank"],
                            price_data=c["prices"], sector=c["sector"],
                            volume_ratio=c.get("volume_ratio"))
        if ok:
            buy_list.append(c)
        if len(buy_list) >= top_n:
            break

    # Position sizing
    raw_weights = {}
    for c in buy_list:
        w = c["score"] * c["confidence"]
        ra = 0.5 if regime == "Bear" else (0.75 if regime == "HighVolatility" else 1.0)
        raw_weights[c["symbol"]] = w * ra
    tw = sum(raw_weights.values())
    if tw <= 0:
        return {}
    weights = {k: v / tw for k, v in raw_weights.items()}

    # 5% cap
    for sym, w in list(weights.items()):
        if w > 0.05:
            exc = w - 0.05
            weights[sym] = 0.05
            others = {k: v for k, v in weights.items() if k != sym and weights[k] < 0.05}
            ot = sum(others.values())
            for osym in others:
                weights[osym] += exc * (others[osym] / ot) if ot > 0 else 0

    return weights


def run_paper_trading(days=90, initial_capital=200000):
    """Run paper trading simulation for `days` days."""
    print(f"Paper Trading Simulation")
    print(f"  Period: {days} days")
    print(f"  Initial Capital: ₹{initial_capital:,}")
    print()

    start_date = date.today() - timedelta(days=days)
    end_date = date.today()

    session = SessionLocal()
    capital = initial_capital
    cash = capital
    positions = {}  # {symbol: {entry_date, entry_price, quantity, weight}}
    trades = []
    daily_pnl = []
    nifty_prices = []

    # Get Nifty proxy prices (RELIANCE as broad market proxy)
    nifty_rows = session.query(PriceHistory.close, PriceHistory.date).filter(
        PriceHistory.symbol == "RELIANCE",
        PriceHistory.date >= start_date,
        PriceHistory.date <= end_date,
    ).order_by(PriceHistory.date).all()
    session.close()

    current_date = start_date
    last_rebalance = None
    portfolio_value = 0  # track current portfolio NAV

    while current_date <= end_date:
        is_rebalance = False
        if last_rebalance is None or (current_date - last_rebalance).days >= 30:
            is_rebalance = True
            last_rebalance = current_date

        if is_rebalance:
            weights = build_portfolio(current_date, top_n=50)

            if weights:
                # SELL ALL existing positions first
                for sym in list(positions.keys()):
                    pos = positions[sym]
                    pnl = pos["quantity"] * (pos["current_price"] - pos["entry_price"])
                    trades.append(dict(symbol=sym, entry_date=pos["entry_date"],
                                      exit_date=current_date,
                                      entry_price=pos["entry_price"],
                                      exit_price=pos["current_price"],
                                      return_pct=(pos["current_price"]-pos["entry_price"])/pos["entry_price"]*100,
                                      pnl=pnl, trade_type="Sell"))
                    cash += pos["quantity"] * pos["current_price"]
                    del positions[sym]

                # Then BUY new positions
                for sym, w in weights.items():
                    amount = cash * w  # use remaining cash
                    session = SessionLocal()
                    pr = session.query(PriceHistory).filter(
                        PriceHistory.symbol == sym
                    ).order_by(PriceHistory.date.desc()).first()
                    session.close()
                    if not pr or not pr.close:
                        continue
                    price = pr.close
                    qty = max(1, int(amount / price))

                    positions[sym] = dict(entry_date=current_date,
                                          entry_price=price,
                                          quantity=qty,
                                          weight=w,
                                          current_price=price)
                    trades.append(dict(symbol=sym, entry_date=current_date,
                                      exit_date=None, entry_price=price,
                                      exit_price=None, return_pct=0,
                                      pnl=0, trade_type="Buy"))
                    cash -= qty * price

        # Update prices
        session = SessionLocal()
        total_value = cash
        for sym, pos in list(positions.items()):
            pr = session.query(PriceHistory).filter(
                PriceHistory.symbol == sym,
                PriceHistory.date <= current_date
            ).order_by(PriceHistory.date.desc()).first()
            if pr and pr.close:
                pos["current_price"] = pr.close
                pos["unrealized_pnl"] = (pr.close - pos["entry_price"]) / pos["entry_price"] * 100
                total_value += pos["quantity"] * pr.close
        session.close()

        # Nifty proxy
        nifty_price = None
        for c, d in nifty_rows:
            if d <= current_date:
                nifty_price = c
        nifty_prices.append(nifty_price if nifty_price else 0)

        daily_pnl.append(dict(date=str(current_date),
                              total_value=round(total_value, 2),
                              cash=round(cash, 2),
                              n_positions=len(positions),
                              pnl_pct=round((total_value - capital) / capital * 100, 2)))
        current_date += timedelta(days=1)

    # Final results
    final_value = daily_pnl[-1]["total_value"] if daily_pnl else capital
    total_return = (final_value - capital) / capital * 100
    nifty_start = nifty_prices[0] if nifty_prices else 0
    nifty_end = nifty_prices[-1] if nifty_prices else 0
    nifty_return = (nifty_end - nifty_start) / nifty_start * 100 if nifty_start > 0 else 0

    print(f"\n{'=' * 50}")
    print(f"PAPER TRADING RESULTS")
    print(f"{'=' * 50}")
    print(f"  Period:           {start_date} to {end_date} ({days} days)")
    print(f"  Initial Capital:  ₹{capital:,}")
    print(f"  Final Value:      ₹{final_value:,.0f}")
    print(f"  Total Return:     {total_return:.2f}%")
    print(f"  Nifty Proxy:      {nifty_return:.2f}%")
    print(f"  Excess Return:    {total_return - nifty_return:.2f}%")
    print(f"  Total Trades:     {len(trades)}")
    print(f"  Final Holdings:   {len(positions)}")
    print(f"  Cash:             ₹{cash:,.0f}")

    # Save to DB (clear old data first)
    session = SessionLocal()
    session.query(PaperPosition).delete()
    session.query(PaperTrade).delete()
    session.commit()
    for t in trades:
        session.add(PaperTrade(symbol=t["symbol"], entry_date=t["entry_date"],
                               exit_date=t["exit_date"], entry_price=t["entry_price"],
                               exit_price=t["exit_price"],
                               return_pct=t["return_pct"], pnl=t["pnl"],
                               trade_type=t["trade_type"]))
    for sym, pos in positions.items():
        session.add(PaperPosition(symbol=sym, entry_date=pos["entry_date"],
                                  entry_price=pos["entry_price"],
                                  quantity=pos["quantity"], weight=pos["weight"],
                                  current_price=pos["current_price"],
                                  unrealized_pnl_pct=pos.get("unrealized_pnl", 0)))
    session.commit()
    session.close()

    # Save report
    report = dict(period=f"{start_date} to {end_date}", days=days,
                  initial_capital=capital, final_value=round(final_value, 0),
                  total_return_pct=round(total_return, 2),
                  benchmark_return_pct=round(nifty_return, 2),
                  excess_return_pct=round(total_return - nifty_return, 2),
                  n_trades=len(trades), n_final_holdings=len(positions))
    os.makedirs("/Users/hemant/alpha-hunter/reports", exist_ok=True)
    with open("/Users/hemant/alpha-hunter/reports/paper_trading.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to reports/paper_trading.json")

    return report


if __name__ == "__main__":
    result = run_paper_trading(days=90, initial_capital=200000)
