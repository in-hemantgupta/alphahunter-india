"""BSE corporate filings fallback for financial data ingestion.
Extracts quarterly financials from BSE annual report PDFs.
Lowest priority in the fallback chain (Screener > yfinance/NSE > BSE).

Pipeline:
  1. Map NSE symbol -> BSE scrip code
  2. Fetch annual report PDF URLs from BSE API
  3. Download and extract PDF text (PyMuPDF)
  4. Parse financial fields via regex
  5. Fallback to LLM extraction if regex yields low coverage
"""

import asyncio


def fetch_bse_quarterly(symbol: str, use_llm: bool = False) -> list[dict] | None:
    """Fetch quarterly financial data from BSE annual report PDFs.

    Args:
        symbol: NSE symbol (e.g. 'RELIANCE')
        use_llm: If True, use LLM extraction as fallback when regex yields <3 fields

    Returns:
        List of dicts matching QuarterlyFinancials schema, or None.
    """
    try:
        from app.ingestion.bse_pdf_parser import fetch_bse_quarterly as _parse

        records = _parse(symbol)
        if records:
            populated = sum(
                1 for r in records for v in r.values() if v is not None
            )
            if populated >= 3 or not use_llm:
                return records

        if use_llm:
            try:
                from app.llm_engine.annual_report_extractor import (
                    fetch_bse_quarterly_llm,
                )
                llm_records = asyncio.run(fetch_bse_quarterly_llm(symbol))
                if llm_records:
                    return llm_records
            except Exception:
                pass

        return records

    except Exception:
        return None
