"""Walk-forward backtest engine using score_snapshots.
Requires 24 months of historical snapshots to produce valid results.
Currently blocked — only single snapshot exists (2026-06-30)."""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory


def run_walkforward_backtest():
    """Walk-forward backtest over available score snapshots.
    For each monthly snapshot: pick top 50, hold 30 days, rebalance.
    Returns metrics dict or error if insufficient snapshots."""
    session = SessionLocal()

    snapshot_dates = [
        r[0] for r in
        session.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()
    ]
    session.close()

    if len(snapshot_dates) < 2:
        return {
            "status": "BLOCKED",
            "reason": f"Need >=2 monthly snapshots for walk-forward test. Got {len(snapshot_dates)}: {snapshot_dates}",
            "n_snapshots": len(snapshot_dates),
            "dates": [str(d) for d in snapshot_dates],
            "missing_infrastructure": "Run pipeline monthly for 24 months, or backfill historical score_snapshots.",
        }

    # Full backtest implementation (ready when snapshots exist)
    session = SessionLocal()
    all_trades = []
    portfolio_values = []
    benchmark_values = []

    for snap_date in sorted(snapshot_dates):
        # Pick top 50 from this snapshot
        top50 = (
            session.query(ScoreSnapshot)
            .filter(ScoreSnapshot.date == snap_date)
            .order_by(ScoreSnapshot.total_score.desc())
            .limit(50)
            .all()
        )
        symbols = [s.symbol for s in top50]

        # Hold for 30 trading days
        hold_end = snap_date + timedelta(days=45)

        # Fetch prices
        for sym in symbols:
            prices = (
                session.query(PriceHistory)
                .filter(
                    PriceHistory.symbol == sym,
                    PriceHistory.date > snap_date,
                    PriceHistory.date <= hold_end,
                )
                .order_by(PriceHistory.date)
                .all()
            )
            if len(prices) >= 2:
                entry_price = prices[0].close
                exit_price = prices[-1].close
                ret = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
                all_trades.append({
                    "symbol": sym,
                    "entry_date": str(prices[0].date),
                    "exit_date": str(prices[-1].date),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_pct": round(ret * 100, 2),
                })

    session.close()

    if not all_trades:
        return {"status": "ERROR", "reason": "No trades generated"}

    returns = np.array([t["return_pct"] for t in all_trades])
    mean_ret = np.mean(returns)
    std_ret = np.std(returns)
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0
    hit_rate = np.sum(returns > 0) / len(returns) * 100
    max_dd = np.min(np.cumsum(returns))

    return {
        "status": "COMPLETE",
        "n_trades": len(all_trades),
        "n_months": len(snapshot_dates),
        "avg_return_pct": round(float(mean_ret), 2),
        "std_return_pct": round(float(std_ret), 2),
        "sharpe": round(float(sharpe), 3),
        "hit_rate_pct": round(float(hit_rate), 1),
        "max_drawdown_pct": round(float(max_dd), 1),
        "sample_trades": all_trades[:10],
    }
