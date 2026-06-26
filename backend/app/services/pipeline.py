import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
yf = None  # disabled by auto patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.quarterly import QuarterlyFinancials
from app.scoring.alpha_engine import alpha_score
from app.ingestion.fetch_universe import build_stock_universe


def _ingest_one(symbol: str) -> tuple[str, bool]:
    """Thread-safe ingestion for parallel execution."""
    session = SessionLocal()
    try:
        ok = ingest_stock_prices(symbol, session)
        return symbol, ok
    except Exception as e:
        print(f"Error ingesting {symbol}: {e}")
        return symbol, False
    finally:
        session.close()


def ingest_stock_prices(symbol: str, session: Session):
    try:
        ticker = None
        info = {} or {}
        hist = pd.DataFrame()

        if hist.empty:
            return False

        for date, row in hist.iterrows():
            existing = session.query(PriceHistory).filter_by(
                symbol=symbol,
                date=date.date()
            ).first()

            if not existing:
                price_record = PriceHistory(
                    symbol=symbol,
                    date=date.date(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume'])
                )
                session.add(price_record)

        stock = session.query(Stock).filter_by(symbol=symbol).first()
        if stock and not stock.market_cap:
            mcap = info.get('marketCap')
            if mcap and mcap > 0:
                stock.market_cap = int(mcap)

        session.commit()
        return True

    except Exception as e:
        print(f"Error ingesting {symbol}: {e}")
        session.rollback()
        return False


import hashlib

def _vary(symbol: str, field: str, lo: float, hi: float) -> float:
    h = int(hashlib.md5(f"{symbol}:{field}".encode()).hexdigest()[:8], 16)
    return lo + (h % 1000) / 1000.0 * (hi - lo)


def get_stock_data_for_scoring(symbol: str, session: Session) -> dict:
    stock = session.query(Stock).filter_by(symbol=symbol).first()
    if not stock:
        return {}

    prices = session.query(PriceHistory).filter_by(
        symbol=symbol
    ).order_by(PriceHistory.date.desc()).limit(252).all()

    if not prices:
        return {}

    current_price = prices[0].close
    price_6m_ago = prices[126].close if len(prices) > 126 else current_price
    price_1y_ago = prices[252].close if len(prices) > 252 else current_price

    returns_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
    returns_1y = ((current_price - price_1y_ago) / price_1y_ago) * 100

    volumes = [p.volume for p in prices[:30]]
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    current_volume = prices[0].volume
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

    # ponytail: derive mock fundamentals from returns + symbol hash, replace when real data ingested
    r1y = max(-50, min(50, returns_1y))
    r6m = max(-30, min(30, returns_6m))
    mcap = stock.market_cap or 0
    quality_bias = min(20, max(0, (mcap / 1e10 - 5) / 5 * 20)) if mcap else 0
    fwd = 55 + r1y * 0.3 + r6m * 0.2 + quality_bias + _vary(symbol, "base", -8, 8)

    # Compute technical fields from price data
    closes = [p.close for p in prices]
    highs = [p.high for p in prices]
    lows = [p.low for p in prices]
    all_volumes = [p.volume for p in prices]

    high_52w = max(highs) if highs else current_price
    recent_returns = [(closes[i] - closes[i+1]) / closes[i+1] for i in range(min(20, len(closes)-1))]
    volume_20d = sum(all_volumes[:20]) / min(20, len(all_volumes)) if all_volumes else 1
    volume_90d = sum(all_volumes[:90]) / min(90, len(all_volumes)) if all_volumes else 1

    # ATR-14 calculation
    tr_list = []
    for i in range(min(14, len(prices)-1)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i+1]), abs(lows[i] - closes[i+1]))
        tr_list.append(tr)
    atr_14 = sum(tr_list) / len(tr_list) if tr_list else 1

    # VWAP approximation (last 20 days)
    vwap = sum(closes[i] * all_volumes[i] for i in range(min(20, len(closes)))) / sum(all_volumes[:20]) if len(closes) >= 20 and sum(all_volumes[:20]) > 0 else current_price

    # Price change %
    price_change = ((closes[0] - closes[1]) / closes[1] * 100) if len(closes) > 1 else 0

    # Volume spike detection
    volume_spike = all_volumes[0] > (sum(all_volumes[1:31]) / min(30, len(all_volumes)-1)) * 2 if len(all_volumes) > 1 else False

    # Benchmark return (mock Nifty 50)
    benchmark_return = 12.0 + _vary(symbol, "bench", -5, 5)

    data = {
        "symbol": symbol,
        "company_name": stock.company_name or "",
        "current_price": current_price,
        "returns_6m": returns_6m,
        "returns_1y": returns_1y,
        "volume_ratio": volume_ratio,
        "delivery_ratio": 0.5 + _vary(symbol, "del", 0, 2.5),
        "roce": fwd + _vary(symbol, "roce", -5, 15),
        "roe": fwd + _vary(symbol, "roe", -5, 12),
        "debt_equity": max(0.1, 1.5 - fwd / 60 + _vary(symbol, "de", -0.4, 0.4)),
        "revenue_acceleration": max(-5, returns_1y * 0.5 + _vary(symbol, "ra", -5, 10)),
        "pat_acceleration": max(-5, returns_1y * 0.6 + _vary(symbol, "pa", -5, 10)),
        "margin_expansion": _vary(symbol, "me", -3, 8),
        "cashflow_improvement": max(-3, returns_1y * 0.3 + _vary(symbol, "cf", -5, 8)),
        "promoter_change": _vary(symbol, "pc", -3, 5),
        "pledge_percent": _vary(symbol, "pp", 0, 12),
        "relative_strength": 50 + returns_1y * 0.5,
        "alternative_score": 30 + _vary(symbol, "alt", 0, 40),
        "llm_score": 30 + _vary(symbol, "llm", 0, 40),

        # Microstructure fields
        "delivery_20d_avg": 40 + _vary(symbol, "d20", 0, 20),
        "delivery_today": 40 + _vary(symbol, "dt", 0, 30),
        "close": current_price,
        "vwap": vwap,
        "delivery_percent": 40 + _vary(symbol, "dp", 0, 30),
        "price_change": price_change,
        "today_volume": all_volumes[0] if all_volumes else 1,
        "avg_30d_volume": sum(all_volumes[:30]) / min(30, len(all_volumes)) if all_volumes else 1,
        "atr_14": atr_14,
        "volume_spike": volume_spike,
        "recent_bulk_buy": _vary(symbol, "bb", 0, 1) > 0.7,

        # Technical fields
        "stock_return": returns_1y,
        "benchmark_return": benchmark_return,
        "high_52w": high_52w,
        "recent_returns": recent_returns,
        "volume_20d": volume_20d,
        "volume_90d": volume_90d,
        "price_series": closes[:60],

        # Alternative fields (mock until real data sources integrated)
        "job_postings_growth": _vary(symbol, "jg", 0, 50),
        "new_order_value": _vary(symbol, "nov", 0, 1000),
        "annual_revenue": 5000 + _vary(symbol, "ar", 0, 5000),
        "new_patents": int(_vary(symbol, "np", 0, 5)),
        "news_mentions_growth": _vary(symbol, "nmg", 0, 60),
        "sector_rotation_score": 40 + _vary(symbol, "sr", 0, 40),
        "search_trend_score": 40 + _vary(symbol, "st", 0, 40),
        "shipment_growth": _vary(symbol, "sg", 0, 40),
    }

    return data


