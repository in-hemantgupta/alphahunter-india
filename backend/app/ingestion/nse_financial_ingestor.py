"""NSE-based financial data ingestion as fallback when Screener.in is unreachable.
Uses yfinance to extract quarterly financial data."""
import yfinance as yf
from datetime import datetime


def _sf(q_data, index, col):
    """Safe float extraction from yfinance DataFrame."""
    try:
        if index in q_data.index:
            v = q_data.loc[index][col]
            if v is not None and not (isinstance(v, float) and v != v):
                return float(v)
    except:
        pass
    return None


def _nearest_col(date, df):
    """Find the nearest column in df on or before `date`. Returns None if df is empty."""
    if df is None or df.empty:
        return None, None
    # Find column ≤ date; if none, use earliest available
    valid = [c for c in df.columns if c <= date or True]  # all valid
    candidates = [c for c in df.columns if c <= date]
    if not candidates:
        candidates = sorted(df.columns)
    best = max(candidates) if candidates else None
    if best is None:
        return None, None
    return best, df[best]


def fetch_nse_quarterly(symbol: str) -> list[dict]:
    """Fetch quarterly financial data via yfinance with expanded field coverage.
    Maps balance sheet / cash flow data to income statement quarters via nearest-date.
    Falls back to annual cashflow when quarterly unavailable.
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        q_fin = ticker.quarterly_financials
        q_bs = ticker.quarterly_balance_sheet
        q_cf = ticker.quarterly_cashflow
        a_cf = ticker.cashflow  # annual cashflow as fallback

        if q_fin is None or q_fin.empty:
            return None

        records = []
        for i, col in enumerate(q_fin.columns):
            dt = col if hasattr(col, 'month') else datetime.strptime(str(col)[:10], "%Y-%m-%d")
            qtr = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"

            row = {"quarter": qtr}

            # --- Income Statement ---
            row["revenue"] = _sf(q_fin, "Total Revenue", col)
            row["operating_profit"] = _sf(q_fin, "Operating Income", col) or _sf(q_fin, "EBIT", col)
            row["ebitda"] = _sf(q_fin, "EBITDA", col)
            row["pat"] = _sf(q_fin, "Net Income", col)
            eps_raw = _sf(q_fin, "Basic EPS", col) or _sf(q_fin, "Diluted EPS", col)
            row["eps"] = eps_raw
            row["interest_expense"] = _sf(q_fin, "Interest Expense", col)
            # Depreciation: yfinance doesn't have a Depreciation line for Indian stocks
            # Compute as EBITDA - EBIT when available
            ebitda = row.get("ebitda")
            ebit = _sf(q_fin, "EBIT", col) or _sf(q_fin, "Operating Income", col)
            if ebitda is not None and ebit is not None:
                row["depreciation"] = ebitda - ebit
            else:
                row["depreciation"] = None
            row["tax_expense"] = _sf(q_fin, "Tax Provision", col) or _sf(q_fin, "Income Tax", col)
            row["employee_cost"] = (
                _sf(q_fin, "Selling General And Administration", col)
                or _sf(q_fin, "Salaries And Wages", col)
                or _sf(q_fin, "Staff Costs", col)
            )
            row["raw_material_cost"] = _sf(q_fin, "Cost Of Revenue", col) or _sf(q_fin, "Total Revenue", col)
            if row["raw_material_cost"] is not None and row["revenue"] is not None and row["raw_material_cost"] == row["revenue"]:
                row["raw_material_cost"] = None  # not actually cost breakdown

            rev = row.get("revenue", 0) or 0
            op = row.get("operating_profit", 0) or 0
            row["operating_margin"] = (op / rev * 100) if rev > 0 else None

            # --- Balance Sheet (nearest-date mapping) ---
            bs_col, bs_data = _nearest_col(dt, q_bs)
            if bs_col is not None and bs_data is not None:
                row["debt"] = _sf(q_bs, "Total Debt", bs_col)
                total_eq = _sf(q_bs, "Stockholders Equity", bs_col)
                row["total_equity"] = total_eq
                row["debt_equity"] = (row["debt"] / total_eq) if row["debt"] is not None and total_eq and total_eq > 0 else None
                row["total_assets"] = _sf(q_bs, "Total Assets", bs_col)
                row["current_assets"] = _sf(q_bs, "Current Assets", bs_col)
                row["current_liabilities"] = _sf(q_bs, "Current Liabilities", bs_col)
                row["cash_equivalents"] = _sf(q_bs, "Cash And Cash Equivalents", bs_col)
                if row["cash_equivalents"] is None:
                    row["cash_equivalents"] = _sf(q_bs, "Cash", bs_col)
                row["receivables"] = _sf(q_bs, "Receivables", bs_col)
                if row["receivables"] is None:
                    row["receivables"] = _sf(q_bs, "Accounts Receivable", bs_col)
                row["inventory"] = _sf(q_bs, "Inventory", bs_col)

            # --- Cash Flow (nearest-date mapping; fallback to annual) ---
            cf_source = q_cf
            if cf_source is None or cf_source.empty:
                cf_source = a_cf
            cf_col, cf_data = _nearest_col(dt, cf_source)
            if cf_col is not None and cf_data is not None:
                row["cash_flow_operations"] = _sf(cf_source, "Operating Cash Flow", cf_col)
                row["free_cash_flow"] = _sf(cf_source, "Free Cash Flow", cf_col)
                row["capex"] = _sf(cf_source, "Capital Expenditure", cf_col)
                if row["capex"] is None:
                    row["capex"] = _sf(cf_source, "Purchase Of Property, Plant & Equipment", cf_col)

            # --- Computed Metrics ---
            ce = None
            if row.get("total_assets") is not None and row.get("current_liabilities") is not None:
                ce = row["total_assets"] - row["current_liabilities"]
            elif row.get("total_assets") is not None and row.get("total_equity") is not None:
                ce = row["total_equity"] + (row.get("debt") or 0)
            if ce and ce > 0 and row.get("operating_profit") is not None:
                row["roce"] = (row["operating_profit"] / ce) * 100
            else:
                row["roce"] = None

            total_eq = row.get("total_equity")
            if total_eq and total_eq > 0 and row.get("pat") is not None:
                row["roe"] = (row["pat"] / total_eq) * 100
            else:
                row["roe"] = None

            records.append(row)

        return records
    except Exception as e:
        print(f"  NSE fallback failed for {symbol}: {e}")
        return None
