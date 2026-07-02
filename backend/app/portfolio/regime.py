import numpy as np
from datetime import date, timedelta
from app.db.database import SessionLocal
from app.models.market_regime import MarketRegime
from app.models.price_history import PriceHistory


NIFTY_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "WIPRO", "AXISBANK", "BAJFINANCE", "ADANIGREEN",
    "DMART", "HCLTECH", "SUNPHARMA", "MARUTI", "TITAN",
    "ULTRACEMCO", "NTPC", "ONGC", "POWERGRID", "M&M",
    "TATASTEEL", "JSWSTEEL", "TECHM", "INDUSINDBK", "BAJAJFINSV",
    "ADANIPORTS", "ASIANPAINT", "NESTLEIND", "HDFC", "BAJAJHLDNG",
    "COALINDIA", "IOC", "BPCL", "GAIL", "HEROMOTOCO",
    "EICHERMOT", "BRITANNIA", "DABUR", "MARICO", "PIDILITIND",
    "HINDZINC", "COLPAL", "HAVELLS", "TORNTPHARM", "DIVISLAB",
]


def fetch_nifty_data():
    """Compute Nifty 50 price and 200 DMA from constituent stocks.
    Returns {date: price} and {date: 200dma_pct}."""
    session = SessionLocal()
    rows = session.query(PriceHistory.symbol, PriceHistory.date, PriceHistory.close).filter(
        PriceHistory.symbol.in_(NIFTY_SYMBOLS)
    ).order_by(PriceHistory.symbol, PriceHistory.date).all()
    session.close()

    price_map = {}
    for sym, dt, close in rows:
        if close is None or close == 0:
            continue
        price_map.setdefault(dt, []).append(close)

    nifty_prices = {}
    for dt, closes in sorted(price_map.items()):
        nifty_prices[dt] = np.mean(closes)

    dates_arr = np.array(sorted(nifty_prices.keys()))
    prices_arr = np.array([nifty_prices[d] for d in dates_arr])

    sma_200 = {}
    for i, d in enumerate(dates_arr):
        if i >= 199:
            sma_200[d] = np.mean(prices_arr[i - 199:i + 1])
        else:
            sma_200[d] = np.mean(prices_arr[:i + 1])

    pct_from_200dma = {}
    for d in dates_arr:
        pct_from_200dma[d] = (nifty_prices[d] / sma_200[d] - 1) * 100

    return nifty_prices, pct_from_200dma


def fetch_vix():
    """Fetch India VIX from yfinance."""
    try:
        import yfinance as yf
        vix = yf.download("^INDIAVIX", period="1y", progress=False)
        if vix.empty:
            return {}
        vix_data = {}
        for idx, row in vix.iterrows():
            dt = idx.date()
            close = float(row["Close"])
            if close > 0:
                vix_data[dt] = close
        return vix_data
    except Exception:
        return {}


def compute_ad_ratio(as_of, lookback=20):
    """Compute advance/decline ratio over lookback period."""
    session = SessionLocal()
    start = as_of - timedelta(days=lookback * 2)
    rows = session.query(PriceHistory.symbol, PriceHistory.date, PriceHistory.close).filter(
        PriceHistory.date >= start, PriceHistory.date <= as_of
    ).order_by(PriceHistory.symbol, PriceHistory.date).all()
    session.close()

    stock_prices = {}
    for sym, dt, close in rows:
        if close is None or close == 0:
            continue
        stock_prices.setdefault(sym, []).append((dt, close))

    advances, declines = 0, 0
    for sym, price_list in stock_prices.items():
        if len(price_list) < 2:
            continue
        prices_sorted = sorted(price_list, key=lambda x: x[0])
        start_price = prices_sorted[0][1]
        end_price = prices_sorted[-1][1]
        if end_price > start_price:
            advances += 1
        else:
            declines += 1

    if declines == 0:
        return advances
    return advances / declines


def vix_percentile(vix_data, days=252):
    """Compute current VIX percentile."""
    if not vix_data:
        return None
    sorted_dates = sorted(vix_data.keys())
    if len(sorted_dates) < 20:
        return None

    current_vix = vix_data[sorted_dates[-1]]
    history = [vix_data[d] for d in sorted_dates[-min(days, len(sorted_dates)):]]
    percentile = sum(1 for v in history if v <= current_vix) / len(history) * 100
    return percentile


def classify_regime(nifty_pct, vix_pctl, ad_ratio):
    """Classify market regime from signals."""
    signals = []

    # Bull/bear from Nifty 200 DMA
    if nifty_pct is not None:
        if nifty_pct > 5:
            signals.append("Bull")
        elif nifty_pct < -5:
            signals.append("Bear")
        elif nifty_pct > 2:
            signals.append("Bull")
        elif nifty_pct < -2:
            signals.append("Bear")

    # Volatility from VIX
    if vix_pctl is not None:
        if vix_pctl > 80:
            signals.append("HighVol")

    # A/D ratio
    if ad_ratio is not None:
        if ad_ratio > 1.5:
            signals.append("Bull")
        elif ad_ratio < 0.7:
            signals.append("Bear")

    bull_count = signals.count("Bull")
    bear_count = signals.count("Bear")
    highvol = "HighVol" in signals

    if highvol and bear_count > 0:
        return "Bear"
    if highvol:
        return "HighVolatility"
    if bull_count >= bear_count + 1:
        return "Bull"
    if bear_count >= bull_count + 1:
        return "Bear"
    return "Rangebound"


def detect_regime(as_of=None):
    """Main regime detection function."""
    if as_of is None:
        as_of = date.today()

    nifty_prices, nifty_pct_map = fetch_nifty_data()
    vix_data = fetch_vix()
    ad_ratio = compute_ad_ratio(as_of)

    # Find closest date
    sorted_nifty_dates = sorted(nifty_pct_map.keys())
    closest_date = None
    for d in sorted_nifty_dates:
        if d <= as_of:
            closest_date = d

    nifty_pct = nifty_pct_map.get(closest_date) if closest_date else None
    vix_pctl = vix_percentile(vix_data)

    regime = classify_regime(nifty_pct, vix_pctl, ad_ratio)

    # Store in DB
    session = SessionLocal()
    existing = session.query(MarketRegime).filter(MarketRegime.date == as_of).first()
    if existing:
        existing.regime = regime
        existing.nifty_200dma_pct = nifty_pct
        existing.vix_percentile = vix_pctl
        existing.ad_ratio = ad_ratio
    else:
        session.add(MarketRegime(
            date=as_of,
            regime=regime,
            nifty_200dma_pct=nifty_pct,
            vix_percentile=vix_pctl,
            ad_ratio=ad_ratio,
        ))
    session.commit()
    session.close()

    return {
        "date": as_of,
        "regime": regime,
        "nifty_200dma_pct": nifty_pct,
        "vix_percentile": vix_pctl,
        "ad_ratio": ad_ratio,
    }


def get_regime(as_of=None):
    """Get current regime from DB, detect if none exists."""
    if as_of is None:
        as_of = date.today()
    session = SessionLocal()
    rec = session.query(MarketRegime).filter(MarketRegime.date == as_of).first()
    session.close()
    if rec:
        return {
            "date": rec.date,
            "regime": rec.regime,
            "nifty_200dma_pct": rec.nifty_200dma_pct,
            "vix_percentile": rec.vix_percentile,
            "ad_ratio": rec.ad_ratio,
        }
    return detect_regime(as_of)
