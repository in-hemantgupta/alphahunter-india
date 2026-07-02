"""BSE scrip master - symbol <-> BSE code <-> ISIN mapping.

Phase 2 Task 4: this is the join key every other BSE ingestor (financials,
announcements, insider trading) needs to go from an NSE symbol to a BSE
scrip code. One bulk call covers BSE's whole active-equity universe (~4900
scrips) - no per-symbol lookups, no rate-limit pressure.
"""
from app.models.ticker_mapping import TickerMapping
from app.utils.http_resilience import resilient_get

SCRIP_MASTER_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/",
}
SOURCE_NAME = "bse_scrip_master"


def fetch_scrip_master() -> list[dict]:
    """Raises on failure - callers must not substitute fabricated rows."""
    params = {"Group": "", "Scripcode": "", "industry": "", "segment": "Equity", "status": "Active"}
    resp = resilient_get(SCRIP_MASTER_URL, SOURCE_NAME, headers=HEADERS, params=params,
                          timeout=30, max_retries=2)
    return resp.json()


def ingest_scrip_master(session) -> int:
    """Upserts symbol -> bse_code/isin. Matches BSE's scrip_id to the NSE
    symbol already used as primary key everywhere else in this schema -
    they use the same short ticker convention (verified: 'ABB', 'AEGISLOG')."""
    rows = fetch_scrip_master()
    updated = 0
    for row in rows:
        symbol = (row.get("scrip_id") or "").strip().upper()
        bse_code = row.get("SCRIP_CD")
        isin = row.get("ISIN_NUMBER")
        if not symbol or not bse_code:
            continue
        existing = session.query(TickerMapping).filter_by(symbol=symbol).first()
        if not existing:
            existing = TickerMapping(symbol=symbol)
            session.add(existing)
        existing.nse_symbol = symbol
        existing.bse_code = str(bse_code)
        existing.isin = isin
        updated += 1
    session.commit()
    return updated


def _demo():
    sample = [
        {"scrip_id": "abb", "SCRIP_CD": "500002", "ISIN_NUMBER": "INE117A01022"},
        {"scrip_id": "", "SCRIP_CD": "999999", "ISIN_NUMBER": "X"},  # no symbol, must skip
    ]
    seen = []
    for row in sample:
        symbol = (row.get("scrip_id") or "").strip().upper()
        if not symbol or not row.get("SCRIP_CD"):
            continue
        seen.append(symbol)
    assert seen == ["ABB"], seen
    print("bse_scrip_master._demo passed")


if __name__ == "__main__":
    _demo()
