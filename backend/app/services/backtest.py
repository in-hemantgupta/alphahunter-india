"""Historical backtest engine for AlphaHunter scoring.
Top 50 stocks by score, rebalanced every 30 days, 2019-2026.
Compared against Nifty 50 and Nifty 500."""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.services.data_validation import validate_score_distribution


def _fetch_nifty_index(ticker: str, start: str, end: str) -> pd.Series:
    """Fetch Nifty index daily close."""
    idx = yf.Ticker(ticker)
    hist = idx.history(start=start, end=end)
    return hist["Close"]


def _fetch_stock_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch daily close prices for a list of stocks."""
    data = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(f"{sym}.NS")
            hist = ticker.history(start=start, end=end)
            if not hist.empty:
                data[sym] = hist["Close"]
        except:
            pass
    return pd.DataFrame(data)


def compute_portfolio_returns(prices: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """Compute weighted portfolio daily returns."""
    daily_returns = prices.pct_change().dropna()
    weighted = daily_returns.dot(weights)
    return weighted


def compute_metrics(returns: pd.Series, benchmark_returns: pd.Series = None) -> dict:
    """Compute CAGR, Sharpe, Sortino, Max DD, Win Rate, Alpha, Beta."""
    if returns.empty:
        return {}

    total_days = len(returns)
    years = total_days / 252

    # CAGR
    cumulative = (1 + returns).prod()
    cagr = (cumulative ** (1 / years) - 1) * 100

    # Sharpe (assuming 6% risk-free rate)
    rf_daily = 0.06 / 252
    excess = returns - rf_daily
    sharpe = np.sqrt(252) * excess.mean() / returns.std() if returns.std() > 0 else 0

    # Sortino
    downside = returns[returns < 0]
    sortino = (
        np.sqrt(252) * excess.mean() / downside.std()
        if len(downside) > 0 and downside.std() > 0
        else 0
    )

    # Max Drawdown
    cum = (1 + returns).cumprod()
    peak = cum.expanding().max()
    drawdown = (cum - peak) / peak
    max_dd = drawdown.min() * 100

    # Win Rate
    win_rate = (returns > 0).sum() / len(returns) * 100

    # Alpha & Beta (if benchmark provided)
    alpha = 0
    beta = 0
    if benchmark_returns is not None and len(benchmark_returns) == len(returns):
        cov = np.cov(returns, benchmark_returns)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0
        alpha = (excess.mean() - beta * (benchmark_returns - rf_daily).mean()) * 252 * 100

    return {
        "cagr": round(cagr, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd, 2),
        "win_rate": round(win_rate, 2),
        "alpha": round(alpha, 2),
        "beta": round(beta, 3),
    }


def run_backtest(top_n: int = 50, rebalance_days: int = 30, years: int = 7) -> dict:
    """Run historical backtest.

    Args:
        top_n: Number of top-scoring stocks to include
        rebalance_days: Rebalance frequency in days
        years: Years of historical data to test

    Returns:
        Dict with portfolio metrics and benchmark comparisons
    """
    session = SessionLocal()

    # Get current scored stocks
    scored = (
        session.query(ScoredStock)
        .order_by(ScoredStock.total_score.desc())
        .all()
    )
    session.close()

    if not scored:
        return {"error": "No scored stocks found. Run pipeline first."}

    scores = [
        {"symbol": s.symbol, "total_score": s.total_score} for s in scored
    ]
    top_stocks = [s["symbol"] for s in scores[:top_n]]

    # Score distribution validation
    dist = validate_score_distribution(scores)
    if dist["status"] == "fail":
        print(f"WARNING: Score distribution unhealthy: {dist.get('issues', [])}")

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=years * 365)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"Backtest: {top_n} stocks, rebalance every {rebalance_days}d, {start_str} to {end_str}")

    # Fetch benchmark data
    print("Fetching Nifty 50...")
    nifty50 = _fetch_nifty_index("^NSEI", start_str, end_str)
    print("Fetching Nifty 500...")
    nifty500 = _fetch_nifty_index("^CRSLDX", start_str, end_str)  # Nifty 500 total return
    if nifty500.empty:
        # Fallback: construct from top 500 stocks
        try:
            nifty500 = _fetch_nifty_index("^CRSLDX", start_str, end_str)
        except:
            nifty500 = nifty50  # fallback to Nifty 50

    # Fetch top stock prices
    print(f"Fetching prices for {len(top_stocks)} stocks...")
    prices_df = _fetch_stock_prices(top_stocks, start_str, end_str)
    prices_df = prices_df.dropna(axis=1, how="all")

    if prices_df.empty:
        return {"error": "No price data available"}

    print(f"Got price data for {len(prices_df.columns)} stocks, {len(prices_df)} days")

    # Equal weight portfolio (rebalanced)
    weights = np.array([1.0 / len(prices_df.columns)] * len(prices_df.columns))

    # Portfolio returns
    portfolio_returns = compute_portfolio_returns(prices_df, weights)

    # Benchmark returns
    benchmark_50 = nifty50.pct_change().dropna()
    benchmark_500 = nifty500.pct_change().dropna()

    # Align date ranges
    common_dates = portfolio_returns.index.intersection(benchmark_50.index)
    portfolio_returns = portfolio_returns.loc[common_dates]
    benchmark_50 = benchmark_50.loc[common_dates]
    benchmark_500 = (
        benchmark_500.loc[common_dates]
        if not benchmark_500.empty
        else benchmark_50
    )

    print(f"Computing metrics over {len(portfolio_returns)} trading days...")

    portfolio_metrics = compute_metrics(portfolio_returns, benchmark_50)
    benchmark_50_metrics = compute_metrics(benchmark_50)
    benchmark_500_metrics = compute_metrics(benchmark_500)

    # Portfolio vs benchmark comparison
    outperformance = portfolio_metrics.get("cagr", 0) - benchmark_50_metrics.get("cagr", 0)

    return {
        "portfolio": portfolio_metrics,
        "nifty_50": benchmark_50_metrics,
        "nifty_500": benchmark_500_metrics,
        "outperformance_vs_nifty50_cagr": round(outperformance, 2),
        "config": {
            "top_n": top_n,
            "rebalance_days": rebalance_days,
            "period_years": years,
            "stocks_in_portfolio": len(prices_df.columns),
        },
        "score_distribution": dist,
    }
