from sqlalchemy.orm import Session
from datetime import datetime
import yfinance as yf

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.quarterly import QuarterlyFinancials
from app.scoring.alpha_engine import alpha_score
from app.ingestion.fetch_universe import build_stock_universe


def ingest_stock_prices(symbol: str, session: Session):
    """Fetch price data from Yahoo Finance and store in DB."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="2y")

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

        session.commit()
        return True

    except Exception as e:
        print(f"Error ingesting {symbol}: {e}")
        session.rollback()
        return False


def get_stock_data_for_scoring(symbol: str, session: Session) -> dict:
    """Fetch all data for a stock and format for scoring."""
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

    data = {
        "symbol": symbol,
        "current_price": current_price,
        "returns_6m": returns_6m,
        "returns_1y": returns_1y,
        "volume_ratio": volume_ratio,
        "delivery_ratio": 1.0,
        "roce": 15.0,
        "roe": 12.0,
        "debt_equity": 0.5,
        "revenue_acceleration": 10.0,
        "pat_acceleration": 15.0,
        "margin_expansion": 2.0,
        "cashflow_improvement": 5.0,
        "promoter_change": 0.0,
        "pledge_percent": 0.0,
        "relative_strength": returns_1y,
        "alternative_score": 50.0,
        "llm_score": 50.0,
    }

    return data


def run_full_pipeline():
    """Execute complete pipeline: ingest → score → rank."""
    session = SessionLocal()

    try:
        universe = build_stock_universe()

        if universe is None or len(universe) == 0:
            return {"error": "Failed to fetch universe", "stocks": []}

        symbols_to_process = universe[:50]

        processed = 0
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

            if ingest_stock_prices(symbol, session):
                processed += 1

        all_stocks = session.query(Stock).all()
        scored_stocks = []

        for stock in all_stocks[:100]:
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
            "ranked": ranked
        }

    except Exception as e:
        print(f"Pipeline error: {e}")
        session.rollback()
        return {"error": str(e), "stocks": []}

    finally:
        session.close()
