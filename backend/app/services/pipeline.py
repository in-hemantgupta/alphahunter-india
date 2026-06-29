import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.quarterly import QuarterlyFinancials
from app.models.shareholding import ShareholdingPattern
from app.models.scored_stock import ScoredStock
from app.scoring.alpha_engine import alpha_score
from app.ingestion.fetch_universe import build_stock_universe
from app.ingestion.financial_ingestor import FinancialIngestor
from app.ingestion.shareholding_ingestor import ShareholdingIngestor
from app.services.elimination import run_elimination_pipeline

_nifty_return_cache = None


def _get_nifty_return():
    global _nifty_return_cache
    if _nifty_return_cache is not None:
        return _nifty_return_cache
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="1y")
        if len(hist) > 2:
            _nifty_return_cache = ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100
        else:
            _nifty_return_cache = 0
    except:
        _nifty_return_cache = 0
    return _nifty_return_cache


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
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}
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

        stock = session.query(Stock).filter_by(symbol=symbol).first()
        if stock and not stock.market_cap:
            mcap = info.get('marketCap')
            if mcap is not None and isinstance(mcap,(int,float)) and mcap > 0:
                stock.market_cap = int(mcap)

        session.commit()
        return True

    except Exception as e:
        print(f"Error ingesting {symbol}: {e}")
        session.rollback()
        return False


import hashlib


def _calculate_delivery_ratio(prices, volumes):
    """Estimate delivery ratio from volume patterns.
    Uses high-volume days with small price moves as proxy for accumulation (delivery buying)."""
    if len(prices) < 5 or len(volumes) < 5:
        return 1.0

    avg_vol = sum(volumes[:20]) / min(20, len(volumes))
    if avg_vol == 0:
        return 1.0

    high_vol_days = 0
    total_days = min(20, len(prices))

    for i in range(total_days):
        if volumes[i] > avg_vol * 1.5:
            price_move = abs(prices[i].close - prices[i].open) / prices[i].open if prices[i].open > 0 else 0
            if price_move < 0.02:
                high_vol_days += 1

    ratio = 1.0 + (high_vol_days / total_days) * 1.5
    return min(3.0, ratio)


