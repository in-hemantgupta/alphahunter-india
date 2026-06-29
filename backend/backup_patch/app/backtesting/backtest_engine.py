import pandas as pd
from app.backtesting.historical_snapshot import load_snapshot

from app.backtesting.strategy_runner import run_strategy

from app.backtesting.portfolio_simulator import simulate_portfolio

from app.backtesting.metrics import cagr

from app.backtesting.drawdown_engine import max_drawdown


def run_backtest():

    dates = quarterly_dates(5)

    results = []

    for date in dates:

        snapshot = load_snapshot(date)

        stocks = run_strategy(snapshot)

        returns = simulate_portfolio(stocks)

        results.append(returns)

    return {

        "cagr": cagr(results),

        "max_drawdown": max_drawdown(results),

        "sharpe": calculate_sharpe(results)

    }
