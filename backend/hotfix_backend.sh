#!/bin/bash

echo "===== PATCH 1: backup main.py ====="
cp main.py main.py.bak

echo "===== PATCH 2: replace slow /stocks endpoint ====="

python << 'PY'
from pathlib import Path
p = Path("main.py")
txt = p.read_text()

old = '''@app.get("/stocks")
def get_stocks():
    session = SessionLocal()
    try:
        ranked = score_all_stocks(session)
        return {"stocks": ranked}
    finally:
        session.close()
'''

new = '''@app.get("/stocks")
def get_stocks():
    session = SessionLocal()
    try:
        stocks = session.query(Stock).limit(100).all()
        return {
            "stocks": [
                {
                    "symbol": s.symbol,
                    "company_name": s.company_name
                }
                for s in stocks
            ]
        }
    finally:
        session.close()


@app.get("/stocks/scored")
def get_scored_stocks():
    session = SessionLocal()
    try:
        ranked = score_all_stocks(session)
        return {"stocks": ranked[:50]}
    finally:
        session.close()
'''

if old in txt:
    txt = txt.replace(old, new)
    p.write_text(txt)
    print("main.py patched")
else:
    print("WARNING: exact block not found, main.py unchanged")
PY

echo "===== PATCH 3: create postgres index ====="

psql -U postgres -d alphahunter -c "
CREATE INDEX IF NOT EXISTS idx_price_symbol_date
ON price_history(symbol, date DESC);
"

echo "===== PATCH 4: kill stuck postgres sessions ====="

psql -U postgres -d alphahunter -c "
select pg_terminate_backend(pid)
from pg_stat_activity
where datname='alphahunter'
and state='idle in transaction';
"

echo "===== PATCH 5: restart uvicorn ====="

pkill -f uvicorn
sleep 2

nohup uvicorn main:app --reload --port 8001 > backend.log 2>&1 &

sleep 5

echo "===== PATCH 6: compile check ====="
find app -name "*.py" -exec python -m py_compile {} \; 2>&1

echo "===== PATCH 7: endpoint speed test ====="
time curl http://127.0.0.1:8001/stocks | head -c 300

echo ""
echo "===== PATCH 8: scored endpoint ====="
time curl http://127.0.0.1:8001/stocks/scored | head -c 300

echo ""
echo "===== DONE ====="