def get_stock_data_for_scoring(symbol: str, session: Session) -> dict:
    stock = session.query(Stock).filter_by(symbol=symbol).first()
    if not stock:
        return None

    prices = session.query(PriceHistory).filter_by(
        symbol=symbol
    ).order_by(PriceHistory.date.desc()).limit(252).all()

    if not prices:
        return None

    current_price = prices[0].close
    price_6m_ago = prices[126].close if len(prices) > 126 else current_price
    price_1y_ago = prices[252].close if len(prices) > 252 else current_price

    returns_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
    returns_1y = ((current_price - price_1y_ago) / price_1y_ago) * 100

    volumes = [p.volume for p in prices[:30]]
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    current_volume = prices[0].volume
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

    closes = [p.close for p in prices]
    highs = [p.high for p in prices]
    lows = [p.low for p in prices]
    all_volumes = [p.volume for p in prices]

    high_52w = max(highs) if highs else current_price
    recent_returns = [(closes[i] - closes[i+1]) / closes[i+1] for i in range(min(20, len(closes)-1))]
    volume_20d = sum(all_volumes[:20]) / min(20, len(all_volumes)) if all_volumes else 1
    volume_90d = sum(all_volumes[:90]) / min(90, len(all_volumes)) if all_volumes else 1

    tr_list = []
    for i in range(min(14, len(prices)-1)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i+1]), abs(lows[i] - closes[i+1]))
        tr_list.append(tr)
    atr_14 = sum(tr_list) / len(tr_list) if tr_list else 1

    vwap = sum(closes[i] * all_volumes[i] for i in range(min(20, len(closes)))) / sum(all_volumes[:20]) if len(closes) >= 20 and sum(all_volumes[:20]) > 0 else current_price

    price_change = ((closes[0] - closes[1]) / closes[1] * 100) if len(closes) > 1 else 0

    volume_spike = all_volumes[0] > (sum(all_volumes[1:31]) / min(30, len(all_volumes)-1)) * 2 if len(all_volumes) > 1 else False

    benchmark_return = _get_nifty_return()

    quarterly_data = session.query(QuarterlyFinancials).filter_by(
        symbol=symbol
    ).order_by(QuarterlyFinancials.quarter.desc()).limit(8).all()

    roce = 0
    roe = 0
    debt_equity = 1
    revenue_acceleration = 0
    pat_acceleration = 0
    margin_expansion = 0
    cashflow_improvement = 0
    operating_cashflow = 0
    fcf_trend = 0
    margin_stability = 0

    if len(quarterly_data) >= 2:
        latest = quarterly_data[0]
        prev = quarterly_data[1]

        roce = latest.roce or 0
        roe = latest.roe or 0
        debt_equity = latest.debt_equity or 1

        if prev.revenue and prev.revenue > 0 and latest.revenue:
            revenue_growth_latest = ((latest.revenue - prev.revenue) / prev.revenue) * 100
            if len(quarterly_data) >= 3:
                prev2 = quarterly_data[2]
                if prev2.revenue and prev2.revenue > 0:
                    revenue_growth_prev = ((prev.revenue - prev2.revenue) / prev2.revenue) * 100
                    revenue_acceleration = revenue_growth_latest - revenue_growth_prev
                else:
                    revenue_acceleration = revenue_growth_latest
            else:
                revenue_acceleration = revenue_growth_latest

        if prev.pat and prev.pat > 0 and latest.pat:
            pat_growth_latest = ((latest.pat - prev.pat) / prev.pat) * 100
            if len(quarterly_data) >= 3:
                prev2 = quarterly_data[2]
                if prev2.pat and prev2.pat > 0:
                    pat_growth_prev = ((prev.pat - prev2.pat) / prev2.pat) * 100
                    pat_acceleration = pat_growth_latest - pat_growth_prev
                else:
                    pat_acceleration = pat_growth_latest
            else:
                pat_acceleration = pat_growth_latest

        if prev.ebitda and prev.revenue and prev.revenue > 0 and latest.ebitda and latest.revenue and latest.revenue > 0:
            margin_latest = (latest.ebitda / latest.revenue) * 100
            margin_prev = (prev.ebitda / prev.revenue) * 100
            margin_expansion = margin_latest - margin_prev

        if len(quarterly_data) >= 4:
            margins = []
            for q in quarterly_data[:4]:
                if q.ebitda and q.revenue and q.revenue > 0:
                    margins.append((q.ebitda / q.revenue) * 100)
            if len(margins) >= 2:
                margin_stability = 100 - (max(margins) - min(margins))

    shareholding_data = session.query(ShareholdingPattern).filter_by(
        symbol=symbol
    ).order_by(ShareholdingPattern.quarter.desc()).limit(4).all()

    promoter_change = 0
    pledge_percent = 0

    if len(shareholding_data) >= 2:
        latest_sh = shareholding_data[0]
        prev_sh = shareholding_data[1]

        if latest_sh.promoter is not None and prev_sh.promoter is not None:
            promoter_change = latest_sh.promoter - prev_sh.promoter

        if latest_sh.pledge is not None:
            pledge_percent = latest_sh.pledge

    delivery_ratio = _calculate_delivery_ratio(prices, all_volumes)

    if len(closes) >= 20:
        sma_20 = sum(closes[:20]) / 20
        sma_50 = sum(closes[:50]) / min(50, len(closes)) if len(closes) >= 50 else sma_20
        trend_strength = (sma_20 - sma_50) / sma_50 if sma_50 > 0 else 0
        compression_pattern = abs(sma_20 - sma_50) / sma_50 < 0.05 if sma_50 > 0 else False
        breakout_probability = 0.5 + (returns_6m / 200) if returns_6m > 0 else 0.3
        volume_confirmation = volume_20d > volume_90d * 1.2
    else:
        trend_strength = 0
        compression_pattern = False
        breakout_probability = 0.3
        volume_confirmation = False

    volume_high = volume_ratio > 1.5
    price_flat = abs(price_change) < 2.0
    vwap_defense = current_price >= vwap * 0.98 if vwap > 0 else False
    price_compression = compression_pattern
    seller_exhaustion = returns_6m < -10 and volume_ratio < 0.7
    bulk_deal_positive = False

    promoter_declining = promoter_change < -5
    auditor_changed = False
    dilution_rate = 0
    cash_conversion = 1.0 if operating_cashflow > 0 else 0.5
    governance_red_flags = False

    roce_trend = 0
    if len(quarterly_data) >= 3:
        roce_values = [q.roce for q in quarterly_data[:3] if q.roce]
        if len(roce_values) >= 2:
            roce_trend = roce_values[0] - roce_values[-1]

    capex_efficiency = 0
    if len(quarterly_data) >= 2:
        latest = quarterly_data[0]
        prev = quarterly_data[1]
        if latest.revenue and prev.revenue and prev.revenue > 0:
            revenue_growth = ((latest.revenue - prev.revenue) / prev.revenue) * 100
            capex_efficiency = revenue_growth

    # Calculate heuristic scores for Alternative Data layer
    # Use available data as proxy signals
    google_trend_score = 0
    contract_score = 0
    shipment_score = 0
    hiring_score = 0
    patent_score = 0
    news_score = 0
    
    # Use revenue acceleration as proxy for market interest
    if revenue_acceleration > 100:
        google_trend_score = 80
        news_score = 75
    elif revenue_acceleration > 50:
        google_trend_score = 70
        news_score = 65
    elif revenue_acceleration > 20:
        google_trend_score = 55
        news_score = 50
    
    # Use margin expansion as proxy for competitive advantage
    if margin_expansion > 200:  # 200 bps
        contract_score = 80
        shipment_score = 75
    elif margin_expansion > 100:
        contract_score = 65
        shipment_score = 60
    elif margin_expansion > 50:
        contract_score = 50
        shipment_score = 45
    
    # Use ROCE trend as proxy for operational efficiency
    if roce_trend > 5:
        hiring_score = 80
        patent_score = 70
    elif roce_trend > 2:
        hiring_score = 65
        patent_score = 55
    elif roce_trend > 0:
        hiring_score = 50
        patent_score = 40

    # Calculate heuristic scores for LLM Intelligence layer
    # Based on quality indicators from available data
    annual_report_score = 0
    concall_score = 0
    governance_score = 0
    narrative_score = 0
    risk_score = 0
    management_confidence = 0
    
    # Use fundamental quality as proxy for report quality
    if roce > 25 and debt_equity < 0.3:
        annual_report_score = 85
        concall_score = 80
    elif roce > 20 and debt_equity < 0.5:
        annual_report_score = 75
        concall_score = 70
    elif roce > 15 and debt_equity < 0.7:
        annual_report_score = 65
        concall_score = 60
    elif roce > 10:
        annual_report_score = 50
        concall_score = 45
    
    # Use promoter behavior as proxy for governance
    if promoter_change > 0 and pledge_percent < 2:
        governance_score = 85
        management_confidence = 80
    elif promoter_change > 0 and pledge_percent < 5:
        governance_score = 75
        management_confidence = 70
    elif promoter_change > -2 and pledge_percent < 10:
        governance_score = 60
        management_confidence = 55
    elif pledge_percent < 15:
        governance_score = 45
        management_confidence = 40
    
    # Use return consistency as proxy for narrative strength
    if returns_1y > 40 and returns_6m > 20:
        narrative_score = 80
        risk_score = 75
    elif returns_1y > 30 and returns_6m > 15:
        narrative_score = 70
        risk_score = 65
    elif returns_1y > 15 and returns_6m > 5:
        narrative_score = 55
        risk_score = 50
    elif returns_1y > 0:
        narrative_score = 40
        risk_score = 35

    data = {
        "symbol": symbol,
        "company_name": stock.company_name or "",
        "current_price": current_price,
        "returns_6m": returns_6m,
        "returns_1y": returns_1y,
        "volume_ratio": volume_ratio,
        "delivery_ratio": delivery_ratio,
        "roce": roce,
        "roe": roe,
        "debt_equity": debt_equity,
        "revenue_acceleration": revenue_acceleration,
        "pat_acceleration": pat_acceleration,
        "margin_expansion": margin_expansion,
        "cashflow_improvement": cashflow_improvement,
        "operating_cashflow": operating_cashflow,
        "fcf_trend": fcf_trend,
        "margin_stability": margin_stability,
        "promoter_change": promoter_change,
        "pledge_percent": pledge_percent,
        "roce_trend": roce_trend,
        "capex_efficiency": capex_efficiency,
        "governance_clean": True,
        "relative_strength": 50 + returns_1y * 0.5,
        "delivery_20d_avg": 0,
        "delivery_today": 0,
        "close": current_price,
        "vwap": vwap,
        "delivery_percent": 0,
        "price_change": price_change,
        "today_volume": all_volumes[0] if all_volumes else 1,
        "avg_30d_volume": sum(all_volumes[:30]) / min(30, len(all_volumes)) if all_volumes else 1,
        "atr_14": atr_14,
        "volume_spike": volume_spike,
        "recent_bulk_buy": False,
        "stock_return": returns_1y,
        "benchmark_return": benchmark_return,
        "high_52w": high_52w,
        "recent_returns": recent_returns,
        "volume_20d": volume_20d,
        "volume_90d": volume_90d,
        "price_series": closes[:60],
        "trend_strength": trend_strength,
        "compression_pattern": compression_pattern,
        "breakout_probability": breakout_probability,
        "volume_confirmation": volume_confirmation,
        "volume_high": volume_high,
        "price_flat": price_flat,
        "vwap_defense": vwap_defense,
        "price_compression": price_compression,
        "seller_exhaustion": seller_exhaustion,
        "bulk_deal_positive": bulk_deal_positive,
        "promoter_declining": promoter_declining,
        "auditor_changed": auditor_changed,
        "dilution_rate": dilution_rate,
        "cash_conversion": cash_conversion,
        "governance_red_flags": governance_red_flags,
        "google_trend_score": google_trend_score,
        "contract_score": contract_score,
        "shipment_score": shipment_score,
        "hiring_score": hiring_score,
        "patent_score": patent_score,
        "news_score": news_score,
        "annual_report_score": annual_report_score,
        "concall_score": concall_score,
        "governance_score": governance_score,
        "narrative_score": narrative_score,
        "risk_score": risk_score,
        "management_confidence": management_confidence,
    }

    return data


