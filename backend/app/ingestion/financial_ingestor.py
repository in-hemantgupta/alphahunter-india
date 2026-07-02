import yfinance as yf
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.models.quarterly import QuarterlyFinancials
from app.ingestion.screener_scraper import scrape_screener


class FinancialIngestor:

    _screener_unreachable = False

    def fetch_quarterly(self, symbol: str) -> bool:
        """Primary: Screener.in. Fallback: yfinance."""
        if not FinancialIngestor._screener_unreachable:
            screener_data = scrape_screener(symbol)
            if screener_data and (
                screener_data.get("quarterly_pl")
                or screener_data.get("quarterly_cf")
                or screener_data.get("quarterly_bs")
            ):
                return self._from_screener(symbol, screener_data)
            if not screener_data:
                FinancialIngestor._screener_unreachable = True
                print("Screener.in unreachable - disabling for this run")

        return self._from_yfinance(symbol)

    def _from_screener(self, symbol: str, data: dict) -> bool:
        session = SessionLocal()
        try:
            pl = data.get("quarterly_pl") or {}
            cf = data.get("quarterly_cf") or {}
            bs = data.get("quarterly_bs") or {}

            if not pl and not cf and not bs:
                return False

            quarters = set()
            for src in [pl, cf, bs]:
                quarters.update(src.get("quarters", []))
            quarters = sorted(quarters)

            for qi, qlabel in enumerate(quarters):
                quarter_str = self._parse_quarter_label(qlabel)
                if not quarter_str:
                    continue

                existing = session.query(QuarterlyFinancials).filter_by(
                    symbol=symbol, quarter=quarter_str
                ).first()
                if existing:
                    continue

                record = QuarterlyFinancials(
                    symbol=symbol,
                    quarter=quarter_str,
                    revenue=self._screener_val(pl, qi, "revenue"),
                    ebitda=None,
                    operating_profit=self._screener_val(pl, qi, "operating_profit"),
                    pat=self._screener_val(pl, qi, "pat"),
                    eps=self._screener_val(pl, qi, "eps"),
                    cash_flow_operations=self._screener_val(cf, qi, "cash_flow_operations"),
                    free_cash_flow=self._screener_val(cf, qi, "free_cash_flow"),
                    debt=self._screener_val(bs, qi, "debt"),
                    interest_expense=self._screener_val(pl, qi, "interest_expense"),
                    inventory=self._screener_val(bs, qi, "inventory"),
                    receivables=self._screener_val(bs, qi, "receivables"),
                    # Expanded fields
                    total_assets=self._screener_val(bs, qi, "total_assets"),
                    total_equity=self._screener_val(bs, qi, "total_equity"),
                    current_assets=self._screener_val(bs, qi, "current_assets"),
                    current_liabilities=self._screener_val(bs, qi, "current_liabilities"),
                    depreciation=self._screener_val(pl, qi, "depreciation"),
                    tax_expense=self._screener_val(pl, qi, "tax_expense"),
                    employee_cost=self._screener_val(pl, qi, "employee_cost"),
                    raw_material_cost=self._screener_val(pl, qi, "raw_material_cost"),
                    cash_equivalents=self._screener_val(bs, qi, "cash_equivalents"),
                    capex=self._screener_val(cf, qi, "capex"),
                )
                # Compute EBITDA if not directly available
                rev = record.revenue
                op = record.operating_profit
                dep = record.depreciation
                if rev is not None and op is not None:
                    record.ebitda = op + (dep or 0) if dep is not None else op
                if rev is not None and rev > 0 and op is not None:
                    record.operating_margin = round((op / rev) * 100, 2)
                session.add(record)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error saving screener data for {symbol}: {e}")
            return False
        finally:
            session.close()

    def _from_yfinance(self, symbol: str) -> bool:
        try:
            from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly
            records = fetch_nse_quarterly(symbol)
            if not records:
                return self._from_bse(symbol)

            session = SessionLocal()
            try:
                for row in records:
                    existing = session.query(QuarterlyFinancials).filter_by(
                        symbol=symbol, quarter=row["quarter"]
                    ).first()
                    if existing and existing.cash_flow_operations is not None:
                        continue
                    qf = existing or QuarterlyFinancials(symbol=symbol, quarter=row["quarter"])
                    _FIELD_KEYS = [
                        "revenue", "ebitda", "operating_profit", "pat", "eps",
                        "operating_margin", "roce", "roe", "debt_equity",
                        "cash_flow_operations", "free_cash_flow",
                        "debt", "receivables", "inventory", "interest_expense",
                        "depreciation", "tax_expense", "employee_cost", "raw_material_cost",
                        "total_assets", "total_equity", "current_assets", "current_liabilities",
                        "cash_equivalents", "capex",
                    ]
                    for field in _FIELD_KEYS:
                        val = row.get(field)
                        if val is not None:
                            setattr(qf, field, val)
                    if not existing:
                        session.add(qf)
                session.commit()
                return True
            finally:
                session.close()

        except Exception as e:
            print(f"  yfinance fallback error for {symbol}: {e}")
            return self._from_bse(symbol)

    def _from_bse(self, symbol: str) -> bool:
        """BSE corporate filings fallback (lowest priority)."""
        try:
            from app.ingestion.bse_financial_ingestor import fetch_bse_quarterly
            records = fetch_bse_quarterly(symbol)
            if not records:
                return False
            session = SessionLocal()
            try:
                for row in records:
                    existing = session.query(QuarterlyFinancials).filter_by(
                        symbol=symbol, quarter=row["quarter"]
                    ).first()
                    if existing and existing.cash_flow_operations is not None:
                        continue
                    qf = existing or QuarterlyFinancials(symbol=symbol, quarter=row["quarter"])
                    _FIELD_KEYS = [
                        "revenue", "ebitda", "operating_profit", "pat", "eps",
                        "operating_margin", "roce", "roe", "debt_equity",
                        "cash_flow_operations", "free_cash_flow",
                        "debt", "receivables", "inventory", "interest_expense",
                        "depreciation", "tax_expense", "employee_cost", "raw_material_cost",
                        "total_assets", "total_equity", "current_assets", "current_liabilities",
                        "cash_equivalents", "capex",
                    ]
                    for field in _FIELD_KEYS:
                        val = row.get(field)
                        if val is not None:
                            setattr(qf, field, val)
                    if not existing:
                        session.add(qf)
                session.commit()
                return True
            finally:
                session.close()
        except Exception as e:
            print(f"  BSE fallback failed for {symbol}: {e}")
            return False

    def _from_yfinance_old(self, symbol: str) -> bool:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            financials = ticker.quarterly_financials
            balance_sheet = ticker.quarterly_balance_sheet

            if financials is None or financials.empty:
                return False

            session = SessionLocal()
            try:
                for i, col in enumerate(financials.columns[:8]):
                    year = col.year if hasattr(col, "year") else 2025
                    month = col.month if hasattr(col, "month") else 1
                    quarter_num = (month - 1) // 3 + 1
                    quarter_str = f"{year}-Q{quarter_num}"

                    existing = session.query(QuarterlyFinancials).filter_by(
                        symbol=symbol, quarter=quarter_str
                    ).first()

                    if existing and existing.cash_flow_operations is not None:
                        continue

                    q_data = financials[col]
                    bs_data = balance_sheet[col] if col in balance_sheet.columns else None

                    cf_data = None
                    if hasattr(ticker, "quarterly_cashflow"):
                        try:
                            cf = ticker.quarterly_cashflow
                            if cf is not None and col in cf.columns:
                                cf_data = cf[col]
                        except:
                            pass

                    revenue = self._safe_get(q_data, "Total Revenue")
                    ebitda = self._safe_get(q_data, "EBITDA")
                    operating_profit = (
                        self._safe_get(q_data, "Operating Income")
                        or self._safe_get(q_data, "EBIT")
                    )
                    pat = self._safe_get(q_data, "Net Income")
                    eps = self._safe_get(q_data, "Diluted EPS") or self._safe_get(q_data, "Basic EPS")

                    total_debt = (
                        self._safe_get(bs_data, "Total Debt") if bs_data is not None else None
                    )
                    total_equity = (
                        self._safe_get(bs_data, "Stockholders Equity")
                        if bs_data is not None
                        else None
                    )
                    debt_equity = None
                    if total_equity is not None and total_equity > 0:
                        debt_equity = (total_debt or 0) / total_equity

                    total_assets = (
                        self._safe_get(bs_data, "Total Assets") if bs_data is not None else None
                    )
                    ebit = self._safe_get(q_data, "EBIT") or 0
                    roce = None
                    if total_assets is not None and total_assets > 0:
                        roce = (ebit * 4 / total_assets) * 100

                    net_income = self._safe_get(q_data, "Net Income") or 0
                    roe = None
                    if total_equity is not None and total_equity > 0:
                        roe = (net_income * 4 / total_equity) * 100

                    operating_margin = (
                        (operating_profit / revenue * 100)
                        if operating_profit is not None and revenue and revenue > 0
                        else None
                    )
                    cash_flow_operations = (
                        self._safe_get(cf_data, "Operating Cash Flow")
                        if cf_data is not None
                        else None
                    )
                    free_cash_flow = (
                        self._safe_get(cf_data, "Free Cash Flow")
                        if cf_data is not None
                        else None
                    )
                    interest_expense = self._safe_get(q_data, "Interest Expense")
                    inventory = (
                        self._safe_get(bs_data, "Inventory") if bs_data is not None else None
                    )
                    receivables = (
                        self._safe_get(bs_data, "Accounts Receivable")
                        or self._safe_get(bs_data, "Receivables")
                        if bs_data is not None
                        else None
                    )
                    debt = total_debt

                    if existing:
                        existing.revenue = revenue
                        existing.ebitda = ebitda
                        existing.operating_profit = operating_profit
                        existing.pat = pat
                        existing.eps = eps
                        existing.roce = roce
                        existing.roe = roe
                        existing.debt_equity = debt_equity
                        existing.operating_margin = operating_margin
                        existing.cash_flow_operations = cash_flow_operations
                        existing.free_cash_flow = free_cash_flow
                        existing.debt = debt
                        existing.interest_expense = interest_expense
                        existing.inventory = inventory
                        existing.receivables = receivables
                    else:
                        record = QuarterlyFinancials(
                            symbol=symbol,
                            quarter=quarter_str,
                            revenue=revenue,
                            ebitda=ebitda,
                            operating_profit=operating_profit,
                            pat=pat,
                            eps=eps,
                            roce=roce,
                            roe=roe,
                            debt_equity=debt_equity,
                            operating_margin=operating_margin,
                            cash_flow_operations=cash_flow_operations,
                            free_cash_flow=free_cash_flow,
                            debt=debt,
                            interest_expense=interest_expense,
                            inventory=inventory,
                            receivables=receivables,
                        )
                        session.add(record)

                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"Error saving yfinance data for {symbol}: {e}")
                return False
            finally:
                session.close()

        except Exception as e:
            print(f"Error fetching yfinance data for {symbol}: {e}")
            return False

    def _screener_val(self, section, idx, key):
        if not section:
            return None
        vals = section.get(key)
        if not vals or idx >= len(vals):
            return None
        v = vals[idx]
        return float(v) if v is not None else None

    def _parse_quarter_label(self, label: str) -> str | None:
        """Parse 'Mar 2025' -> '2025-Q1', 'Jun 2024' -> '2024-Q2', etc."""
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        try:
            parts = label.strip().split()
            if len(parts) < 2:
                return None
            month_str = parts[0].lower()[:3]
            year_str = parts[1]
            month = month_map.get(month_str)
            if month is None:
                return None
            year = int(year_str)
            quarter_num = (month - 1) // 3 + 1
            return f"{year}-Q{quarter_num}"
        except:
            return None

    def _safe_get(self, data, key):
        try:
            if data is None:
                return None
            if hasattr(data, "get"):
                val = data.get(key)
            elif hasattr(data, key):
                val = getattr(data, key)
            else:
                return None
            if val is not None and not (isinstance(val, float) and (val != val)):
                return float(val)
        except:
            pass
        return None
