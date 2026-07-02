"""Extract structured financial fields from annual report PDF text using LLM.
Falls back gracefully if LLM is unavailable."""

import json
import re

FINANCIAL_FIELDS = [
    "total_assets", "cash_flow_operations", "depreciation", "capex",
    "receivables", "inventory", "employee_cost", "tax_expense", "cash_equivalents",
]

EXTRACTION_PROMPT = """You are a financial data extraction specialist. Extract the following fields from this annual report text. Return ONLY a JSON object with these exact keys. Use null for any field you cannot find. Do NOT include any other text.

Fields to extract:
- total_assets: Total Assets from the Balance Sheet (in crores)
- cash_flow_operations: Net Cash from Operating Activities (in crores)
- depreciation: Depreciation and Amortisation expense (in crores)
- capex: Capital Expenditure or Purchase of Fixed Assets (in crores)
- receivables: Trade Receivables or Sundry Debtors (in crores)
- inventory: Inventories or Stock in Trade (in crores)
- employee_cost: Employee Benefits Expense or Employee Cost (in crores)
- tax_expense: Tax Expense or Current Tax (in crores)
- cash_equivalents: Cash and Cash Equivalents or Cash & Bank (in crores)

Annual report text:
{text}

Return ONLY a valid JSON object:"""


async def extract_with_llm(pdf_text: str) -> dict | None:
    """Extract financial fields from annual report text using the LLM router.
    Returns dict with field values or None if extraction fails."""
    if not pdf_text or len(pdf_text.strip()) < 100:
        return None

    try:
        from app.llm_engine.llm_router import LLMRouter

        truncated = pdf_text[:15000]

        prompt = EXTRACTION_PROMPT.format(text=truncated)

        router = LLMRouter()
        response = await router.query(prompt)

        if not response or response in ("LLM not configured", "LLM unavailable"):
            return None

        json_str = response.strip()
        json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
        json_str = re.sub(r"\s*```$", "", json_str)
        json_str = json_str.strip()

        data = json.loads(json_str)

        result = {}
        for field in FINANCIAL_FIELDS:
            val = data.get(field)
            if val is not None:
                try:
                    result[field] = float(val)
                except (ValueError, TypeError):
                    result[field] = None
            else:
                result[field] = None

        return result

    except Exception:
        return None


async def fetch_bse_quarterly_llm(symbol: str) -> list[dict] | None:
    """Fetch quarterly financials via BSE annual report PDFs + LLM extraction.
    Returns list of quarterly records or None."""
    try:
        from app.ingestion.bse_pdf_parser import (
            get_bse_scripcode,
            fetch_annual_report_urls,
            download_and_extract_pdf,
        )

        scripcode = get_bse_scripcode(symbol)
        if not scripcode:
            return None

        reports = fetch_annual_report_urls(scripcode)
        if not reports:
            return None

        latest = [r for r in reports if r.get("year") and int(r["year"]) >= 2024]
        if not latest:
            latest = reports[:2]

        records = []
        seen = set()

        for report in latest:
            year = report.get("year")
            if year in seen:
                continue
            seen.add(year)

            pdf_text = download_and_extract_pdf(report.get("pdf_url", ""))
            if not pdf_text:
                continue

            fin = await extract_with_llm(pdf_text)
            if not fin or all(v is None for v in fin.values()):
                continue

            record = {"quarter": f"{year}-Q1"}
            record.update(fin)
            records.append(record)

        return records if records else None

    except Exception:
        return None
