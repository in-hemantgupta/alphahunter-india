from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from datetime import date, timedelta
import numpy as np


def get_market_cap_tier(symbol):
    """Classify stock by market cap tier."""
    session = SessionLocal()
    stock = session.query(Stock).filter(Stock.symbol == symbol).first()
    session.close()
    if stock is None or stock.market_cap is None:
        return "C"

    mc = stock.market_cap
    if mc >= 10000e7:  # 10000 crore
        return "A"
    elif mc >= 1000e7:  # 1000 crore
        return "B"
    else:
        return "C"


def get_daily_turnover(symbol):
    """Compute avg daily turnover in crores."""
    session = SessionLocal()
    end = date.today()
    start = end - timedelta(days=90)
    rows = session.query(PriceHistory.close, PriceHistory.volume).filter(
        PriceHistory.symbol == symbol,
        PriceHistory.date >= start,
        PriceHistory.date <= end,
    ).all()
    session.close()
    if len(rows) < 10:
        return 0
    turnovers = []
    for close, volume in rows:
        if close and volume:
            turnovers.append(close * volume / 1e7)
    return float(np.mean(turnovers)) if turnovers else 0


def compute_liquidity_score(symbol):
    """Compute overall liquidity score 0-100."""
    tier = get_market_cap_tier(symbol)
    turnover = get_daily_turnover(symbol)

    tier_scores = {"A": 100, "B": 70, "C": 40}
    base = tier_scores.get(tier, 40)

    turnover_score = min(turnover / 5 * 100, 100)  # ₹5cr+ = 100

    if turnover < 1:
        return 0

    score = base * 0.5 + turnover_score * 0.5
    return int(score)


def get_liquidity_allocation_limit(tier):
    """Max % of portfolio allocated to a tier."""
    limits = {"A": 1.0, "B": 0.50, "C": 0.15}
    return limits.get(tier, 0.15)


def is_liquid(symbol):
    """Minimum liquidity check for entry."""
    if compute_liquidity_score(symbol) == 0:
        return False
    turnover = get_daily_turnover(symbol)
    if turnover < 1:
        return False
    return True
