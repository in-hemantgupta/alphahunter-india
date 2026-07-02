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
from app.models.score_snapshot import ScoreSnapshot
from app.scoring.alpha_engine import alpha_score, get_score_breakdown, batch_normalize_scores
from app.scoring.ranker import PercentileRanker
from app.ingestion.fetch_universe import build_stock_universe
from app.ingestion.financial_ingestor import FinancialIngestor
from app.ingestion.shareholding_ingestor import ShareholdingIngestor
from app.services.elimination import run_elimination_pipeline
from app.services.data_validation import validate_data_coverage, validate_score_distribution
from app.models.alternative_signals import AlternativeSignal
from app.models.llm_analysis import LLMAnalysis
import json
from app.services.data_freshness import DataFreshnessMonitor
from app.services.audit_logger import AuditLogger

_nifty_return_cache = None
_nifty_hist_cache = None


def _get_nifty_return():
    global _nifty_return_cache
    if _nifty_return_cache is not None:
        return _nifty_return_cache
    _nifty_return_cache = 0
    return 0


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
        if stock:
            if not stock.market_cap:
                mcap = info.get('marketCap')
                if mcap is not None and isinstance(mcap,(int,float)) and mcap > 0:
                    stock.market_cap = int(mcap)
            if not stock.sector or stock.sector == 'Unknown':
                sector = info.get('sector')
                if sector and str(sector).strip() not in ('', 'N/A', 'Unknown'):
                    stock.sector = str(sector).strip()

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

    roce = None
    roe = None
    debt_equity = None
    revenue_acceleration = None
    pat_acceleration = None
    margin_expansion = None
    cashflow_improvement = None
    operating_cashflow = None
    fcf_trend = None
    margin_stability = None

    if len(quarterly_data) >= 2:
        latest = quarterly_data[0]
        prev = quarterly_data[1]

        roce = latest.roce
        roe = latest.roe
        debt_equity = latest.debt_equity

        operating_cashflow = latest.cash_flow_operations or None

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
            margin_expansion = (margin_latest - margin_prev) * 100

        if len(quarterly_data) >= 4:
            margins = []
            for q in quarterly_data[:4]:
                if q.ebitda and q.revenue and q.revenue > 0:
                    margins.append((q.ebitda / q.revenue) * 100)
            if len(margins) >= 2:
                margin_stability = 100 - (max(margins) - min(margins))

        if len(quarterly_data) >= 2:
            cf_values = []
            for q in quarterly_data[:min(4, len(quarterly_data))]:
                cf = q.pat * 0.85 if q.pat else 0
                cf_values.append(cf)
            if len(cf_values) >= 2:
                if cf_values[0] > cf_values[-1]:
                    cashflow_improvement = ((cf_values[0] - cf_values[-1]) / max(abs(cf_values[-1]), 1)) * 100
                elif cf_values[0] > 0:
                    cashflow_improvement = 10

        if len(quarterly_data) >= 3:
            cf_trend_vals = []
            for q in quarterly_data[:min(4, len(quarterly_data))]:
                cf = q.pat * 0.85 if q.pat else 0
                cf_trend_vals.append(cf)
            if len(cf_trend_vals) >= 2:
                if cf_trend_vals[0] > cf_trend_vals[-1]:
                    fcf_trend = 1
                elif cf_trend_vals[0] == cf_trend_vals[-1] and cf_trend_vals[0] > 0:
                    fcf_trend = 0
                else:
                    fcf_trend = -1

    shareholding_data = session.query(ShareholdingPattern).filter_by(
        symbol=symbol
    ).order_by(ShareholdingPattern.quarter.desc()).limit(4).all()

    promoter_change = None
    pledge_percent = None
    fii_change = None
    dii_change = None

    if len(shareholding_data) >= 2:
        latest_sh = shareholding_data[0]
        prev_sh = shareholding_data[1]

        if latest_sh.promoter is not None and prev_sh.promoter is not None:
            promoter_change = latest_sh.promoter - prev_sh.promoter

        if latest_sh.fii is not None and prev_sh.fii is not None:
            fii_change = latest_sh.fii - prev_sh.fii

        if latest_sh.dii is not None and prev_sh.dii is not None:
            dii_change = latest_sh.dii - prev_sh.dii

        if latest_sh.pledge is not None:
            pledge_percent = latest_sh.pledge

    # CFO negative count: count quarters with negative operating cashflow
    cfo_negative_4q_count = 0
    for q in quarterly_data[:4]:
        if q.cash_flow_operations is not None and q.cash_flow_operations < 0:
            cfo_negative_4q_count += 1

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

    promoter_declining = promoter_change is not None and promoter_change < -5
    auditor_changed = False
    dilution_rate = 0
    cash_conversion = None
    latest_pat = quarterly_data[0].pat if quarterly_data and quarterly_data[0] and quarterly_data[0].pat is not None else None
    if operating_cashflow is not None and latest_pat is not None and latest_pat > 0:
        cash_conversion = operating_cashflow / latest_pat if operating_cashflow > 0 else 0
    governance_red_flags = False

    roce_trend = None
    if len(quarterly_data) >= 3:
        roce_values = [q.roce for q in quarterly_data[:3] if q.roce is not None]
        if len(roce_values) >= 2:
            roce_trend = roce_values[0] - roce_values[-1]

    capex_efficiency = None
    if len(quarterly_data) >= 2:
        latest = quarterly_data[0]
        prev = quarterly_data[1]
        if latest.revenue is not None and prev.revenue is not None and prev.revenue > 0:
            revenue_growth = ((latest.revenue - prev.revenue) / prev.revenue) * 100
            capex_efficiency = revenue_growth

    # Real data: read from AlternativeSignal cache table (populated by /enrich/google-trends)
    alt_cache = session.query(AlternativeSignal).filter_by(
        symbol=symbol, date=datetime.today().date()
    ).first()

    google_trend_score = alt_cache.google_trend_score if alt_cache and alt_cache.google_trend_score is not None else 0
    contract_score = alt_cache.contract_score if alt_cache and alt_cache.contract_score is not None else 0
    shipment_score = alt_cache.shipment_score if alt_cache and alt_cache.shipment_score is not None else 0
    hiring_score = alt_cache.hiring_score if alt_cache and alt_cache.hiring_score is not None else 0
    patent_score = alt_cache.patent_score if alt_cache and alt_cache.patent_score is not None else 0
    news_score = alt_cache.news_score if alt_cache and alt_cache.news_score is not None else 0

    # Real data: read from LLMAnalysis cache table (populated by /enrich/llm)
    llm_cache = session.query(LLMAnalysis).filter_by(
        symbol=symbol, date=datetime.today().date()
    ).first()

    annual_report_score = llm_cache.annual_score if llm_cache and llm_cache.annual_score is not None else 0
    concall_score = llm_cache.concall_score if llm_cache and llm_cache.concall_score is not None else 0
    narrative_score = llm_cache.narrative_score if llm_cache and llm_cache.narrative_score is not None else 0
    risk_score = llm_cache.risk_score if llm_cache and llm_cache.risk_score is not None else 0
    governance_score = llm_cache.governance_score if llm_cache and llm_cache.governance_score is not None else 0
    governance_language = governance_score  # same LLM output mapped for llm_score
    sentiment_score = llm_cache.sentiment_score if llm_cache and llm_cache.sentiment_score is not None else 0
    management_confidence = llm_cache.management_confidence if llm_cache and llm_cache.management_confidence is not None else 0

    # Sector rotation: relative outperformance vs benchmark (real derived metric)
    relative_perf = returns_1y - benchmark_return
    if relative_perf >= 30:
        sector_rotation = 95
    elif relative_perf >= 20:
        sector_rotation = 85
    elif relative_perf >= 10:
        sector_rotation = 70
    elif relative_perf >= 0:
        sector_rotation = 55
    elif relative_perf >= -10:
        sector_rotation = 40
    else:
        sector_rotation = 25

    # --- Computed fields for new factor layers ---
    revenue_prev = quarterly_data[1].revenue if quarterly_data and len(quarterly_data) > 1 else None
    revenue_prev2 = quarterly_data[2].revenue if quarterly_data and len(quarterly_data) > 2 else None
    pat_prev = quarterly_data[1].pat if quarterly_data and len(quarterly_data) > 1 else None
    pat_prev2 = quarterly_data[2].pat if quarterly_data and len(quarterly_data) > 2 else None
    op_profit = quarterly_data[0].operating_profit if quarterly_data and len(quarterly_data) > 0 else None
    op_profit_prev = quarterly_data[1].operating_profit if quarterly_data and len(quarterly_data) > 1 else None
    debt_equity_prev = quarterly_data[1].debt_equity if quarterly_data and len(quarterly_data) > 1 else None

    eps_val = quarterly_data[0].eps if quarterly_data and len(quarterly_data) > 0 else None

    pat_4q_vals = [q.pat for q in quarterly_data[:4] if q.pat is not None]
    pat_4q_avg = sum(pat_4q_vals) / len(pat_4q_vals) if pat_4q_vals else None

    pe_ratio = None
    if eps_val is not None and eps_val > 0 and current_price and current_price > 0:
        pe_ratio = round(current_price / eps_val, 2)

    data_vol_60d = None
    beta = None
    if len(closes) > 60:
        import numpy as np
        close_arr = np.array(closes[:252][::-1]) if len(closes) >= 252 else np.array(closes[::-1])
        if len(close_arr) > 60:
            daily_ret = np.diff(close_arr) / close_arr[:-1]
            data_vol_60d = np.std(daily_ret[-60:]) * np.sqrt(252) if len(daily_ret) >= 60 else None
            try:
                import yfinance as yf
                if _nifty_hist_cache is None:
                    _nifty_hist_cache = yf.Ticker("^NSEI").history(period="1y")
                nf_hist = _nifty_hist_cache
                if not nf_hist.empty:
                    nf_closes = nf_hist["Close"].values
                    min_len = min(len(close_arr), len(nf_closes))
                    if min_len > 20:
                        stock_ret = np.diff(close_arr[-min_len:]) / close_arr[-min_len:-1]
                        nifty_ret = np.diff(nf_closes[-min_len:]) / nf_closes[-min_len:-1]
                        if len(stock_ret) > 20 and np.std(nifty_ret) > 0:
                            beta = np.cov(stock_ret, nifty_ret)[0, 1] / np.var(nifty_ret)
                            beta = max(-2, min(3, beta))
            except:
                pass
        if beta is None:
            beta = 1.0

    # Keep management_confidence/sentiment_score/governance_language from LLM cache above
    insider_trades = 0
    compensation_quality = 0

    avg_daily_value = None
    if all_volumes and current_price:
        avg_daily_value = (sum(all_volumes[:30]) / min(30, len(all_volumes))) * current_price
    trading_days_pct = min(100, len(all_volumes) / 252 * 100) if all_volumes else 0
    liquidity_score = min(100, max(0, (avg_daily_value or 0) / 5_000_000 * 100)) if avg_daily_value else 0

    data = {
        "symbol": symbol,
        "sector": stock.sector or "Unknown",
        "company_name": stock.company_name or "",
        "market_cap": stock.market_cap,
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
        "fii_change": fii_change,
        "dii_change": dii_change,
        "pledge_percent": pledge_percent,
        "roce_trend": roce_trend,
        "capex_efficiency": capex_efficiency,
        "revenue": quarterly_data[0].revenue if quarterly_data and len(quarterly_data) > 0 else None,
        "pat": quarterly_data[0].pat if quarterly_data and len(quarterly_data) > 0 else None,
        "ebitda": quarterly_data[0].ebitda if quarterly_data and len(quarterly_data) > 0 else None,
        "cash_conversion_ratio": cash_conversion,
        "eps": quarterly_data[0].eps if quarterly_data and len(quarterly_data) > 0 else None,
        "operating_margin": quarterly_data[0].operating_margin if quarterly_data and len(quarterly_data) > 0 else None,
        "cash_flow_operations": quarterly_data[0].cash_flow_operations if quarterly_data and len(quarterly_data) > 0 else None,
        "free_cash_flow": quarterly_data[0].free_cash_flow if quarterly_data and len(quarterly_data) > 0 else None,
        "debt": quarterly_data[0].debt if quarterly_data and len(quarterly_data) > 0 else None,
        "interest_expense": quarterly_data[0].interest_expense if quarterly_data and len(quarterly_data) > 0 else None,
        "inventory": quarterly_data[0].inventory if quarterly_data and len(quarterly_data) > 0 else None,
        "receivables": quarterly_data[0].receivables if quarterly_data and len(quarterly_data) > 0 else None,
        "pe_ratio": pe_ratio,
        "pb_ratio": None,
        "ev_ebitda": None,
        "dividend_yield": None,
        "beta": beta,
        "rolling_volatility_60d": data_vol_60d,
        "seasonality": 0,
        "nifty_500_member": True,
        "governance_clean": True,
        "relative_strength": 50 + returns_1y * 0.5,
        "delivery_20d_avg": sum(all_volumes[:20]) / min(20, len(all_volumes)) if all_volumes else 0,
        "delivery_today": all_volumes[0] if all_volumes else 0,
        "close": current_price,
        "vwap": vwap,
        "delivery_percent": (all_volumes[0] - sum(all_volumes[1:21]) / min(20, len(all_volumes)-1)) / max(sum(all_volumes[1:21]) / min(20, len(all_volumes)-1), 1) * 100 if len(all_volumes) > 1 else 0,
        "price_change": price_change,
        "today_volume": all_volumes[0] if all_volumes else 1,
        "avg_30d_volume": sum(all_volumes[:30]) / min(30, len(all_volumes)) if all_volumes else 1,
        "atr_14": atr_14,
        "volume_spike": volume_spike,
        "recent_bulk_buy": volume_ratio > 3 and abs(price_change) < 1,
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
        "sector_rotation": sector_rotation,
        "sentiment_score": sentiment_score,
        "governance_language": governance_language,
        "insider_trades": insider_trades,
        "compensation_quality": compensation_quality,
        "operating_profit": quarterly_data[0].operating_profit if quarterly_data and len(quarterly_data) > 0 else None,
        "operating_profit_prev": op_profit_prev,
        "revenue_prev": revenue_prev,
        "revenue_prev2": revenue_prev2,
        "pat_prev": pat_prev,
        "pat_prev2": pat_prev2,
        "debt_equity_prev": debt_equity_prev,
        "pat_4q_avg": pat_4q_avg,
        "revenue_yoy": ((quarterly_data[0].revenue - revenue_prev) / abs(revenue_prev) * 100) if quarterly_data and len(quarterly_data) > 0 and quarterly_data[0].revenue is not None and revenue_prev is not None and revenue_prev != 0 else None,
        "cfo_negative_4q_count": cfo_negative_4q_count,
    }

    return data


