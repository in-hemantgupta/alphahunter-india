"""Risk Engine: portfolio risk monitoring and constraint checking.
Provides beta exposure, sector neutrality, volatility targeting,
max factor exposure, and correlation monitoring.
"""
import math
from datetime import datetime, date, timedelta
from collections import defaultdict

import numpy as np
import yfinance as yf
import pandas as pd

from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.models.stock import Stock
from app.scoring.alpha_engine import LAYER_WEIGHTS


_NIFTY_50_TICKER = "^NSEI"


def get_portfolio_holdings():
    """Get current portfolio holdings from ScoredStock (top 50)."""
    session = SessionLocal()
    try:
        stocks = session.query(ScoredStock).order_by(ScoredStock.total_score.desc()).limit(50).all()
        return [s.symbol for s in stocks]
    finally:
        session.close()


def compute_beta(symbol, period="1y"):
    """Compute stock beta vs Nifty 50 using yfinance."""
    try:
        stock = yf.Ticker(symbol + ".NS")
        nifty = yf.Ticker(_NIFTY_50_TICKER)
        end = datetime.now()
        start = end - timedelta(days=365 if period == "1y" else 180)
        s_hist = stock.history(start=start, end=end, auto_adjust=True)
        n_hist = nifty.history(start=start, end=end, auto_adjust=True)
        if s_hist.empty or n_hist.empty or len(s_hist) < 30:
            return 1.0
        s_rets = s_hist["Close"].pct_change().dropna()
        n_rets = n_hist["Close"].pct_change().dropna()
        aligned = pd.concat([s_rets, n_rets], axis=1).dropna()
        if len(aligned) < 20:
            return 1.0
        cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
        beta = cov[0, 1] / max(cov[1, 1], 1e-10)
        return round(float(beta), 2)
    except Exception:
        return 1.0


def portfolio_beta_exposure(holdings=None):
    """Compute portfolio-weighted beta."""
    if holdings is None:
        holdings = get_portfolio_holdings()
    if not holdings:
        return 0, []
    betas = []
    for symbol in holdings:
        beta = compute_beta(symbol)
        betas.append(beta)
    avg_beta = np.mean(betas) if betas else 0
    high_beta = sum(1 for b in betas if b > 1.5)
    return round(float(avg_beta), 2), [
        {"symbol": s, "beta": b}
        for s, b in zip(holdings, betas)
    ]


def _get_sector(symbol):
    """Get sector for a symbol from the database."""
    session = SessionLocal()
    try:
        stock = session.query(Stock).filter(Stock.symbol == symbol).first()
        return stock.sector if stock and stock.sector else "Unknown"
    finally:
        session.close()


def sector_neutrality(holdings=None):
    """Check sector concentration vs equal-weight benchmark."""
    if holdings is None:
        holdings = get_portfolio_holdings()
    if not holdings:
        return {}, []

    sectors = defaultdict(list)
    for symbol in holdings:
        sector = _get_sector(symbol)
        sectors[sector].append(symbol)

    n = len(holdings)
    equal_weight = 1.0 / max(len(sectors), 1) * 100
    sector_weights = {}
    deviations = []

    for sector, symbols in sorted(sectors.items()):
        weight = len(symbols) / n * 100
        deviation = weight - equal_weight
        sector_weights[sector] = {
            "count": len(symbols),
            "weight_pct": round(weight, 1),
            "deviation_pct": round(deviation, 1),
        }
        deviations.append(abs(deviation))

    max_deviation = max(deviations) if deviations else 0
    return {
        "equal_weight_benchmark_pct": round(equal_weight, 1),
        "max_deviation_pct": round(float(max_deviation), 1),
        "sectors": sector_weights,
        "passes_sector_limit": max_deviation <= 15.0,
    }, sectors


def volatility_targeting(holdings=None):
    """Compute volatility for each holding and flag over-volatile positions."""
    if holdings is None:
        holdings = get_portfolio_holdings()
    if not holdings:
        return {}, []

    results = []
    for symbol in holdings:
        try:
            stock = yf.Ticker(symbol + ".NS")
            hist = stock.history(period="6mo", auto_adjust=True)
            if hist.empty or len(hist) < 20:
                results.append({"symbol": symbol, "volatility": None, "exceeds_limit": False})
                continue
            returns = hist["Close"].pct_change().dropna()
            daily_vol = returns.std()
            annual_vol = daily_vol * math.sqrt(252)
            results.append({
                "symbol": symbol,
                "volatility": round(float(annual_vol * 100), 1),
                "exceeds_limit": annual_vol * 100 > 60,
            })
        except Exception:
            results.append({"symbol": symbol, "volatility": None, "exceeds_limit": False})

    exceeding = sum(1 for r in results if r.get("exceeds_limit"))
    return {"total": len(results), "exceeding_limit": exceeding}, results


