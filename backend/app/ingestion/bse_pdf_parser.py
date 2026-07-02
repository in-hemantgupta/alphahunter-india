"""BSE annual report PDF scraper for Indian stocks.
Extracts financial fields from BSE annual report PDFs via the BSE API.
Fallback chain: Screener.in -> NSE/yfinance -> BSE."""

import re
import io
import json
import os
import httpx

BSE_API_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
}

_EXPANDED_MAP_PATH = os.path.join(os.path.dirname(__file__), "../../scripts/nse_to_bse_expanded.json")


def _load_bse_mappings():
    """Load expanded NSE→BSE mapping from JSON if available."""
    try:
        with open(_EXPANDED_MAP_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


NSE_TO_BSE = {
    "RELIANCE": "500325", "TCS": "532540", "INFY": "500209",
    "HDFCBANK": "500180", "ICICIBANK": "532174", "KOTAKBANK": "500247",
    "SBIN": "500112", "BHARTIARTL": "532454", "ITC": "500875",
    "WIPRO": "507685", "HINDUNILVR": "500696", "LT": "500510",
    "MARUTI": "532500", "TATAMOTORS": "500570", "TATASTEEL": "500470",
    "JSWSTEEL": "500228", "SUNPHARMA": "524715", "BAJFINANCE": "500034",
    "BAJAJFINSV": "500032", "HCLTECH": "532281", "AXISBANK": "532215",
    "ULTRACEMCO": "532538", "NTPC": "532555", "ONGC": "500312",
    "POWERGRID": "532898", "M&M": "500520", "TITAN": "500114",
    "ASIANPAINT": "500820", "NESTLEIND": "500790", "COALINDIA": "533278",
    "ADANIPORTS": "532921", "ADANIENT": "512599", "HINDALCO": "500440",
    "EICHERMOT": "505200", "BAJAJ-AUTO": "532977", "HEROMOTOCO": "500182",
    "DIVISLAB": "532488", "DRREDDY": "500124", "CIPLA": "500087",
    "GRASIM": "500300", "BRITANNIA": "500825", "SHREECEM": "530066",
    "TECHM": "532755", "SBILIFE": "541719", "ICICIPRULI": "540019",
    "ICICIGI": "540716", "HDFCLIFE": "540777", "HDFCAMC": "541729",
    "MUTHOOTFIN": "533169", "PEL": "500302", "PIDILITIND": "500331",
    "VOLTAS": "500238", "HAVELLS": "517354", "DABUR": "500096",
    "MARICO": "531642", "BERGEPAINT": "500266", "TORNTPHARM": "500420",
    "AUROPHARMA": "500289", "SRTRANSFIN": "532705", "PAGEIND": "532747",
    "COLPAL": "500830", "AMBUJACEM": "500425", "BANDHANBNK": "541153",
    "IOC": "530965", "BPCL": "500547", "HINDPETRO": "500104",
    "GAIL": "532155", "LICHSGFIN": "533387", "CHOLAFIN": "532343",
    "NAUKRI": "532522", "INDUSINDBK": "532187", "FEDERALBNK": "500469",
    "IDEA": "532822", "ZOMATO": "543320", "PAYTM": "543396",
    "POLICYBZR": "543397", "VEDL": "500295", "TATACONSUM": "500800",
    "DMART": "540376", "BIOCON": "532523", "ABBOTINDIA": "500488",
    "GLENMARK": "532296", "CADILAHC": "532321", "MCDOWELL-N": "532651",
    "TRENT": "500251", "ALKEM": "539523", "LUPIN": "500257",
    "APOLLOHOSP": "508869", "MANAPPURAM": "531213", "TVSMOTOR": "532343",
    "ASHOKLEY": "500530", "BALKRISIND": "502355", "MRF": "500290",
    "APOLLOTYRE": "500877", "SIEMENS": "500550", "BHEL": "500103",
    "BEL": "500049", "HAL": "541154", "IRCTC": "542830",
    "GODREJCP": "532424", "GODREJPROP": "533150", "OBEROIRLTY": "533273",
    "DLF": "532868", "PFC": "532810", "RECLTD": "532955",
    "POWERINDIA": "532760", "ABB": "500002", "PERSISTENT": "533179",
    "MINDTREE": "532819", "LTI": "540005", "LTTS": "543211",
    "COFORGE": "532867", "MPHASIS": "532174", "NATIONALUM": "532234",
    "SUZLON": "532667", "YESBANK": "532648", "IDFCFIRSTB": "539437",
    "RBLBANK": "540065", "AUBANK": "540377", "BANKBARODA": "532134",
    "PNB": "532461", "CANBK": "532483", "UNIONBANK": "532477",
    "INDIANB": "532814", "IDBI": "500116", "MFSL": "500446",
    "IEX": "540777", "NIACL": "541227", "AARTIIND": "524208",
    "DALBHARAT": "542301", "NAVINFLUOR": "532251", "ABCAPITAL": "540726",
    "MOTILALOFS": "532892", "ANGELONE": "543235", "JUBLFOOD": "533155",
    "VBL": "543404", "KRBL": "530813", "ESCORTS": "500495",
    "TATAPOWER": "500400", "ADANITRANS": "543254", "ADANIGREEN": "543463",
    "ADANIPOWER": "533096", "ZYDUSLIFE": "532320",
}

_HEADERS_PDF = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/plain, application/pdf, */*",
}


def get_bse_scripcode(nse_symbol: str) -> str | None:
    """Map NSE symbol to BSE scrip code.
    Checks expanded JSON mapping first, then falls back to embedded dict."""
    sym = nse_symbol.upper()
    val = _EXPANDED.get(sym)
    if val is not None:
        return val
    return NSE_TO_BSE.get(sym)


# Load expanded mappings on module import
_EXPANDED = _load_bse_mappings()


def fetch_annual_report_urls(scripcode: str) -> list[dict]:
    """Fetch annual report PDF URLs from BSE API.
    Returns list of {year, pdf_url, date} dicts sorted by year desc."""
    try:
        url = f"{BSE_API_BASE}/AnnualReport_New/w?scripcode={scripcode}"
        resp = httpx.get(url, headers=BSE_HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        reports = []
        for row in (data.get("Table") or []):
            pdf_url = (row.get("PDFDownload") or "").strip()
            if not pdf_url or not pdf_url.endswith(".pdf"):
                continue
            pdf_url = pdf_url.replace("\\", "")
            reports.append({
                "year": row.get("Year"),
                "pdf_url": pdf_url,
                "date": row.get("Fld_AuthoriseDate"),
                "name": row.get("scrip_name"),
            })
        return reports
    except Exception:
        return []


def download_and_extract_pdf(pdf_url: str) -> str | None:
    """Download PDF from URL and extract text using PyMuPDF."""
    try:
        resp = httpx.get(pdf_url, headers=_HEADERS_PDF, timeout=60, follow_redirects=True)
        if resp.status_code != 200 or not resp.content:
            return None
        import fitz
        doc = fitz.open(stream=io.BytesIO(resp.content), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
            text += "\n"
        doc.close()
        return text if text.strip() else None
    except Exception:
        return None


def _parse_num(s: str) -> float | None:
    """Parse Indian number format '1,23,456.78' or '(1,234)' to float."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip().replace(",", "").replace(" ", "").replace("\t", "")
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        val = float(s)
        return -val if neg else val
    except (ValueError, TypeError):
        return None


def _find_value_after(text: str, labels: list[str], window: int = 200) -> float | None:
    """Search for a numeric value appearing after one of the given labels.
    Uses three strategies in sequence:
      1. Same-line: label and number on same line (with flexible separators)
      2. Newline: number on line immediately after label
      3. Chunk: first substantial number (>=100) within window after label
    """
    text_clean = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    text_clean = re.sub(r" +", " ", text_clean)

    found_small = None

    for label in labels:
        escaped = re.escape(label)
        same_line = escaped + r"\s*[:\-]?\s*([\d,]+\.?\d*)"
        m = re.search(same_line, text_clean, re.IGNORECASE)
        if m:
            val = _parse_num(m.group(1))
            if val is not None:
                if abs(val) >= 100:
                    return val
                if found_small is None:
                    found_small = val

        newline = escaped + r"\s*\n\s*([\d,]+\.?\d*)"
        m = re.search(newline, text, re.IGNORECASE)
        if m:
            val = _parse_num(m.group(1))
            if val is not None:
                if abs(val) >= 100:
                    return val
                if found_small is None:
                    found_small = val

    for label in labels:
        idx = text.lower().find(label.lower())
        if idx == -1:
            continue
        chunk = text[idx: idx + window]
        numbers = re.findall(r"([\d,]+\.?\d*)", chunk)
        for n in numbers:
            parsed = _parse_num(n)
            if parsed is not None and abs(parsed) >= 100:
                return parsed

    return found_small


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace by collapsing spaces but preserving paragraph structure."""
    return re.sub(r"[ \t]+", " ", text)


def parse_financials_from_text(pdf_text: str) -> dict:
    """Extract financial fields from annual report PDF text using regex patterns."""
    if not pdf_text:
        return {}

    result = {}

    mapping = {
        "total_assets": [
            "TOTAL ASSETS",
            "Total Assets",
            "Total assets",
            "Balance Sheet Total",
            "Total Equity and Liabilities",
        ],
        "depreciation": [
            "Depreciation and amortisation expense",
            "Depreciation and amortization expense",
            "Depreciation & Amortisation",
            "Depreciation & Amortization",
            "Depreciation Expense",
            "Depreciation",
        ],
        "employee_cost": [
            "Employee cost",
            "Employee Cost",
            "Employee benefits expense",
            "Employee benefits expenses",
            "Employee Benefit Expense",
            "Staff Costs",
            "Staff costs",
            "Salaries and wages",
            "Salaries and employee benefits",
            "Employee remuneration",
        ],
        "capex": [
            "Capital Expenditure",
            "Capital expenditure",
            "Purchase of Fixed Assets",
            "Purchase of Property, Plant and Equipment",
            "Additions to fixed assets",
            "Additions to property, plant and equipment",
        ],
        "cash_equivalents": [
            "Cash and cash equivalents",
            "Cash & Cash Equivalents",
            "Cash and Bank Balances",
            "Cash & Bank",
            "Cash and bank balances",
        ],
        "receivables": [
            "Trade Receivables",
            "Trade receivables",
            "Sundry Debtors",
            "Sundry debtors",
        ],
        "inventory": [
            "Inventories",
            "Stock in Trade",
            "Stock-In-Trade",
        ],
        "tax_expense": [
            "Tax expense",
            "Tax Expense",
            "Current Tax",
            "Income Tax Expense",
            "Provision for Tax",
            "Provision for income tax",
        ],
        "cash_flow_operations": [
            "Net cash from operating activities",
            "Net cash generated from operating activities",
            "Net cash flow from operating activities",
            "Cash generated from operations",
            "Cash flow from operating activities",
            "Net Cash Provided by Operating Activities",
        ],
    }

    for field, labels in mapping.items():
        val = _find_value_after(pdf_text, labels, window=200)
        if val is not None:
            result[field] = val

    return result


def fetch_bse_quarterly(symbol: str) -> list[dict] | None:
    """Main entry point: fetch quarterly financials from BSE annual report PDFs.
    Returns list of quarterly records matching QuarterlyFinancials schema,
    or None if no data available."""
    try:
        scripcode = get_bse_scripcode(symbol)
        if not scripcode:
            return None

        reports = fetch_annual_report_urls(scripcode)
        if not reports:
            return None

        latest_reports = [r for r in reports if r.get("year") and r["year"].isdigit()
                          and int(r["year"]) >= 2023]
        if not latest_reports:
            latest_reports = reports[:2]
        else:
            latest_reports = latest_reports[:2]  # two most recent years

        records = []
        seen_years = set()

        for report in latest_reports:
            year = report.get("year")
            if year in seen_years or not year:
                continue
            seen_years.add(year)

            if not report.get("pdf_url"):
                continue

            pdf_text = download_and_extract_pdf(report["pdf_url"])
            if not pdf_text:
                continue

            fin = parse_financials_from_text(pdf_text)
            populated = {k: v for k, v in fin.items() if v is not None}
            if not populated:
                continue

            record = {
                "quarter": f"{year}-Q1",
                "total_assets": fin.get("total_assets"),
                "cash_flow_operations": fin.get("cash_flow_operations"),
                "depreciation": fin.get("depreciation"),
                "capex": fin.get("capex"),
                "receivables": fin.get("receivables"),
                "inventory": fin.get("inventory"),
                "employee_cost": fin.get("employee_cost"),
                "tax_expense": fin.get("tax_expense"),
                "cash_equivalents": fin.get("cash_equivalents"),
            }
            records.append(record)

        return records if records else None

    except Exception:
        return None
