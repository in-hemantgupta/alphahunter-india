from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.rebalance_history import RebalanceHistory
from app.models.portfolio_history import PortfolioHistory
from app.models.scored_stock import ScoredStock
from app.services.pipeline import run_full_pipeline, get_stock_data_for_scoring
from app.services.elimination import run_elimination_pipeline
from app.scoring.alpha_engine import alpha_score

app = FastAPI(title="QuantumAlpha India API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def score_all_stocks(session, limit=500):
    stocks = session.query(Stock).limit(limit).all()
    results = []
    for stock in stocks:
        data = get_stock_data_for_scoring(stock.symbol, session)
        if data:
            passed, stages = run_elimination_pipeline(stock.symbol, session, data)
            if passed:
                data["total_score"] = alpha_score(data)
                data["company_name"] = stock.company_name
                data["elimination_stages"] = stages
                results.append(data)
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results


def get_scored_stocks_from_db(session, limit=500):
    scored = session.query(ScoredStock).order_by(ScoredStock.total_score.desc()).limit(limit).all()
    stocks = []
    for s in scored:
        stocks.append({
            "symbol": s.symbol,
            "company_name": s.company_name,
            "total_score": s.total_score,
            "current_price": s.current_price,
            "returns_6m": s.returns_6m,
            "returns_1y": s.returns_1y,
            "volume_ratio": s.volume_ratio,
            "delivery_ratio": s.delivery_ratio,
            "roce": s.roce,
            "roe": s.roe,
            "debt_equity": s.debt_equity,
            "revenue_acceleration": s.revenue_acceleration,
            "pat_acceleration": s.pat_acceleration,
            "margin_expansion": s.margin_expansion,
            "promoter_change": s.promoter_change,
            "pledge_percent": s.pledge_percent,
            "relative_strength": s.relative_strength,
            "trend_strength": s.trend_strength,
            "compression_pattern": s.compression_pattern,
            "breakout_probability": s.breakout_probability,
            "volume_confirmation": s.volume_confirmation,
            "google_trend_score": s.google_trend_score,
            "contract_score": s.contract_score,
            "hiring_score": s.hiring_score,
            "patent_score": s.patent_score,
            "news_score": s.news_score,
            "annual_report_score": s.annual_report_score,
            "concall_score": s.concall_score,
            "governance_score": s.governance_score,
            "narrative_score": s.narrative_score,
            "risk_score": s.risk_score,
            "management_confidence": s.management_confidence,
            "elimination_stages": s.elimination_stages.split(',') if s.elimination_stages else [],
            "passed_elimination": s.passed_elimination
        })
    return stocks


@app.get("/")
def health():
    return {"status": "running"}


@app.get("/stocks")
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
def get_scored_stocks(limit: int = 500):
    session = SessionLocal()
    try:
        stocks = get_scored_stocks_from_db(session, limit=limit)
        return {"stocks": stocks}
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
            passed, stages = run_elimination_pipeline(symbol, session, data)
            data["total_score"] = alpha_score(data)
            data["elimination_passed"] = passed
            data["elimination_stages"] = stages
        return {"symbol": symbol, "data": data}
    finally:
        session.close()


@app.get("/scan/run")
def run_scan(force: bool = False):
    return run_full_pipeline(force=force)


@app.get("/scan/status")
def scan_status():
    session = SessionLocal()
    try:
        scored_count = session.query(ScoredStock).count()
        latest_scored = session.query(ScoredStock).order_by(ScoredStock.scored_at.desc()).first()
        return {
            "status": "operational",
            "scored_stocks": scored_count,
            "last_run": str(latest_scored.scored_at) if latest_scored else None
        }
    finally:
        session.close()


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
        ranked = get_scored_stocks_from_db(session, limit=500)
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
        ranked = get_scored_stocks_from_db(session, limit=500)
        return {"signals": ranked[:50]}
    finally:
        session.close()