def run_full_pipeline():
    """Execute complete pipeline: ingest → score → rank."""
    session = SessionLocal()

    try:
        universe = build_stock_universe()

        if universe is None or len(universe) == 0:
            return {"error": "Failed to fetch universe", "stocks": pd.DataFrame()}

        # ponytail: shuffle to get cross-alphabet coverage, not just A-names
        symbols_to_process = universe.sample(min(500, len(universe)))

        # Phase 1: Insert new symbols into DB (fast, single-threaded)
        new_symbols = []
        for _, row in symbols_to_process.iterrows():
            symbol = row.get('SYMBOL')
            if not symbol:
                continue
            existing = session.query(Stock).filter_by(symbol=symbol).first()
            if not existing:
                stock = Stock(
                    symbol=symbol,
                    company_name=row.get('NAME OF COMPANY', ''),
                    sector='Unknown',
                    exchange='NSE'
                )
                session.add(stock)
                session.commit()
                new_symbols.append(symbol)

        # Phase 2: Gather stocks that need price data
        symbols_to_ingest = []
        skipped = 0
        for _, row in symbols_to_process.iterrows():
            symbol = row.get('SYMBOL')
            if not symbol:
                continue
            price_count = session.query(PriceHistory).filter_by(symbol=symbol).count()
            if price_count > 0:
                skipped += 1
                continue
            symbols_to_ingest.append(symbol)

        # Phase 3: Parallel ingestion (10 workers)
        processed = 0
        if symbols_to_ingest:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(_ingest_one, sym): sym for sym in symbols_to_ingest}
                for future in as_completed(futures):
                    symbol, ok = future.result()
                    if ok:
                        processed += 1
                    if (processed + len(futures) - len([f for f in futures if not f.done()])) % 25 == 0:
                        pass  # progress tracked per batch

        all_stocks = session.query(Stock).all()
        scored_stocks = []

        for stock in all_stocks:
            data = get_stock_data_for_scoring(stock.symbol, session)
            if data:
                score = alpha_score(data)
                data['total_score'] = score
                scored_stocks.append(data)

        ranked = sorted(
            scored_stocks,
            key=lambda x: x['total_score'],
            reverse=True
        )[:30]

        return {
            "status": "success",
            "processed": processed,
            "skipped": skipped,
            "ranked": ranked
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline error: {e}")
        session.rollback()
        return {"error": str(e), "stocks": pd.DataFrame()}

    finally:
        session.close()
