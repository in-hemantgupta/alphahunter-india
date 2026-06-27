#!/bin/bash

echo "=== Fixing corrupted pd.DataFrame returns ==="

# pipeline.py fixes
sed -i '' 's/return {"error": "Failed to fetch universe", "stocks": pd.DataFrame()}/return {"error": "Failed to fetch universe", "stocks": []}/g' app/services/pipeline.py
sed -i '' 's/return {"error": str(e), "stocks": pd.DataFrame()}/return {"error": str(e), "stocks": []}/g' app/services/pipeline.py

# api/stocks.py fix
sed -i '' 's/return {"stocks": pd.DataFrame()}/return {"stocks": []}/g' app/api/stocks.py 2>/dev/null

echo "=== Fixing alpha_engine bad defaults ==="

sed -i '' 's/stock.get("recent_returns", pd.DataFrame())/stock.get("recent_returns", [])/g' app/scoring/alpha_engine.py 2>/dev/null
sed -i '' 's/stock.get("price_series", pd.DataFrame())/stock.get("price_series", [])/g' app/scoring/alpha_engine.py 2>/dev/null

echo "=== Fixing rebalance engine ==="

sed -i '' 's/sells = pd.DataFrame()/sells = []/g' app/portfolio/rebalance_engine.py 2>/dev/null
sed -i '' 's/buys = pd.DataFrame()/buys = []/g' app/portfolio/rebalance_engine.py 2>/dev/null

echo "=== Searching dangerous fake yfinance patches ==="
grep -R "ticker = None" app/ || true
grep -R "yf = None" app/ || true

echo "=== Searching leftover pandas append corruption ==="
grep -R "\.append(" app/ || true

echo "=== Searching leftover pd.DataFrame placeholders ==="
grep -R "pd.DataFrame()" app/ || true

echo ""
echo "PATCH COMPLETE"
