import requests
from bs4 import BeautifulSoup
import re


def scrape_screener(symbol: str) -> dict:
    try:
        url = f"https://www.screener.in/company/{symbol}/consolidated/"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        data = {"symbol": symbol}

        for table in soup.find_all("table", class_="data-table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).lower()
                    val = cells[1].get_text(strip=True)
                    num = _parse_number(val)
                    if num is not None:
                        data[_normalize_key(key)] = num

        return data
    except Exception as e:
        print(f"Screener scrape failed for {symbol}: {e}")
        return {}


def _parse_number(text: str):
    text = text.replace(",", "").replace("₹", "").replace("%", "").strip()
    if text in ("", "-", "NA", "N/A"):
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