def run_full_pipeline(force: bool = False):
    import time
    t0 = time.time()
    print("PIPELINE START")

    """Execute complete pipeline: ingest → score → rank."""
    session = SessionLocal()

    try:
        
        print("STEP 1 universe")
        universe = build_stock_universe()
        print("DONE universe", time.time()-t0)


        if universe is None or len(universe) == 0:
            return {"error": "Failed to fetch universe", "stocks": []}

        # Process all stocks in universe
        symbols_to_process = universe

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
            if price_count > 0 and not force:
                skipped += 1
                continue
            symbols_to_ingest.append(symbol)

        # Phase 3: Parallel ingestion
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

        
        print("STEP 2 loading stocks")
        all_stocks = session.query(Stock).all()
        print("DONE stocks load", time.time()-t0)

        print("STEP 3 ingesting financials")
        financial_ingestor = FinancialIngestor()
        shareholding_ingestor = ShareholdingIngestor()
        financial_count = 0
        # Ingest financials for all stocks that have price data
        stocks_with_prices = session.query(PriceHistory.symbol).distinct().all()
        stocks_with_prices = [s[0] for s in stocks_with_prices]
        print(f"Stocks with price data: {len(stocks_with_prices)}")
        for stock in all_stocks:
            if stock.symbol in stocks_with_prices:
                if financial_ingestor.fetch_quarterly(stock.symbol):
                    financial_count += 1
                if shareholding_ingestor.fetch_shareholding(stock.symbol):
                    pass
        print(f"DONE financials: {financial_count} stocks", time.time()-t0)

        scored_stocks = []
        eliminated_stocks = []

        for stock in all_stocks:
            data = get_stock_data_for_scoring(stock.symbol, session)
            if data:
                passed, stages = run_elimination_pipeline(stock.symbol, session, data)
                if passed:
                    score = alpha_score(data)
                    data['total_score'] = score
                    data['elimination_stages'] = stages
                    scored_stocks.append(data)
                else:
                    eliminated_stocks.append({
                        'symbol': stock.symbol,
                        'stages': stages
                    })

        ranked = sorted(
            scored_stocks,
            key=lambda x: x['total_score'],
            reverse=True
        )

        # Save scored stocks to database
        print(f"Saving {len(ranked)} scored stocks to database...")
        session.query(ScoredStock).delete()
        session.commit()

        for stock_data in ranked:
            scored_stock = ScoredStock(
                symbol=stock_data['symbol'],
                company_name=stock_data.get('company_name', ''),
                total_score=stock_data.get('total_score', 0),
                current_price=stock_data.get('current_price'),
                returns_6m=stock_data.get('returns_6m'),
                returns_1y=stock_data.get('returns_1y'),
                volume_ratio=stock_data.get('volume_ratio'),
                delivery_ratio=stock_data.get('delivery_ratio'),
                roce=stock_data.get('roce'),
                roe=stock_data.get('roe'),
                debt_equity=stock_data.get('debt_equity'),
                revenue_acceleration=stock_data.get('revenue_acceleration'),
                pat_acceleration=stock_data.get('pat_acceleration'),
                margin_expansion=stock_data.get('margin_expansion'),
                promoter_change=stock_data.get('promoter_change'),
                pledge_percent=stock_data.get('pledge_percent'),
                relative_strength=stock_data.get('relative_strength'),
                trend_strength=stock_data.get('trend_strength'),
                compression_pattern=stock_data.get('compression_pattern'),
                breakout_probability=stock_data.get('breakout_probability'),
                volume_confirmation=stock_data.get('volume_confirmation'),
                google_trend_score=stock_data.get('google_trend_score'),
                contract_score=stock_data.get('contract_score'),
                hiring_score=stock_data.get('hiring_score'),
                patent_score=stock_data.get('patent_score'),
                news_score=stock_data.get('news_score'),
                annual_report_score=stock_data.get('annual_report_score'),
                concall_score=stock_data.get('concall_score'),
                governance_score=stock_data.get('governance_score'),
                narrative_score=stock_data.get('narrative_score'),
                risk_score=stock_data.get('risk_score'),
                management_confidence=stock_data.get('management_confidence'),
                elimination_stages=','.join(stock_data.get('elimination_stages', []))
            )
            session.add(scored_stock)

        session.commit()
        print(f"Saved {len(ranked)} scored stocks to database")

        return {
            "status": "success",
            "processed": processed,
            "skipped": skipped,
            "passed_elimination": len(scored_stocks),
            "eliminated": len(eliminated_stocks),
            "ranked": ranked[:30],
            "eliminated_samples": eliminated_stocks[:10]
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline error: {e}")
        session.rollback()
        return {"error": str(e), "stocks": []}

    finally:
        session.close()
