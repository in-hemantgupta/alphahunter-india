"""BSE corporate announcements - verified real endpoint (Phase 2 Task 2).

api.bseindia.com's AnnSubCategoryGetData feed covers board meetings,
results, AGM/EGM, insider trading/SAST, and general company updates,
filterable by BSE scrip code. Requires app/ingestion/bse_scrip_master.py
to have already populated the symbol -> bse_code mapping used to resolve
the scrip code for a given NSE symbol.
"""
from datetime import datetime

from app.models.corporate_filings import CorporateFiling
from app.models.ticker_mapping import TickerMapping
from app.utils.http_resilience import resilient_get

ANNOUNCEMENTS_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/",
}
SOURCE_NAME = "bse_corp_announcements"


def fetch_announcements(bse_code: str, category: str = "-1", from_date: str = "", to_date: str = "") -> list[dict]:
    """category="-1" (BSE's own "All" value, confirmed via live testing) or
    a real CATEGORYNAME string ("Company Update", "Insider Trading / SAST",
    "Board Meeting", ...). Raises on failure - no fabricated fallback."""
    params = {
        "strCat": category, "strPrevDate": from_date, "strScrip": bse_code,
        "strSearch": "P", "strToDate": to_date, "strType": "C",
    }
    resp = resilient_get(ANNOUNCEMENTS_URL, SOURCE_NAME, headers=HEADERS, params=params,
                          timeout=20, max_retries=2)
    return resp.json().get("Table") or []


def ingest_announcements(session, symbol: str, category: str = "-1") -> int:
    mapping = session.query(TickerMapping).filter_by(symbol=symbol).first()
    if not mapping or not mapping.bse_code:
        return 0
    rows = fetch_announcements(mapping.bse_code, category=category)
    new = 0
    for row in rows:
        news_id = row.get("NEWSID")
        dt_str = row.get("NEWS_DT") or row.get("DT_TM")
        if not news_id or not dt_str:
            continue
        existing = session.query(CorporateFiling).filter_by(id=news_id).first()
        if existing:
            continue
        try:
            filing_date = datetime.fromisoformat(dt_str).date()
        except ValueError:
            continue
        session.add(CorporateFiling(
            id=news_id,
            symbol=symbol,
            date=filing_date,
            announcement_type=row.get("CATEGORYNAME"),
            text=row.get("HEADLINE") or row.get("NEWSSUB"),
        ))
        new += 1
    session.commit()
    return new


def _demo():
    sample_row = {
        "NEWSID": "b4c787ec-3949-4737-a1db-8fe2f44ca3e6", "NEWS_DT": "2026-06-24T16:10:40.66",
        "CATEGORYNAME": "Company Update", "HEADLINE": "Media Release",
    }
    filing_date = datetime.fromisoformat(sample_row["NEWS_DT"]).date()
    assert str(filing_date) == "2026-06-24"
    print("bse_announcements._demo passed")


if __name__ == "__main__":
    _demo()
