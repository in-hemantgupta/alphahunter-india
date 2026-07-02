import requests
from bs4 import BeautifulSoup
import re


def scrape_screener(symbol: str) -> dict:
    try:
        url = f"https://www.screener.in/company/{symbol}/consolidated/"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        data = {"symbol": symbol}

        # Extract summary KPIs from 2-column data tables
        for table in soup.find_all("table", class_="data-table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).lower()
                    val = cells[1].get_text(strip=True)
                    num = _parse_number(val)
                    if num is not None:
                        data[_normalize_key(key)] = num

        # Extract quarterly financial tables
        sections = soup.find_all("section")
        for section in sections:
            h2 = section.find("h2")
            if not h2:
                continue
            title = h2.get_text(strip=True).lower()

            table = section.find("table")
            if not table:
                continue

            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Header row: quarter labels
            header_cells = rows[0].find_all(["th", "td"])
            quarters = []
            for cell in header_cells[1:]:
                q = cell.get_text(strip=True)
                if q:
                    quarters.append(q)

            if not quarters:
                continue

            # Data rows
            quarterly_data = {}
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                metric = cells[0].get_text(strip=True).lower().strip()
                metric = _normalize_quarterly_metric(metric)
                if not metric:
                    continue
                vals = []
                for cell in cells[1:]:
                    v = cell.get_text(strip=True)
                    vals.append(_parse_number(v))
                quarterly_data[metric] = vals

            if title.startswith("profit") or title.startswith("profit & loss"):
                data["quarterly_pl"] = {"quarters": quarters, **quarterly_data}
            elif "cash flow" in title:
                data["quarterly_cf"] = {"quarters": quarters, **quarterly_data}
            elif "balance sheet" in title:
                data["quarterly_bs"] = {"quarters": quarters, **quarterly_data}

        return data
    except Exception as e:
        print(f"Screener scrape failed for {symbol}: {e}")
        return {}


def _normalize_quarterly_metric(metric: str) -> str | None:
    mapping = {
        "revenue": "revenue",
        "sales": "revenue",
        "operating profit": "operating_profit",
        "op profit": "operating_profit",
        "interest": "interest_expense",
        "depreciation": "depreciation",
        "tax": "tax_expense",
        "tax expense": "tax_expense",
        "net profit": "pat",
        "net profit +": "pat",
        "eps": "eps",
        "cash from operating": "cash_flow_operations",
        "cash from operations": "cash_flow_operations",
        "operating cash flow": "cash_flow_operations",
        "free cash flow": "free_cash_flow",
        "capital expenditure": "capex",
        "borrowings": "debt",
        "total debt": "debt",
        "total liabilities": "debt",
        "inventories": "inventory",
        "trade receivables": "receivables",
        "receivables": "receivables",
        "debtors": "receivables",
        "cash": "cash_equivalents",
        "cash & bank": "cash_equivalents",
        "equity capital": "total_equity",
        "share capital": "total_equity",
        "reserves": "reserves",
        "total assets": "total_assets",
        "current assets": "current_assets",
        "current liabilities": "current_liabilities",
        "employee cost": "employee_cost",
        "employee expense": "employee_cost",
        "raw material cost": "raw_material_cost",
        "cost of materials": "raw_material_cost",
    }
    return mapping.get(metric, None)


def _parse_number(text: str):
    text = text.replace(",", "").replace("₹", "").replace("%", "").strip()
    if text in ("", "-", "NA", "N/A", "—"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_key(key: str) -> str:
    mapping = {
        "roce": "roce",
        "roe": "roe",
        "roa": "roa",
        "debt to equity": "debt_equity",
        "debt/equity": "debt_equity",
        "operating margin": "opm",
        "net profit margin": "npm",
        "sales growth 3years": "sales_growth_3y",
        "sales growth 5years": "sales_growth_5y",
        "profit growth 3years": "profit_growth_3y",
        "profit growth 5years": "profit_growth_5y",
        "promoter holding": "promoter_holding",
        "pledged": "pledge_percent",
        "market cap": "market_cap_cr",
        "pe ratio": "pe_ratio",
        "pb ratio": "pb_ratio",
        "ev/ebitda": "ev_ebitda",
        "book value": "book_value",
        "dividend yield": "div_yield",
        "face value": "face_value",
        "cash": "cash",
        "reserves": "reserves",
        "borrowings": "borrowings",
        "other income": "other_income",
        "int coverage": "interest_coverage",
    }
    return mapping.get(key, key.replace(" ", "_").replace("/", "_"))
