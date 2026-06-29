
from fastapi import APIRouter
from app.db.database import SessionLocal
from app.models.stock import Stock

router = APIRouter()

@router.get("/stocks")
def get_stocks():
    session = SessionLocal()
    stocks = session.query(Stock).limit(50).all()

    result = []
    for s in stocks:
        result.append({
            "symbol": s.symbol,
            "company_name": s.company_name
        })

    session.close()
    return {"stocks": result}
