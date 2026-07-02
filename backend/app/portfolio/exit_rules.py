import numpy as np
from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from datetime import date


def score_dropped(symbol, current_score, threshold=20):
    """Check if score dropped > threshold rank points from last snapshot."""
    session = SessionLocal()
    recent = session.query(ScoreSnapshot).filter(
        ScoreSnapshot.symbol == symbol
    ).order_by(ScoreSnapshot.date.desc()).limit(2).all()
    session.close()
    if len(recent) < 2:
        return False
    prev = recent[1].total_score or 0
    curr = current_score or 0
    return (prev - curr) > threshold


def price_below_sma(prices, period=100):
    """Check if price closed below SMA(period)."""
    if len(prices) < period:
        return False
    sma = np.mean(prices[-period:])
    return prices[-1] < sma


def trailing_stop_triggered(entry_price, current_price, trail_pct=10):
    """Check if 10% trailing stop triggered from highest since entry."""
    if entry_price is None or current_price is None or entry_price <= 0:
        return False
    ret = (current_price - entry_price) / entry_price * 100
    return ret <= -trail_pct


def sector_momentum_reversed(symbol, sector, current_price_ret_3m):
    """Check if broader sector momentum reversed. Disabled — no sector index data."""
    return False


def check_exit(symbol, current_score, entry_price, current_price, prices, sector):
    """Check all exit conditions. Returns (should_exit, reasons)."""
    reasons = []

    if score_dropped(symbol, current_score):
        reasons.append("score_drop>20")
        return True, reasons

    if price_below_sma(prices, 100):
        reasons.append("price<100dma")
        return True, reasons

    if trailing_stop_triggered(entry_price, current_price):
        reasons.append("trailing_stop")
        return True, reasons

    if sector and sector != "Unknown":
        if sector_momentum_reversed(None, sector, None):
            reasons.append("sector_reversal")
            return True, reasons

    return False, reasons
