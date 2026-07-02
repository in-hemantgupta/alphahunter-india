"""Corporate actions ingestion.

Sources (priority order):
1. BSE Corporate Actions page
2. NSE Corporate Announcements
3. Manual override API

Each source has its own circuit breaker flag to prevent repeated failures.
"""

import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import Optional
from sqlalchemy import func as sa_func
from app.db.database import SessionLocal
from app.models.corporate_action import CorporateAction

BSE_CA_URL = "https://www.bseindia.com/corporates/announcements.aspx"


class CorporateActionsIngestor:
    _bse_unreachable = False

    def ingest_all(self) -> int:
        """Run full ingestion cycle. Returns count of new records."""
        total = 0
        total += self._from_bse()
        return total

    def _from_bse(self) -> int:
        """Scrape BSE Corporate Actions page for latest announcements."""
        if CorporateActionsIngestor._bse_unreachable:
            return 0
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "text/html,application/xhtml+xml",
            }
            resp = requests.get(BSE_CA_URL, headers=headers, timeout=15)
            if resp.status_code != 200:
                CorporateActionsIngestor._bse_unreachable = True
                return 0

            soup = BeautifulSoup(resp.text, "lxml")
            records = []
            table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_gvAnnouncement"})
            if not table:
                table = soup.find("table", class_="mGrid")
            if not table:
                return 0

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

                    action_date = self._parse_date(dt_str)
                    if not action_date:
                        continue

                    action_type = self._classify(desc)
                    if not action_type:
                        continue

                    rid = hashlib.md5(f"{symbol}{dt_str}{desc}".encode()).hexdigest()[:16]
                    records.append({
                        "id": rid,
                        "symbol": symbol,
                        "date": action_date,
                        "action_type": action_type,
                        "dividend": self._extract_dividend(desc, action_type),
                        "split_ratio": self._extract_split(desc),
                        "bonus_ratio": self._extract_bonus(desc),
                        "buyback_size": None,
                        "rights_issue": None,
                    })
                except Exception:
                    continue
            return self._save(records)
        except Exception as e:
            print(f"BSE corporate actions scrape failed: {e}")
            CorporateActionsIngestor._bse_unreachable = True
            return 0

    def _save(self, records: list) -> int:
        session = SessionLocal()
        try:
            new = 0
            for rec in records:
                exists = session.query(CorporateAction).filter_by(id=rec["id"]).first()
                if not exists:
                    session.add(CorporateAction(**rec))
                    new += 1
            session.commit()
            return new
        except Exception as e:
            session.rollback()
            print(f"Error saving corporate actions: {e}")
            return 0
        finally:
            session.close()

    def _classify(self, desc: str) -> Optional[str]:
        desc_lower = desc.lower()
        if "dividend" in desc_lower:
            return "dividend"
        if "split" in desc_lower or "stock split" in desc_lower:
            return "split"
        if "bonus" in desc_lower:
            return "bonus"
        if "buyback" in desc_lower:
            return "buyback"
        if "rights" in desc_lower:
            return "rights_issue"
        return None

    def _extract_dividend(self, desc: str, action_type: str) -> Optional[float]:
        if action_type != "dividend":
            return None
        import re
        nums = re.findall(r"(\d+(?:\.\d+)?)", desc.replace(",", ""))
        if nums:
            return float(nums[-1])
        return None

    def _extract_split(self, desc: str) -> Optional[str]:
        import re
        m = re.search(r"(\d+)\s*:\s*(\d+)", desc)
        return m.group(0) if m else None

    def _extract_bonus(self, desc: str) -> Optional[str]:
        import re
        m = re.search(r"(\d+)\s*:\s*(\d+)", desc)
        return m.group(0) if m else None

    def _parse_date(self, s: str) -> Optional[date]:
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
            try:
                return datetime.strptime(s.strip(), fmt).date()
            except ValueError:
                continue
        return None
