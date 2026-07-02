#!/usr/bin/env python
"""Expand NSE→BSE scrip code mapping by searching BSE master data + API."""

import sys, os, re, json, time, httpx
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import SessionLocal
from app.models.stock import Stock
from sqlalchemy import func

BSE_API_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
}

# Load existing mapping
NSE_TO_BSE_PATH = os.path.join(os.path.dirname(__file__),
                               '../app/ingestion/bse_pdf_parser.py')


def fetch_bse_master():
    """Fetch the complete BSE scrip master."""
    resp = httpx.get(
        f"{BSE_API_BASE}/ListofScripData/w?segment=EQ&scripcode=&start=0&limit=10000",
        headers=BSE_HEADERS, timeout=60
    )
    return resp.json() if resp.status_code == 200 else []


def _normalize(s):
    """Normalize company names for comparison."""
    s = s.upper()
    s = re.sub(r'\b(LTD|LIMITED|PVT|PRIVATE|LT|INC|CORPORATION|CORP|CO|COMPANY|PLC|LLC)\b', '', s)
    s = re.sub(r'[^A-Z0-9 ]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def search_bse_by_name(master_data, company_name, symbol):
    """Find BSE scrip code by matching company name or symbol."""
    norm_name = _normalize(company_name)
    norm_words = set(norm_name.split())

    best_match = None
    best_score = 0

    for item in master_data:
        bse_name = _normalize(item.get('Scrip_Name', '') or '')
        bse_scrip_id = (item.get('scrip_id', '') or '').upper()
        status = item.get('Status', '')

        if status != 'Active':
            continue

        # Exact name match
        if bse_name == norm_name:
            best_match = item
            best_score = 100
            break

        # Symbol match (NSE symbol might match BSE scrip_id)
        if symbol.upper() == bse_scrip_id:
            if best_score < 90:
                best_match = item
                best_score = 90

        # Word overlap score
        bse_words = set(bse_name.split())
        if len(norm_words) > 1 and len(bse_words) > 1:
            overlap = len(norm_words & bse_words)
            if overlap >= max(2, len(norm_words) * 0.6):
                score = overlap / max(len(norm_words), len(bse_words)) * 50
                if score > best_score:
                    best_score = score
                    best_match = item

    if best_match:
        return best_match.get('SCRIP_CD')

    # Fallback: try BSE search API
    try:
        resp = httpx.get(
            f"{BSE_API_BASE}/PeerSmartSearch/w",
            params={"Type": "SS", "text": symbol},
            headers=BSE_HEADERS, timeout=10
        )
        if resp.status_code == 200:
            html = resp.text
            pattern = rf"<strong>{re.escape(symbol.upper())}</strong>.*?(\d{{6}})"
            m = re.search(pattern, html)
            if m:
                return m.group(1)
    except Exception:
        pass

    return None


def main():
    print("Fetching BSE master data...")
    master = fetch_bse_master()
    print(f"Loaded {len(master)} scrips")

    # Build active scrip index
    active = [s for s in master if s.get('Status') == 'Active']
    print(f"Active: {len(active)}")

    session = SessionLocal()
    stocks = session.query(Stock).all()
    session.close()
    print(f"NSE stocks: {len(stocks)}")

    # Load existing mapping
    from app.ingestion.bse_pdf_parser import NSE_TO_BSE
    existing = dict(NSE_TO_BSE)
    print(f"Existing mapped: {len(existing)}")

    # Find new mappings
    new_mappings = {}
    for s in stocks:
        if s.symbol in existing:
            continue
        scrip = search_bse_by_name(active, s.company_name, s.symbol)
        if scrip:
            new_mappings[s.symbol] = scrip

    print(f"New mappings found: {len(new_mappings)}")

    # Merge
    all_mappings = {**existing, **new_mappings}
    print(f"Total: {len(all_mappings)}")

    # Print some new ones
    for sym in sorted(new_mappings.keys())[:20]:
        print(f"  {sym}: {new_mappings[sym]}")

    # Save to JSON for later use
    json.dump(all_mappings, open('/tmp/nse_to_bse_expanded.json', 'w'), indent=2)
    print(f"\nSaved to /tmp/nse_to_bse_expanded.json")


if __name__ == "__main__":
    main()
