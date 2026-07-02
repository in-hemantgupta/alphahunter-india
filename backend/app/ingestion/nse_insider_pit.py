"""SEBI PIT (Prohibition of Insider Trading) Regulation 7(2) disclosures.

Phase 2 Task 3: verified real endpoint. SEBI itself doesn't run a
symbol-queryable PIT database - insiders file Regulation 7(2) disclosures
with the exchange, which publishes them. NSE's `corporates-pit` API
(distinct from the 404ing `corporate-pit` singular - confirmed by direct
testing, not guessed) returns the whole market's disclosures for a date
range in one call: promoter/director/KMP buys and sells, with XBRL source
links for full audit trail.

Requires the same session warm-up as other NSE JSON endpoints (Phase 2
Task 1 Method A) - the homepage 403s but still sets the AKA_A2 cookie
needed by the API.
"""
import hashlib
import time
from datetime import date, datetime, timedelta

import requests

from app.models.insider_trade import InsiderTrade
from app.utils.http_resilience import resilient_get

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}
PIT_URL = "https://www.nseindia.com/api/corporates-pit"
SOURCE_NAME = "sebi_pit_disclosure"


def _warmed_cookies() -> dict:
    """One throwaway GET to collect the Akamai cookie the API needs.
    The homepage itself returns 403 - that's expected, the cookie is set
    on the response regardless."""
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    s.get("https://www.nseindia.com/", timeout=15)
    return dict(s.cookies)


def fetch_pit_disclosures(from_date: date, to_date: date) -> list[dict]:
    """Raises on failure - callers must not substitute fabricated rows."""
    cookies = _warmed_cookies()
    time.sleep(1)
    headers = dict(BASE_HEADERS)
    headers["Accept"] = "application/json"
    headers["Referer"] = "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"
    params = {
        "index": "equities",
        "from_date": from_date.strftime("%d-%m-%Y"),
        "to_date": to_date.strftime("%d-%m-%Y"),
    }
    resp = resilient_get(PIT_URL, SOURCE_NAME, headers=headers, params=params,
                          cookies=cookies, timeout=30, max_retries=2)
    return resp.json().get("data", [])


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_row(row: dict) -> dict | None:
    symbol = row.get("symbol")
    intim_dt = row.get("intimDt")
    if not symbol or not intim_dt:
        return None
    try:
        trade_date = datetime.strptime(intim_dt, "%d-%b-%Y").date()
    except ValueError:
        return None

    txn_type = (row.get("tdpTransactionType") or "").strip().lower()
    qty = _to_float(row.get("secAcq"))
    value = _to_float(row.get("secVal"))
    avg_price = (value / qty) if (value is not None and qty) else None
    row_id_src = f"{row.get('pid')}|{row.get('did')}|{symbol}|{intim_dt}"

    return {
        "id": hashlib.md5(row_id_src.encode()).hexdigest()[:16],
        "symbol": symbol,
        "date": trade_date,
        "insider_name": row.get("acqName"),
        "transaction_type": "buy" if "buy" in txn_type else ("sell" if "sell" in txn_type else txn_type or None),
        "quantity": int(qty) if qty is not None else None,
        "avg_price": avg_price,
        "value": value,
        "insider_role": row.get("personCategory"),
        "source": SOURCE_NAME,
    }


def ingest_pit_disclosures(session, from_date: date = None, to_date: date = None) -> int:
    from app.services.source_confidence import confidence_for
    to_date = to_date or date.today()
    from_date = from_date or (to_date - timedelta(days=30))
    raw_rows = fetch_pit_disclosures(from_date, to_date)

    new = 0
    for raw in raw_rows:
        parsed = _parse_row(raw)
        if not parsed:
            continue
        exists = session.query(InsiderTrade).filter_by(id=parsed["id"]).first()
        if exists:
            continue
        parsed["confidence"] = confidence_for(SOURCE_NAME)
        session.add(InsiderTrade(**parsed))
        new += 1
    session.commit()
    return new


def _demo():
    """Self-check: parse two real-shaped rows (captured from a live response
    during Phase 2 Task 3 testing) without hitting the network."""
    sample_buy = {
        "acqName": "Shantanu Lath", "intimDt": "02-May-2026", "symbol": "RELTD",
        "personCategory": "Director", "tdpTransactionType": "Buy",
        "secAcq": "70000", "secVal": "7000000", "pid": "1197873", "did": "570637",
    }
    sample_sell = {
        "acqName": "Vama Sundari Investments (Delhi) Private Limited",
        "intimDt": "30-Apr-2026", "symbol": "HCLTECH", "personCategory": "Promoters",
        "tdpTransactionType": "Sell", "secAcq": "183673", "secVal": "220277165",
        "pid": "1197864", "did": "570626",
    }
    p1 = _parse_row(sample_buy)
    p2 = _parse_row(sample_sell)
    assert p1["symbol"] == "RELTD" and p1["transaction_type"] == "buy" and p1["quantity"] == 70000
    assert p2["avg_price"] == 220277165 / 183673
    assert p2["insider_role"] == "Promoters"
    print("nse_insider_pit._demo passed:", p1["id"], p2["id"])


if __name__ == "__main__":
    _demo()
