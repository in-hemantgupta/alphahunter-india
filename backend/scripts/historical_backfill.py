"""Historical score snapshot backfill.
Loads all data into memory, reconstructs point-in-time state for each month-end,
scores entire universe, stores in score_snapshots table."""
import sys, os, json, math, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from datetime import datetime, date, timedelta
from collections import defaultdict
from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.quarterly import QuarterlyFinancials
from app.models.shareholding import ShareholdingPattern
from app.models.score_snapshot import ScoreSnapshot
from app.scoring.alpha_engine import get_score_breakdown
from app.scoring.ranker import PercentileRanker

t0 = time.time()
print("Loading all data into memory...")

# Load stocks
session = SessionLocal()
all_stocks = session.query(Stock).all()
stock_sectors = {s.symbol: s.sector or "Unknown" for s in all_stocks}
stock_mcaps = {s.symbol: s.market_cap for s in all_stocks}
print(f"Loaded {len(all_stocks)} stocks")

# Load all price history into memory: {symbol: [(date, close, high, low, vol), ...]}
all_prices_raw = session.query(
    PriceHistory.symbol, PriceHistory.date, PriceHistory.close,
    PriceHistory.high, PriceHistory.low, PriceHistory.volume
).order_by(PriceHistory.symbol, PriceHistory.date).all()
print(f"Loaded {len(all_prices_raw)} price records")

price_by_stock = defaultdict(list)
for sym, dt, close, high, low, vol in all_prices_raw:
    price_by_stock[sym].append((dt, close, high, low, vol))

# Load all quarterly data: {symbol: [(quarter, {fields...}), ...]}
all_quarterly = session.query(QuarterlyFinancials).order_by(
    QuarterlyFinancials.symbol, QuarterlyFinancials.quarter
).all()
q_by_stock = defaultdict(list)
for q in all_quarterly:
    q_by_stock[q.symbol].append((q.quarter, q))
print(f"Loaded {len(all_quarterly)} quarterly records")

# Load shareholding data
all_shareholding = session.query(ShareholdingPattern).order_by(
    ShareholdingPattern.symbol, ShareholdingPattern.quarter
).all()
sh_by_stock = defaultdict(list)
for s in all_shareholding:
    sh_by_stock[s.symbol].append((s.quarter, s))
print(f"Loaded {len(all_shareholding)} shareholding records")

# Load existing snapshots to avoid duplicates
existing_snapshots = set()
for r in session.query(ScoreSnapshot.date, ScoreSnapshot.symbol).all():
    existing_snapshots.add((r[0], r[1]))
print(f"Existing snapshot records: {len(existing_snapshots)}")

session.close()
print(f"Data loading: {time.time()-t0:.1f}s")


def quarter_available_date(quarter_label):
    """Estimate when quarterly data becomes publicly available.
    SEBI requires 45-day filing; we use ~45 days after quarter end."""
    parts = quarter_label.split("-Q")
    if len(parts) != 2:
        return None
    yr = int(parts[0])
    q = int(parts[1])
    if q == 1:
        return date(yr, 5, 15)  # Q1 ends Mar 31
    elif q == 2:
        return date(yr, 8, 15)  # Q2 ends Jun 30
    elif q == 3:
        return date(yr, 11, 15) # Q3 ends Sep 30
    elif q == 4:
        return date(yr + 1, 2, 15)  # Q4 ends Dec 31
    return None


def get_latest_quarter_as_of(as_of, q_records):
    """Get latest quarterly data available as of date."""
    latest = None
    for q_label, q_data in q_records:
        avail = quarter_available_date(q_label)
        if avail and avail <= as_of:
            if latest is None or q_label > latest[0]:
                latest = (q_label, q_data)
    return latest[1] if latest else None


def get_latest_shareholding_as_of(as_of, sh_records):
    """Get latest shareholding data available as of date.
    Shareholding is reported quarterly with ~1 month delay."""
    latest = None
    for sh_label, sh_data in sh_records:
        parts = sh_label.split("-Q")
        if len(parts) == 2:
            yr = int(parts[0])
            q = int(parts[1])
            if q == 4:
                avail = date(yr+1, 2, 1)
            else:
                avail = date(yr, (q-1)*3+4, 1)  # ~1 month after quarter end
            if avail <= as_of:
                if latest is None or sh_label > latest[0]:
                    latest = (sh_label, sh_data)
    return latest[1] if latest else None


