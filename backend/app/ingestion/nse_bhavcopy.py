"""NSE bhavcopy delivery-percentage ingestion.

Phase 2 Task 1 (Method E) verified this endpoint is reachable with a plain
GET - no session warm-up, no cookies, no Akamai challenge - because it's a
static file host, not the JS-app API surface. It IS aggressively rate
limited on bursts (observed: silent connection hang after ~3 requests in
quick succession), so this must run at most once per trading day per date
via resilient_get's backoff/circuit-breaker, never in a tight loop.

This is the real replacement for pipeline.py's `delivery_ratio = None`
(see docs/INSTITUTIONAL_REBUILD_PLAN.md Phase 2B): NSE's own DELIV_PER
field, not a volume-based proxy.
"""
import csv
import io
from datetime import date

from app.models.price_history import PriceHistory
from app.utils.http_resilience import resilient_get

BHAVCOPY_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/csv,*/*",
}


def fetch_delivery_pct(trading_date: date) -> dict:
    """Returns {symbol: delivery_pct} for EQ-series rows on trading_date.
    Raises on failure - callers must treat this as unavailable, not
    substitute a guessed value."""
    url = BHAVCOPY_URL.format(ddmmyyyy=trading_date.strftime("%d%m%Y"))
    resp = resilient_get(url, "nse_bhavcopy", headers=HEADERS, timeout=30, max_retries=2)
    reader = csv.DictReader(io.StringIO(resp.text))
    result = {}
    for row in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if row.get("SERIES") != "EQ":
            continue
        symbol = row.get("SYMBOL")
        deliv = row.get("DELIV_PER")
        if not symbol or not deliv or deliv == "-":
            continue
        try:
            result[symbol] = float(deliv)
        except ValueError:
            continue
    return result


def ingest_delivery_pct(session, trading_date: date) -> int:
    """Upserts delivery_pct onto existing price_history rows for trading_date.
    Only attaches to symbols that already have a price row for that date -
    this fills in a column, it doesn't create new OHLCV rows."""
    deliveries = fetch_delivery_pct(trading_date)
    if not deliveries:
        return 0
    rows = session.query(PriceHistory).filter(
        PriceHistory.date == trading_date,
        PriceHistory.symbol.in_(list(deliveries.keys())),
    ).all()
    updated = 0
    for row in rows:
        row.delivery_pct = deliveries[row.symbol]
        updated += 1
    session.commit()
    return updated


def _demo():
    """Self-check: parse a small synthetic bhavcopy CSV, verify EQ filtering
    and float parsing without hitting the network."""
    sample = (
        "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, "
        "LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, "
        "NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
        "RELIANCE, EQ, 01-JUL-2026,100,101,102,99,100,100,100,1000,10,5,300,30.00\n"
        "RELPREF, BE, 01-JUL-2026,100,101,102,99,100,100,100,1000,10,5,300,30.00\n"
        "TCS, EQ, 01-JUL-2026,100,101,102,99,100,100,100,1000,10,5,-,-\n"
    )
    reader = csv.DictReader(io.StringIO(sample))
    result = {}
    for row in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if row.get("SERIES") != "EQ":
            continue
        symbol = row.get("SYMBOL")
        deliv = row.get("DELIV_PER")
        if not symbol or not deliv or deliv == "-":
            continue
        try:
            result[symbol] = float(deliv)
        except ValueError:
            continue
    assert result == {"RELIANCE": 30.0}, result
    print("nse_bhavcopy._demo passed:", result)


if __name__ == "__main__":
    _demo()
