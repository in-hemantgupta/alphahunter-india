import yfinance as yf
from datetime import datetime
from app.db.database import SessionLocal
from app.models.quarterly import QuarterlyFinancials


class FinancialIngestor:

    def fetch_quarterly(self, symbol: str) -> bool:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            financials = ticker.quarterly_financials
            balance_sheet = ticker.quarterly_balance_sheet

            if financials is None or financials.empty:
                return False

            session = SessionLocal()
            try:
                for i, col in enumerate(financials.columns[:8]):
                    year = col.year if hasattr(col, 'year') else 2025
                    month = col.month if hasattr(col, 'month') else 1
                    quarter_num = (month - 1) // 3 + 1
                    quarter_str = f"{year}-Q{quarter_num}"

                    existing = session.query(QuarterlyFinancials).filter_by(
                        symbol=symbol,
                        quarter=quarter_str
                    ).first()

                    if existing:
                        continue

                    q_data = financials[col]
                    bs_data = balance_sheet[col] if col in balance_sheet.columns else None

                    revenue = self._safe_get(q_data, 'Total Revenue')
                    ebitda = self._safe_get(q_data, 'EBITDA')
                    pat = self._safe_get(q_data, 'Net Income')

                    total_debt = self._safe_get(bs_data, 'Total Debt') if bs_data is not None else None
                    total_equity = self._safe_get(bs_data, 'Stockholders Equity') if bs_data is not None else None
                    if total_equity is None or total_equity == 0:
                        debt_equity = 1
                    else:
                        debt_equity = (total_debt or 0) / total_equity

                    total_assets = self._safe_get(bs_data, 'Total Assets') if bs_data is not None else None
                    ebit = self._safe_get(q_data, 'EBIT') or 0
                    if total_assets is None or total_assets == 0:
                        roce = 0
                    else:
                        roce = (ebit * 4 / total_assets) * 100

                    net_income = self._safe_get(q_data, 'Net Income') or 0
                    if total_equity is None or total_equity == 0:
                        roe = 0
                    else:
                        roe = (net_income * 4 / total_equity) * 100

                    record = QuarterlyFinancials(
                        symbol=symbol,
                        quarter=quarter_str,
                        revenue=revenue,
                        ebitda=ebitda,
                        pat=pat,
                        roce=roce,
                        roe=roe,
                        debt_equity=debt_equity
                    )
                    session.add(record)

                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"Error saving quarterly data for {symbol}: {e}")
                return False
            finally:
                session.close()

        except Exception as e:
            print(f"Error fetching quarterly data for {symbol}: {e}")
            return False

    def _safe_get(self, data, key):
        try:
            if data is None:
                return None
            if hasattr(data, 'get'):
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
