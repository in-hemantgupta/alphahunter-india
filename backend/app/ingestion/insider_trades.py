"""Insider trading data ingestion.

Sources (priority order):
1. SEBI Disclosures portal
2. BSE Announcements
3. NSE Corporate Announcements

Each source has its own circuit breaker flag.
"""

import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import Optional
from app.db.database import SessionLocal
from app.models.insider_trade import InsiderTrade


class InsiderTradesIngestor:
    _sebi_unreachable = False

    def ingest_all(self) -> int:
        total = 0
        total += self._from_bse_announcements()
        return total

    def _from_bse_announcements(self) -> int:
        """Scrape BSE announcements for insider trading disclosures."""
        try:
            url = "https://www.bseindia.com/corporates/announcements.aspx"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "text/html,application/xhtml+xml",
            }
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return 0

            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_gvAnnouncement"})
            if not table:
                table = soup.find("table", class_="mGrid")
            if not table:
                return 0

            records = []
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                try:
                    dt_str = cells[0].get_text(strip=True)
                    symbol = cells[1].get_text(strip=True).upper()
                    desc = cells[3].get_text(strip=True).lower()
                    if not symbol or not dt_str:
                        continue
                    if "insider" not in desc:
                        continue

                    trade_date = self._parse_date(dt_str)
                    if not trade_date:
                        continue

                    ttype = "buy" if any(w in desc for w in ["acquire", "purchase", "buy"]) else "sell"
                    rid = hashlib.md5(f"bse|it|{symbol}|{dt_str}|{desc}".encode()).hexdigest()[:16]

                    records.append({
                        "id": rid,
                        "symbol": symbol,
                        "date": trade_date,
                        "insider_name": self._extract_name(desc),
                        "transaction_type": ttype,
                        "quantity": self._extract_qty(desc),
                        "avg_price": None,
                        "insider_role": None,
                    })
                except Exception:
                    continue
            return self._save(records)
        except Exception as e:
            print(f"BSE insider scrape failed: {e}")
            return 0

    def _save(self, records: list) -> int:
        session = SessionLocal()
        try:
            new = 0
            for rec in records:
                exists = session.query(InsiderTrade).filter_by(id=rec["id"]).first()
                if not exists:
                    session.add(InsiderTrade(**rec))
                    new += 1
            session.commit()
            return new
        except Exception as e:
            session.rollback()
            print(f"Error saving insider trades: {e}")
            return 0
        finally:
            session.close()

    def _extract_name(self, desc: str) -> Optional[str]:
        import re
        m = re.search(r"(?:insider|promoter|director|kmp)\s+([a-z\s]+?)(?:\s+acquired|\s+sold|\s+exercised|\s+on|$)", desc, re.I)
        return m.group(1).strip().title() if m else None

    def _extract_qty(self, desc: str) -> Optional[int]:
        import re
        nums = re.findall(r"(\d[\d,]*)\s*(?:equity|shares|share)", desc, re.I)
        if nums:
            return int(nums[0].replace(",", ""))
        nums = re.findall(r"(\d[\d,]*)", desc)
        if nums:
            return int(nums[-1].replace(",", ""))
        return None

    def _parse_date(self, s: str) -> Optional[date]:
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
            try:
                return datetime.strptime(s.strip(), fmt).date()
            except ValueError:
                continue
        return None
