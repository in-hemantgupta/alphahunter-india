from fastapi import FastAPI

from app.api.stocks import router as stock_router

from app.services.pipeline import run_full_pipeline


app = FastAPI(

    title="QuantumAlpha India API"

)


@app.get("/")

def health():

    return {"status": "running"}


@app.get("/stocks")

def get_stocks():

    return {"stocks": []}


@app.get("/stock/{symbol}")

def get_stock(symbol: str):

    return {"symbol": symbol, "data": None}


@app.get("/scan/run")

def run_scan():

    result = run_full_pipeline()

    return result


@app.get("/portfolio/current")

def get_portfolio():

    return {"portfolio": []}


@app.get("/backtest/run")

def run_backtest():

    return {"status": "backtest initiated"}


@app.get("/agents/status")

def agents_status():

    return {"agents": "operational"}


@app.get("/ml/predictions")

def ml_predictions():

    return {"predictions": []}


@app.get("/signals/latest")

def latest_signals():

    return {"signals": []}


app.include_router(stock_router)
