import numpy as np
from app.db.database import SessionLocal
from app.models.price_history import PriceHistory


def get_stock_volatility(symbol, lookback=60):
    session = SessionLocal()
    rows = session.query(PriceHistory.close).filter(
        PriceHistory.symbol == symbol
    ).order_by(PriceHistory.date.desc()).limit(lookback + 1).all()
    session.close()
    if len(rows) < 10:
        return 0.4
    prices = [r[0] for r in rows if r[0] is not None and r[0] > 0]
    if len(prices) < 10:
        return 0.4
    rets = np.diff(prices) / prices[:-1]
    return float(np.std(rets) * np.sqrt(252))


def kelly_fraction(score, base_win_rate=0.50, base_edge=0.02):
    win_prob = 0.40 + (score / 100) * 0.30
    win_prob = min(win_prob, 0.75)
    loss_prob = 1 - win_prob
    avg_win = 0.03 + (score / 100) * 0.07
    avg_loss = 0.03
    if avg_loss <= 0:
        return 0.05
    fraction = (win_prob / avg_loss) - (loss_prob / avg_win) if avg_win > 0 else 0
    return max(0.01, min(fraction, 0.50))


def size_position(score, confidence, symbol=None, method="kelly"):
    """Compute position weight.
    kelly: score-based Kelly fraction, capped at 5%.
    inverse_vol: position = 0.04 / ann_vol.
    Max 5%, min 1%.
    """
    if method == "kelly":
        raw = kelly_fraction(score) * 0.10
    elif method == "inverse_vol":
        vol = get_stock_volatility(symbol) if symbol else 0.4
        raw = 0.04 / max(vol, 0.10)
    elif method == "equal":
        raw = 0.03
    else:
        raw = 0.03

    weight = raw * confidence
    return round(max(0.01, min(weight, 0.05)), 4)
