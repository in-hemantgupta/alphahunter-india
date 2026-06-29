
echo "===== CHECK 1: inspect one stock raw scoring data ====="
python << PY
from app.db.database import SessionLocal
from app.services.pipeline import get_stock_data_for_scoring

session = SessionLocal()

# pick first stock
data = get_stock_data_for_scoring("RELIANCE", session)

print(data)

session.close()
PY

echo ""
echo "===== CHECK 2: inspect alpha score breakdown ====="

sed -n '1,220p' app/scoring/alpha_engine.py

echo ""
echo "===== CHECK 3: inspect component scorers ====="

grep -R "def .*score" app/scoring/

echo ""
echo "===== CHECK 4: look for hardcoded zero fields ====="

grep -R '"roce": 0' app/
grep -R '"roe": 0' app/
grep -R '"delivery_ratio": 0' app/
grep -R '"relative_strength": 50' app/