def compute_returns(prices_subset, days):
    """Compute return over 'days' from most recent to 'days' ago."""
    if len(prices_subset) >= days + 1:
        latest = prices_subset[-1]
        past = prices_subset[-(days+1)]
        if past[1] > 0:
            return (latest[1] - past[1]) / past[1] * 100
    elif len(prices_subset) >= 2:
        latest = prices_subset[-1]
        past = prices_subset[0]
        if past[1] > 0:
            return (latest[1] - past[1]) / past[1] * 100
    return 0


def build_data_dict(symbol, prices, q_data, sh_data, as_of):
    """Build scoring data dict as of a point in time."""
    # Filter price data up to as_of
    prices_f = [(dt, c, h, lo, v) for dt, c, h, lo, v in prices if dt <= as_of]
    if not prices_f:
        return None

    closes = [p[1] for p in prices_f]
    highs = [p[2] for p in prices_f]
    lows = [p[3] for p in prices_f]
    vols = [p[4] for p in prices_f]
    current_price = closes[-1]

    n = len(closes)

    returns_6m = compute_returns(prices_f, 126)
    returns_1y = compute_returns(prices_f, 252)

    avg_vol = sum(vols[:30]) / min(30, len(vols)) if vols else 0
    curr_vol = vols[-1] if vols else 0
    volume_ratio = curr_vol / avg_vol if avg_vol > 0 else 1

    high_52w = max(highs) if highs else current_price

    # Recent returns (daily, last 20)
    recent_returns = []
    for i in range(min(20, n - 1)):
        if closes[-(i+1)] > 0:
            recent_returns.append((closes[-(i+1)] - closes[-(i+2)]) / closes[-(i+2)])
        else:
            recent_returns.append(0)

    # ATR-14
    tr_list = []
    for i in range(min(14, n - 1)):
        tr = max(highs[-(i+1)] - lows[-(i+1)],
                 abs(highs[-(i+1)] - closes[-(i+2)]),
                 abs(lows[-(i+1)] - closes[-(i+2)]))
        tr_list.append(tr)
    atr_14 = sum(tr_list) / len(tr_list) if tr_list else 1

    # VWAP (20 days)
    if n >= 20 and sum(vols[-20:]) > 0:
        vwap = sum(closes[-20+i] * vols[-20+i] for i in range(20)) / sum(vols[-20:])
    else:
        vwap = current_price

    volume_20d = sum(vols[:20]) / min(20, len(vols)) if vols else 1
    volume_90d = sum(vols[:90]) / min(90, len(vols)) if vols else 1
    delivery_ratio = 0.5  # approximate

    # Sector rotation (relative performance vs benchmark)
    # Approximate benchmark_return as average of all stock returns
    # Since we don't have Nifty data in this backfill, use 0
    benchmark_return = 0

    price_change = ((closes[-1] - closes[-2]) / closes[-2] * 100) if n > 1 else 0
    volume_spike = vols[-1] > (sum(vols[1:31]) / min(30, n-1)) * 2 if n > 1 else False

    # Quarterly data
    q = q_data
    if q:
        roce = q.roce
        roe = q.roe
        debt_equity = q.debt_equity
        revenue = q.revenue
        pat = q.pat
        ebitda = q.ebitda
        eps = q.eps
        operating_margin = q.operating_margin
        operating_profit = q.operating_profit
        cash_flow_operations = q.cash_flow_operations
        free_cash_flow = q.free_cash_flow
        debt = q.debt
        interest_expense = q.interest_expense
        inventory = q.inventory
        receivables = q.receivables
    else:
        roce = roe = debt_equity = revenue = pat = ebitda = eps = None
        operating_margin = operating_profit = None
        cash_flow_operations = free_cash_flow = None
        debt = interest_expense = inventory = receivables = None

    cash_conversion = None
    if cash_flow_operations is not None and pat is not None and pat > 0:
        cash_conversion = cash_flow_operations / pat if cash_flow_operations > 0 else 0

    cfo_negative_4q_count = 0
    if q and q.cash_flow_operations is not None and q.cash_flow_operations < 0:
        cfo_negative_4q_count = 1

    # Get 2nd latest quarter for comparisons
    # We already have the latest, need prev quarter
    # For simplicity, use q_data as is — prev quarter data isn't critical here

    # Shareholding
    promoter_change = None
    pledge_percent = None
    fii_change = None
    dii_change = None
    if sh_data:
        promoter_change = 0
        pledge_percent = sh_data.pledge or 0
        fii_change = 0
        dii_change = 0

    # Promoter declining / dilution
    promoter_declining = promoter_change is not None and promoter_change < -5
    dilution_rate = 0

    # Beta approximation (use 1.0 as default)
    beta = 1.0
    data_vol_60d = None
    if n > 60:
        close_arr = np.array(closes[-60:])
        daily_ret = np.diff(close_arr) / close_arr[:-1]
        data_vol_60d = float(np.std(daily_ret) * np.sqrt(252)) if len(daily_ret) > 0 else None

    # Seasonality
    seasonality = 0

    # Growth metrics (approximate from latest quarter, no prev quarter comp)
    revenue_acceleration = 0
    pat_acceleration = 0
    margin_expansion = 0
    cashflow_improvement = 0
    margin_stability = None
    capex_efficiency = None
    roce_trend = None
    fcf_trend = 0
    operating_cashflow = cash_flow_operations

    # Technical indicators
    relative_strength = 50 + returns_1y * 0.5 if returns_1y else 50
    trend_strength = 0
    compression_pattern = False
    breakout_probability = 0.3
    volume_confirmation = volume_ratio > 1.2
    vwap_defense = current_price >= vwap * 0.98 if vwap > 0 else False
    price_compression = False
    seller_exhaustion = returns_6m < -10 and volume_ratio < 0.7

    # Market cap
    market_cap = stock_mcaps.get(symbol)

    # PE ratio
    pe_ratio = None
    if eps is not None and eps > 0 and current_price > 0:
        pe_ratio = round(current_price / eps, 2)

    # Nifty 500 membership approx
    nifty_500_member = market_cap is not None and market_cap > 5000000000

    # LLM / alternative data defaults
    google_trend_score = 0
    contract_score = 0
    news_score = 0
    hiring_score = 0
    patent_score = 0
    shipment_score = 0

    data = {
        "symbol": symbol,
        "sector": stock_sectors.get(symbol, "Unknown"),
        "company_name": "",
        "market_cap": market_cap,
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
        "revenue": revenue,
        "pat": pat,
        "ebitda": ebitda,
        "cash_conversion_ratio": cash_conversion,
        "eps": eps,
        "operating_margin": operating_margin,
        "cash_flow_operations": cash_flow_operations,
        "free_cash_flow": free_cash_flow,
        "debt": debt,
        "interest_expense": interest_expense,
        "inventory": inventory,
        "receivables": receivables,
        "pe_ratio": pe_ratio,
        "pb_ratio": None,
        "ev_ebitda": None,
        "dividend_yield": None,
        "beta": beta,
        "rolling_volatility_60d": data_vol_60d,
        "seasonality": seasonality,
        "nifty_500_member": nifty_500_member,
        "governance_clean": True,
        "relative_strength": relative_strength,
        "delivery_20d_avg": sum(vols[:20]) / min(20, len(vols)) if vols else 0,
        "delivery_today": vols[-1] if vols else 0,
        "close": current_price,
        "vwap": vwap,
        "delivery_percent": 0,
        "price_change": price_change,
        "today_volume": vols[-1] if vols else 1,
        "avg_30d_volume": sum(vols[:30]) / min(30, len(vols)) if vols else 1,
        "atr_14": atr_14,
        "volume_spike": volume_spike,
        "recent_bulk_buy": volume_ratio > 3 and abs(price_change) < 1,
        "stock_return": returns_1y,
        "benchmark_return": benchmark_return,
        "high_52w": high_52w,
        "recent_returns": recent_returns,
        "volume_20d": volume_20d,
        "volume_90d": volume_90d,
        "price_series": closes[-60:] if n >= 60 else closes,
        "trend_strength": trend_strength,
        "compression_pattern": compression_pattern,
        "breakout_probability": breakout_probability,
        "volume_confirmation": volume_confirmation,
        "volume_high": volume_ratio > 1.5,
        "price_flat": abs(price_change) < 2.0,
        "vwap_defense": vwap_defense,
        "price_compression": price_compression,
        "seller_exhaustion": seller_exhaustion,
        "bulk_deal_positive": False,
        "promoter_declining": promoter_declining,
        "auditor_changed": False,
        "dilution_rate": dilution_rate,
        "cash_conversion": cash_conversion,
        "governance_red_flags": False,
        "google_trend_score": google_trend_score,
        "contract_score": contract_score,
        "shipment_score": shipment_score,
        "hiring_score": hiring_score,
        "patent_score": patent_score,
        "news_score": news_score,
        "annual_report_score": 0,
        "concall_score": 0,
        "governance_score": 0,
        "narrative_score": 0,
        "risk_score": 0,
        "management_confidence": 0,
        "sector_rotation": 50,
        "sentiment_score": 0,
        "governance_language": 0,
        "insider_trades": 0,
        "compensation_quality": 0,
        "operating_profit": operating_profit,
        "operating_profit_prev": None,
        "revenue_prev": None,
        "revenue_prev2": None,
        "pat_prev": None,
        "pat_prev2": None,
        "debt_equity_prev": None,
        "pat_4q_avg": None,
        "revenue_yoy": None,
        "avg_daily_value": (sum(vols[:30]) / min(30, len(vols))) * current_price if vols and current_price else None,
        "liquidity_score": None,
        "cfo_negative_4q_count": cfo_negative_4q_count,
    }
    return data


