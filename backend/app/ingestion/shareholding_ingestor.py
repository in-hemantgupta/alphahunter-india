"""Rule 1: never fake data. The previous version derived promoter/FII/DII
percentages from yfinance's `major_holders`/`institutional_holders` tables
via string-matching on holder names (a heuristic, not a shareholding filing)
and hardcoded pledge_pct = 0 unconditionally - i.e. every stock in the
universe was reported as having zero promoter pledge regardless of reality.
Both are deleted, not patched.

The real source is NSE's corporate-shareholding-pattern filings. That
endpoint is Akamai-protected and returned HTTP 403 to every request attempted
from this environment during the rebuild (see
docs/INSTITUTIONAL_REBUILD_PLAN.md Phase 2A) - a JS bot challenge, not a
credentials/auth problem, so there's no header combination that fixes it from
a plain scripted client. The request/retry/circuit-breaker plumbing below is
real and does get exercised end-to-end; only the response parser is stubbed,
because guessing NSE's current JSON field names without ever having seen a
real 200 response would risk silently writing wrong numbers that *look*
successful - exactly the failure mode Rule 3 exists to prevent. Capture one
real response (browser session, proxy, or paid vendor feed) and fill in
_parse_nse_response before this can write real rows.
"""
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models.shareholding import ShareholdingPattern
from app.utils.http_resilience import resilient_get, CircuitOpenError
from app.services.source_confidence import confidence_for

NSE_SHAREHOLDING_URL = "https://www.nseindia.com/api/corporate-shareholding-pattern"
SOURCE_NAME = "nse_shareholding_filing"

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern",
}


class ShareholdingIngestor:

    def _current_quarter(self) -> str:
        now = datetime.now(timezone.utc)
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"

    def _parse_nse_response(self, payload: dict) -> dict | None:
        """Not implemented: NSE's live JSON schema has never been observed
        from this environment (every request 403'd). Raising rather than
        guessing a field mapping - see module docstring."""
        raise NotImplementedError(
            "NSE shareholding-pattern response schema unverified - capture a real "
            "200 response before implementing this parser (Rule 1: no guessed data)."
        )

    def fetch_shareholding(self, symbol: str) -> bool:
        """Attempt a real NSE shareholding-pattern fetch. Returns False (and
        writes nothing) on any failure - callers must not treat False as
        'zero pledge' or 'zero promoter change', only as 'no data available
        this run'."""
        try:
            resp = resilient_get(
                NSE_SHAREHOLDING_URL,
                source_name=SOURCE_NAME,
                headers=_NSE_HEADERS,
                params={"index": "equities", "symbol": symbol},
            )
        except CircuitOpenError as e:
            print(f"[shareholding] {symbol}: {e}")
            return False
        except Exception as e:
            print(f"[shareholding] {symbol}: fetch failed: {e}")
            return False

        try:
            parsed = self._parse_nse_response(resp.json())
        except Exception as e:
            print(f"[shareholding] {symbol}: parse failed, discarding response: {e}")
            return False

        if parsed is None:
            return False

        session = SessionLocal()
        try:
            quarter_str = self._current_quarter()
            record = session.query(ShareholdingPattern).filter_by(
                symbol=symbol, quarter=quarter_str,
            ).first()
            if not record:
                record = ShareholdingPattern(symbol=symbol, quarter=quarter_str)
                session.add(record)

            record.promoter = parsed.get("promoter_pct")
            record.fii = parsed.get("fii_pct")
            record.dii = parsed.get("dii_pct")
            record.pledge = parsed.get("pledge_pct")
            record.source = SOURCE_NAME
            record.confidence = confidence_for(SOURCE_NAME)
            record.filing_date = parsed.get("filing_date")
            record.fetched_at = datetime.now(timezone.utc)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"[shareholding] {symbol}: DB write failed: {e}")
            return False
        finally:
            session.close()
