#!/usr/bin/env python
"""Backfill employee_cost from yfinance SG&A / Salaries columns for stocks with zero coverage."""

import sys, os, time, concurrent.futures
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import SessionLocal
from app.models.quarterly import QuarterlyFinancials
from sqlalchemy import func, distinct


def try_yfinance_employee_cost(symbol):
    """Fetch yfinance quarterly data and try to extract employee-related fields."""
    import yfinance as yf
    try:
        tk = yf.Ticker(f"{symbol}.NS")
        q_fin = tk.quarterly_financials
        if q_fin is None or q_fin.empty:
            return symbol, 0

        session = SessionLocal()
        try:
            updated = 0
            from datetime import datetime

            for col in q_fin.columns:
                dt = col if hasattr(col, 'month') else datetime.strptime(str(col)[:10], "%Y-%m-%d")
                qtr = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"

                emp = None
                if 'Selling General And Administration' in q_fin.index:
                    v = q_fin.loc['Selling General And Administration', col]
                    if v is not None and not (isinstance(v, float) and v != v):
                        emp = float(v)
                if emp is None and 'Salaries And Wages' in q_fin.index:
                    v = q_fin.loc['Salaries And Wages', col]
                    if v is not None and not (isinstance(v, float) and v != v):
                        emp = float(v)

                if emp is not None:
                    existing = session.query(QuarterlyFinancials).filter(
                        QuarterlyFinancials.symbol == symbol,
                        QuarterlyFinancials.quarter == qtr
                    ).first()
                    if existing and existing.employee_cost is None:
                        existing.employee_cost = emp
                        updated += 1

            if updated > 0:
                session.commit()
            return symbol, updated
        finally:
            session.close()
    except Exception:
        return symbol, 0


def main():
    print("=" * 60)
    print("yfinance SG&A backfill for employee_cost")
    print("=" * 60)

    session = SessionLocal()
    missing = session.query(distinct(QuarterlyFinancials.symbol)).filter(
        QuarterlyFinancials.employee_cost.is_(None)
    ).all()
    session.close()

    symbols = sorted([s for (s,) in missing])
    total_stocks = len(symbols)

    # Also get stocks with partial coverage (1-3 quarters) to check for SG&A
    session = SessionLocal()
    partial = session.query(
        QuarterlyFinancials.symbol,
        func.count(QuarterlyFinancials.quarter)
    ).filter(
        QuarterlyFinancials.employee_cost.is_(None)
    ).group_by(QuarterlyFinancials.symbol).having(
        func.count(QuarterlyFinancials.quarter) > 0
    ).all()
    session.close()

    partial_symbols = set(s for (s, c) in partial if c < 4)

    print(f"Stocks with 0 employee_cost: {len(symbols)}")
    print(f"Stocks with partial coverage (<4 quarters): {len(partial_symbols)}")

    all_to_check = list(set(symbols) | partial_symbols)
    print(f"Total to check: {len(all_to_check)}")

    if not all_to_check:
        print("Nothing to do.")
        return

    start = time.time()
    results = {"updated": 0, "no_data": 0}
    total_updated_records = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(try_yfinance_employee_cost, sym): sym for sym in all_to_check}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            done += 1
            try:
                sym, n = future.result(timeout=60)
            except (concurrent.futures.TimeoutError, Exception):
                sym = futures[future]
                n = 0
                results["no_data"] += 1

            if n > 0:
                results["updated"] += 1
                total_updated_records += n
            else:
                results["no_data"] += 1

            if done % 50 == 0 or done == len(all_to_check):
                elapsed = time.time() - start
                rate = done / elapsed * 60 if elapsed > 0 else 0
                print(f"  [{done}/{len(all_to_check)}] {elapsed:.0f}s — "
                      f"updated={results['updated']}, records_added={total_updated_records} | "
                      f"{rate:.1f}/min, last: {sym}")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.0f}s")

    session = SessionLocal()
    total = session.query(func.count(QuarterlyFinancials.quarter)).scalar()
    emp = session.query(func.count(QuarterlyFinancials.quarter)).filter(
        QuarterlyFinancials.employee_cost.isnot(None)).scalar()
    session.close()
    print(f"\nAFTER — total={total}, employee_cost={emp} ({emp/total*100:.1f}%)")
    print(f"Delta: +{total_updated_records} records")


if __name__ == "__main__":
    main()
