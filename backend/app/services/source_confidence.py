"""Phase 2 Task 5: central confidence registry, one number per data source.

Every ingestor stamps `source` (a key here) onto the row it writes; scoring
reads `confidence_for(source)` instead of each module inventing its own
number. Values are deliberately conservative for anything that isn't a
direct regulatory filing - Rule 1: an unknown/unlisted source must not
default to full trust.
"""

SOURCE_CONFIDENCE = {
    # Direct regulatory/exchange filings - highest trust
    "nse_shareholding_filing": 0.98,
    "nse_bhavcopy": 0.98,
    "nse_corp_announcements": 0.97,
    "bse_corp_filing": 0.95,
    "bse_pdf_parser": 0.85,          # PDF text-extraction, not structured filing
    "sebi_pit_disclosure": 0.97,
    # Third-party aggregators (re-publish filings, occasional lag/typos)
    "screener_in": 0.90,
    # Market data vendor, reliable for prices but not a primary filing
    "yfinance_prices": 0.90,
    "yfinance_financials": 0.75,
    # Derived/inferred, not sourced from a single filing
    "pdf_ocr": 0.80,
    "llm_extraction": 0.70,
    "regex_scrape": 0.65,             # e.g. announcement-text pattern matching
}

DEFAULT_CONFIDENCE = 0.60  # unregistered source: conservative, not full trust


def confidence_for(source: str) -> float:
    if not source:
        return DEFAULT_CONFIDENCE
    return SOURCE_CONFIDENCE.get(source, DEFAULT_CONFIDENCE)


def _demo():
    assert confidence_for("nse_shareholding_filing") == 0.98
    assert confidence_for("llm_extraction") == 0.70
    assert confidence_for("some_unregistered_source") == DEFAULT_CONFIDENCE
    assert confidence_for(None) == DEFAULT_CONFIDENCE
    print("source_confidence._demo passed")


if __name__ == "__main__":
    _demo()
