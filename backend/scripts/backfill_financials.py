"""NSE financial backfill for all stocks.

Runs the NSE yfinance ingestor on ALL stocks to fill gaps from
Screener.in's missing fields (cash flow, balance sheet breakdown,
and the 10 expanded P1B fields).

Usage:
    source venv/bin/activate
    PYTHONPATH=. python scripts/backfill_financials.py
"""

import sys, os, time
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
print(f"Total stocks: {len(all_stocks)}")

# Load existing quarters per stock
existing = session.query(
    QuarterlyFinancials.symbol, QuarterlyFinancials.quarter
).all()
existing_map = {}
for sym, qtr in existing:
    existing_map.setdefault(sym, set()).add(qtr)

updated = 0
failed = 0
skipped = 0
filled_counts = {f: 0 for f in NSE_FIELDS}

for i, stock in enumerate(all_stocks):
    if (i+1) % 100 == 0:
        elapsed = time.time() - t0
        rate = (i+1) / elapsed
        print(f"  [{i+1}/{len(all_stocks)}] {updated} updated, {failed} failed, "
              f"{elapsed:.0f}s ({rate:.0f}/s)", flush=True)

    try:
        records = fetch_nse_quarterly(stock.symbol)
        if not records:
            skipped += 1
            continue

        ses = SessionLocal()
        try:
            stock_updated = False
            for row in records:
                qtr = row["quarter"]
                if qtr not in existing_map.get(stock.symbol, set()):
                    continue  # only update existing quarters

                qf = ses.query(QuarterlyFinancials).filter_by(
                    symbol=stock.symbol, quarter=qtr
                ).first()
                if not qf:
                    continue

                changed = False
                for field in NSE_FIELDS:
                    val = row.get(field)
                    if val is not None and getattr(qf, field) is None:
                        setattr(qf, field, val)
                        filled_counts[field] += 1
                        changed = True

                if changed:
                    stock_updated = True

            if stock_updated:
                ses.commit()
                updated += 1
            else:
                skipped += 1
        finally:
            ses.close()
    except Exception as e:
        failed += 1
        if failed <= 5:
            print(f"  FAIL: {stock.symbol}: {e}")

session.close()
elapsed = time.time() - t0
print(f"\n{'='*50}")
print(f"Backfill complete: {elapsed:.0f}s")
print(f"  Updated: {updated} stocks")
print(f"  Skipped: {skipped} stocks")
print(f"  Failed:  {failed} stocks")
print(f"\nFields filled from NSE:")
for f in NSE_FIELDS:
    print(f"  {f:25s}: {filled_counts[f]:>6d} records")
