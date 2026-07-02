"""Parallel NSE financial backfill using ThreadPoolExecutor.
Updates existing quarterly records with missing fields from yfinance/NSE ingestor.
"""
import sys, os, time, concurrent.futures
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.quarterly import QuarterlyFinancials
from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly

NSE_FIELDS = [
    "revenue", "ebitda", "operating_profit", "pat", "eps",
    "operating_margin", "roce", "roe", "debt_equity",
    "cash_flow_operations", "free_cash_flow",
    "debt", "receivables", "inventory", "interest_expense",
    "depreciation", "tax_expense", "employee_cost", "raw_material_cost",
    "total_assets", "total_equity", "current_assets", "current_liabilities",
    "cash_equivalents", "capex",
]

t0 = time.time()
session = SessionLocal()
all_stocks = session.query(Stock).all()
existing_qtrs = list(session.query(
    QuarterlyFinancials.symbol, QuarterlyFinancials.quarter
).all())
session.close()

# Group quarters by symbol
from collections import defaultdict
sym_qtrs = defaultdict(set)
for sym, qtr in existing_qtrs:
    sym_qtrs[sym].add(qtr)

total = len(all_stocks)
print(f"Total stocks: {total}")


def process_stock(stock):
    try:
        records = fetch_nse_quarterly(stock.symbol)
        if not records:
            return None

        ses = SessionLocal()
        try:
            updated = False
            for row in records:
                qtr = row["quarter"]
                if qtr not in sym_qtrs.get(stock.symbol, set()):
                    continue
                qf = ses.query(QuarterlyFinancials).filter_by(
                    symbol=stock.symbol, quarter=qtr
                ).first()
                if not qf:
                    continue
                for field in NSE_FIELDS:
                    val = row.get(field)
                    if val is not None and getattr(qf, field) is None:
                        setattr(qf, field, val)
                        updated = True
            if updated:
                ses.commit()
                return stock.symbol
            return None
        finally:
            ses.close()
    except Exception:
        return None


completed = 0
updated = 0
failed = 0

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    fut_map = {ex.submit(process_stock, s): s for s in all_stocks}
    for fut in concurrent.futures.as_completed(fut_map):
        completed += 1
        result = fut.result()
        if result:
            updated += 1
        else:
            failed += 1
        if completed % 200 == 0 or completed == total:
            elapsed = time.time() - t0
            rate = completed / elapsed
            print(f"  [{completed}/{total}] {updated} updated, {failed} failed, "
                  f"{elapsed:.0f}s ({rate:.1f}/s)", flush=True)

elapsed = time.time() - t0
print(f"\nBackfill complete: {elapsed:.0f}s")
print(f"  Updated: {updated} stocks")
print(f"  Failed:  {failed} stocks")