def max_factor_exposure(holdings=None):
    """Measure portfolio exposure to each scoring factor."""
    if holdings is None:
        holdings = get_portfolio_holdings()
    if not holdings:
        return {}, []

    session = SessionLocal()
    try:
        stocks = session.query(ScoredStock).filter(
            ScoredStock.symbol.in_(holdings)
        ).all()

        factor_cols = {
            "quality": "quality_score",
            "growth": "growth_score",
            "technical": "technical_score",
            "microstructure": "microstructure_score",
            "value": "value_score",
            "lowvol": "lowvol_score",
            "forensic": "forensic_score",
        }

        factor_exposures = {}
        for name, col in factor_cols.items():
            values = [getattr(s, col) for s in stocks if getattr(s, col) is not None]
            if values:
                factor_exposures[name] = {
                    "mean": round(float(np.mean(values)), 1),
                    "std": round(float(np.std(values)), 1),
                    "min": round(float(min(values)), 1),
                    "max": round(float(max(values)), 1),
                }
            else:
                factor_exposures[name] = {"mean": None, "std": None, "min": None, "max": None}

        return factor_exposures, stocks
    finally:
        session.close()


def correlation_monitoring(holdings=None):
    """Compute pairwise correlation matrix for portfolio holdings."""
    if holdings is None:
        holdings = get_portfolio_holdings()
    if not holdings or len(holdings) < 2:
        return {}, []

    symbols = holdings[:20]
    prices = {}
    for symbol in symbols:
        try:
            stock = yf.Ticker(symbol + ".NS")
            hist = stock.history(period="6mo", auto_adjust=True)
            if not hist.empty and len(hist) > 20:
                prices[symbol] = hist["Close"]
        except Exception:
            pass

    if len(prices) < 2:
        return {}, []

    df = pd.DataFrame(prices)
    returns_df = df.pct_change().dropna()
    if returns_df.empty or len(returns_df.columns) < 2:
        return {}, []

    corr_matrix = returns_df.corr().values
    avg_corr = float(np.mean(corr_matrix[np.triu_indices_from(corr_matrix, k=1)]))
    high_corr_pairs = []
    symbols_list = list(prices.keys())
    for i in range(len(symbols_list)):
        for j in range(i + 1, len(symbols_list)):
            c = float(corr_matrix[i, j])
            if c > 0.80:
                high_corr_pairs.append({
                    "stock1": symbols_list[i],
                    "stock2": symbols_list[j],
                    "correlation": round(c, 2),
                })

    return {
        "avg_correlation": round(float(avg_corr), 2),
        "n_stocks": len(symbols_list),
        "high_corr_pairs_count": len(high_corr_pairs),
        "high_corr_pairs": high_corr_pairs[:10],
    }, symbols_list


def full_risk_report(holdings=None):
    """Generate comprehensive portfolio risk report."""
    if holdings is None:
        holdings = get_portfolio_holdings()

    report = {
        "report_date": str(date.today()),
        "n_holdings": len(holdings),
        "beta_report": portfolio_beta_exposure(holdings)[0],
        "sector_report": sector_neutrality(holdings)[0],
        "volatility_report": volatility_targeting(holdings)[0],
        "factor_exposure": max_factor_exposure(holdings)[0],
        "correlation_report": correlation_monitoring(holdings)[0],
    }

    risk_flags = []
    if report["beta_report"] > 1.2:
        risk_flags.append(f"High beta ({report['beta_report']})")
    if report["sector_report"].get("max_deviation_pct", 0) > 15:
        risk_flags.append("Sector concentration exceed 15%")
    if report["volatility_report"].get("exceeding_limit", 0) > 5:
        risk_flags.append(f"{report['volatility_report']['exceeding_limit']} stocks exceed vol limit")

    report["risk_flags"] = risk_flags
    report["risk_count"] = len(risk_flags)
    report["passes_risk_check"] = len(risk_flags) == 0

    return report


def risk_score(data):
    """Legacy function: simple risk score for a single stock."""
    score = 0
    if (data.get("volatility") or 0) > 40:
        score += 40
    if (data.get("max_drawdown") or 0) > 30:
        score += 30
    if (data.get("beta") or 0) > 1.5:
        score += 30
    return score
