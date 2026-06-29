from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.rebalance_history import RebalanceHistory
from app.models.portfolio_history import PortfolioHistory
from app.services.pipeline import run_full_pipeline, get_stock_data_for_scoring
from app.scoring.alpha_engine import alpha_score

app = FastAPI(title="QuantumAlpha India API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def score_all_stocks(session):
    stocks = session.query(Stock).all()
    results = []
    for stock in stocks:
        data = get_stock_data_for_scoring(stock.symbol, session)
        if data:
            data["total_score"] = alpha_score(data)
            data["company_name"] = stock.company_name
            results.append(data)
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results


@app.get("/")
def health():
    return {"status": "running"}


@app.get("/stocks")
def get_stocks():
    session = SessionLocal()
    try:
        ranked = score_all_stocks(session)
        return {"stocks": ranked}
    finally:
        session.close()


@app.get("/stocks/universe")
def get_universe():
    session = SessionLocal()
    try:
        stocks = session.query(Stock).all()
        price_count = session.query(func.count(PriceHistory.date)).scalar()
        return {
            "universe": [
                {"symbol": s.symbol, "company_name": s.company_name, "sector": s.sector, "exchange": s.exchange}
                for s in stocks
            ],
            "total_stocks": len(stocks),
            "total_prices": price_count,
        }
    finally:
        session.close()


@app.get("/stock/{symbol}")
def get_stock(symbol: str):
    session = SessionLocal()
    try:
        data = get_stock_data_for_scoring(symbol, session)
        if data:
            data["total_score"] = alpha_score(data)
        return {"symbol": symbol, "data": data}
    finally:
        session.close()


@app.get("/scan/run")
def run_scan():
    return run_full_pipeline()


@app.get("/scan/history")
def scan_history():
    session = SessionLocal()
    try:
        records = session.query(PortfolioHistory).order_by(PortfolioHistory.date.desc()).limit(100).all()
        return {
            "history": [
                {"date": str(r.date), "symbol": r.symbol, "allocation": r.allocation, "score": r.score}
                for r in records
            ]
        }
    finally:
        session.close()


@app.get("/portfolio/current")
def get_portfolio():
    session = SessionLocal()
    try:
        ranked = score_all_stocks(session)
        top = ranked[:10]
        total_score = sum(s["total_score"] for s in top) or 1
        portfolio = []
        for s in top:
            weight = s["total_score"] / total_score * 100
            portfolio.append({
                "symbol": s["symbol"],
                "company_name": s.get("company_name", ""),
                "weight": round(weight, 2),
                "score": round(s["total_score"], 2),
            })
        return {"portfolio": portfolio}
    finally:
        session.close()


@app.get("/rebalancing")
def get_rebalancing():
    session = SessionLocal()
    try:
        records = session.query(RebalanceHistory).order_by(RebalanceHistory.date.desc()).limit(100).all()
        return {
            "rebalances": [
                {"date": str(r.date), "symbol": r.symbol, "old_weight": r.old_weight, "new_weight": r.new_weight, "reason": r.reason}
                for r in records
            ]
        }
    finally:
        session.close()


@app.get("/agents/status")
def agents_status():
    return {"agents": "operational"}


@app.get("/ml/predictions")
def ml_predictions():
    return {"predictions": []}


@app.get("/signals/latest")
def latest_signals():
    session = SessionLocal()
    try:
        ranked = score_all_stocks(session)
        return {"signals": ranked[:20]}
    finally:
        session.close()