def run_full_pipeline(force: bool = False):
    import time
    t0 = time.time()
    _audit = AuditLogger()
    _audit.log("pipeline_start", "scoring", "INFO", source="pipeline")
    print("PIPELINE START")

    # Data freshness check
    try:
        freshness = DataFreshnessMonitor()
        stale = freshness.get_stale_sources(48)
        if stale:
            print(f"[FRESHNESS] WARNING: Stale data sources: {[s['source_name'] for s in stale]}")
        freshness.close()
    except Exception as e:
        print(f"[FRESHNESS] Check failed (non-blocking): {e}")

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
        shareholding_count = 0
        # Ingest financials only for stocks that need them
        existing_financials = set(r[0] for r in session.query(QuarterlyFinancials.symbol).distinct().all())
        existing_shareholding = set(r[0] for r in session.query(ShareholdingPattern.symbol).distinct().all())
        stocks_with_prices = session.query(PriceHistory.symbol).distinct().all()
        stocks_with_prices = [s[0] for s in stocks_with_prices]
        print(f"Stocks with price data: {len(stocks_with_prices)}, need financials: {len(set(stocks_with_prices) - existing_financials)}, need shareholding: {len(set(stocks_with_prices) - existing_shareholding)}")
        for stock in all_stocks:
            if stock.symbol not in stocks_with_prices:
                continue
            if stock.symbol not in existing_financials:
                if financial_ingestor.fetch_quarterly(stock.symbol):
                    financial_count += 1
            if stock.symbol not in existing_shareholding:
                if shareholding_ingestor.fetch_shareholding(stock.symbol):
                    shareholding_count += 1
            if not stock.sector or stock.sector == 'Unknown':
                try:
                    ticker = yf.Ticker(f"{stock.symbol}.NS")
                    info = ticker.info or {}
                    sector = info.get('sector')
                    if sector and str(sector).strip() not in ('', 'N/A', 'Unknown'):
                        stock.sector = str(sector).strip()
                except:
                    pass
        session.commit()
        print(f"DONE financials: {financial_count} new, shareholding: {shareholding_count} new, time:", time.time()-t0)

        # Ingest corporate actions and insider trades
        try:
            from app.ingestion.corporate_actions import CorporateActionsIngestor
            ca_count = CorporateActionsIngestor().ingest_all()
            print(f"Corporate actions ingested: {ca_count} new")
        except Exception as e:
            print(f"Corporate actions ingestion skipped: {e}")

        try:
            from app.ingestion.insider_trades import InsiderTradesIngestor
            it_count = InsiderTradesIngestor().ingest_all()
            print(f"Insider trades ingested: {it_count} new")
        except Exception as e:
            print(f"Insider trades ingestion skipped: {e}")

        # Data coverage validation
        coverage = validate_data_coverage(session)
        print(f"Data coverage: {coverage['status']}")
        for field, info in coverage.get("fields", {}).items():
            if not info["ok"]:
                print(f"  WARNING: {field} only {info['covered_pct']}% covered (need >=70%)")
        if coverage["status"] == "fail":
            print("WARNING: Pipeline proceeding despite data coverage gaps")
            print("See field-level breakdown for details")

        print(f"Collecting data for all {len(all_stocks)} stocks...")
        all_data = []
        for stock in all_stocks:
            data = get_stock_data_for_scoring(stock.symbol, session)
            if data:
                all_data.append(data)

        ranker = PercentileRanker(all_data) if all_data else None
        print(f"Collected {len(all_data)} stock data records, computing percentile ranks")

        scored_stocks = []
        eliminated_stocks = []

        print(f"Scoring all {len(all_data)} stocks with percentile ranking...")
        for data in all_data:
            passed, stages = run_elimination_pipeline(data['symbol'], session, data)
            breakdown = get_score_breakdown(data, ranker)
            data['_breakdown'] = breakdown
            data['total_score'] = breakdown['total_score']
            data['composite'] = breakdown['composite']
            data['penalty'] = breakdown['penalty']
            data['penalty_detail'] = breakdown.get('penalty_detail', {})
            data['confidence_score'] = breakdown.get('confidence', 0)
            data['elimination_stages'] = stages
            data['passed_elimination'] = passed
            for layer_key, layer_info in breakdown['layers'].items():
                data[f'{layer_key}_score'] = layer_info['score']
            data['layer_breakdown_json'] = json.dumps(breakdown)
            scored_stocks.append(data)
            if not passed:
                eliminated_stocks.append({
                    'symbol': data['symbol'],
                    'stages': stages
                })

        print(f"Scored {len(scored_stocks)} stocks, {len(eliminated_stocks)} eliminated")

        # Apply cross-sectional z-score normalization to all layer scores
        print("Applying z-score normalization to layer scores...")
        batch_normalize_scores(scored_stocks)
        for sd in scored_stocks:
            sd['layer_breakdown_json'] = json.dumps(sd.get('_breakdown', {}))
        print("Z-score normalization complete")

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
                fundamental_score=stock_data.get('quality_score'),
                value_score=stock_data.get('value_score'),
                quality_score=stock_data.get('quality_score'),
                momentum_score=stock_data.get('momentum_score'),
                growth_score=stock_data.get('growth_score'),
                management_score=stock_data.get('management_score'),
                institutional_score=stock_data.get('microstructure_score'),
                microstructure_score=stock_data.get('microstructure_score'),
                forensic_score=stock_data.get('forensic_score'),
                lowvol_score=stock_data.get('lowvol_score'),
                alternative_score=stock_data.get('alternative_score'),
                macro_score=stock_data.get('macro_score'),
                technical_score=stock_data.get('technical_score'),
                llm_score=stock_data.get('llm_score'),
                confidence_score=stock_data.get('confidence_score'),
                layer_breakdown_json=stock_data.get('layer_breakdown_json'),
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
                elimination_stages=','.join(stock_data.get('elimination_stages', [])),
                passed_elimination=stock_data.get('passed_elimination', False)
            )
            session.add(scored_stock)

        session.commit()
        print(f"Saved {len(ranked)} scored stocks to database")

        # Insert score snapshot
        snapshot_date = datetime.today().date()
        for sd in ranked:
            snap = ScoreSnapshot(
                date=snapshot_date,
                symbol=sd['symbol'],
                total_score=sd.get('total_score'),
                quality_score=sd.get('quality_score'),
                growth_score=sd.get('growth_score'),
                technical_score=sd.get('technical_score'),
                microstructure_score=sd.get('microstructure_score'),
                management_score=sd.get('management_score'),
                forensic_score=sd.get('forensic_score'),
                lowvol_score=sd.get('lowvol_score'),
                value_score=sd.get('value_score'),
                confidence_score=sd.get('confidence_score'),
                layer_breakdown_json=sd.get('layer_breakdown_json'),
            )
            session.merge(snap)
        session.commit()
        print(f"Snapshot saved: {snapshot_date} ({len(ranked)} stocks)")

        # Data health monitor
        try:
            from app.services.data_health_monitor import DataHealthMonitor
            health = DataHealthMonitor.run(session)
            health.to_json("/tmp/data_health_report.json")
            print(f"\nData Health [{health.severity.upper()}]:")
            print(health.summary())
            if health.is_critical:
                print("CRITICAL: Data health issues block pipeline integrity")
        except Exception as e:
            print(f"Data health monitor skipped: {e}")

        # Record successful data fetch
        try:
            freshness = DataFreshnessMonitor()
            freshness.record_success("yfinance_prices")
            freshness.record_success("yfinance_financials")
            freshness.close()
        except Exception:
            pass

        _dur = int((time.time() - t0) * 1000)
        _audit.log_success("pipeline_complete", "scoring", details=f"{len(scored_stocks)} stocks scored", source="pipeline", duration_ms=_dur)
        _audit.close()
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
        _audit.log_failure("pipeline_error", "scoring", str(e), source="pipeline")
        _audit.close()
        print(f"Pipeline error: {e}")
        session.rollback()
        return {"error": str(e), "stocks": []}

    finally:
        session.close()