def generate_month_end_dates(start, end):
    """Generate last trading day of each month between start and end."""
    dates = []
    current = date(start.year, start.month, 1)
    while current <= end:
        # Last day of month
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        last_day = next_month - timedelta(days=1)
        dates.append(last_day)
        current = next_month
    return [d for d in dates if start <= d <= end]


# ============ MAIN BACKFILL LOOP ============
t_start = time.time()

month_ends = generate_month_end_dates(date(2018, 1, 1), date(2026, 6, 1))
print(f"\nBackfilling {len(month_ends)} months: {month_ends[0]} to {month_ends[-1]}")

for m_idx, as_of in enumerate(month_ends):
    t_m = time.time()
    print(f"\n[{m_idx+1}/{len(month_ends)}] Scoring as of {as_of}...")

    # Build data dicts for all stocks
    all_data = []
    skipped = 0
    for stock in all_stocks:
        prices = price_by_stock.get(stock.symbol, [])
        q_records = q_by_stock.get(stock.symbol, [])
        sh_records = sh_by_stock.get(stock.symbol, [])

        if not prices:
            skipped += 1
            continue

        q_data = get_latest_quarter_as_of(as_of, q_records)
        sh_data = get_latest_shareholding_as_of(as_of, sh_records)

        data = build_data_dict(stock.symbol, prices, q_data, sh_data, as_of)
        if data:
            all_data.append(data)
        else:
            skipped += 1

    print(f"  Built data dicts: {len(all_data)} stocks (skipped {skipped})")

    if len(all_data) < 100:
        print(f"  SKIP: too few stocks ({len(all_data)})")
        continue

    # Create ranker and score
    ranker = PercentileRanker(all_data)

    snapshots = []
    for data in all_data:
        breakdown = get_score_breakdown(data, ranker)
        layers = breakdown.get("layers", {})

        snap = {
            "date": as_of,
            "symbol": data["symbol"],
            "total_score": breakdown.get("total_score", 0),
            "quality_score": layers.get("quality", {}).get("score"),
            "growth_score": layers.get("growth", {}).get("score"),
            "technical_score": layers.get("technical", {}).get("score"),
            "microstructure_score": layers.get("microstructure", {}).get("score"),
            "value_score": layers.get("value", {}).get("score"),
            "management_score": layers.get("management", {}).get("score"),
            "lowvol_score": layers.get("lowvol", {}).get("score"),
            "forensic_score": layers.get("forensic", {}).get("score"),
            "confidence_score": breakdown.get("confidence", 0),
            "layer_breakdown_json": json.dumps(breakdown),
        }
        snapshots.append(snap)

    # Store in DB
    session = SessionLocal()
    try:
        inserted = 0
        for snap in snapshots:
            existing = session.query(ScoreSnapshot).filter_by(
                date=snap["date"], symbol=snap["symbol"]
            ).first()
            if existing:
                continue
            obj = ScoreSnapshot(**snap)
            session.add(obj)
            inserted += 1
        session.commit()
        print(f"  Inserted {inserted} new snapshot records")
    except Exception as e:
        print(f"  DB ERROR: {e}")
        session.rollback()
    finally:
        session.close()

    print(f"  Time: {time.time()-t_m:.1f}s")

# Print summary
t_total = time.time() - t_start
print(f"\n{'='*60}")
print(f"Backfill complete: {len(month_ends)} months in {t_total:.0f}s ({t_total/len(month_ends):.1f}s/month)")

# Verify
session = SessionLocal()
dates = [r[0] for r in session.query(ScoreSnapshot.date).distinct().order_by(ScoreSnapshot.date).all()]
counts = {}
for d in dates:
    cnt = session.query(ScoreSnapshot).filter(ScoreSnapshot.date == d).count()
    counts[d] = cnt
session.close()

print(f"Snapshots now available: {len(dates)}")
for d in sorted(dates):
    print(f"  {d}: {counts[d]} stocks")
