from datetime import date, timedelta
import json
import numpy as np
import yfinance as yf
from sqlalchemy import text
from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.rebalance_history import RebalanceHistory
from app.models.stock import Stock


class AttributionEngine:
    def __init__(self):
        self.session = SessionLocal()

    def stock_selection_alpha(self, portfolio_returns_dict, benchmark_return, holdings_weights):
        total_weight = sum(holdings_weights.values()) or 1.0
        actual_return = sum(
            portfolio_returns_dict.get(sym, 0.0) * w / total_weight
            for sym, w in holdings_weights.items()
        )
        selection_alpha = actual_return - benchmark_return
        details = {}
        for sym, w in holdings_weights.items():
            stock_ret = portfolio_returns_dict.get(sym, 0.0)
            contribution = stock_ret * w / total_weight
            details[sym] = {
                "weight": round(w / total_weight, 4),
                "stock_return": round(stock_ret, 6),
                "contribution": round(contribution, 6),
                "excess": round(stock_ret - benchmark_return, 6),
            }
        return {
            "actual_return": round(actual_return, 6),
            "benchmark_return": round(benchmark_return, 6),
            "selection_alpha": round(selection_alpha, 6),
            "details": details,
        }

    def sector_allocation_alpha(self, sector_weights, sector_returns, benchmark_sector_weights):
        all_sectors = set(sector_weights.keys()) | set(benchmark_sector_weights.keys())
        allocation_alpha = 0.0
        details_per_sector = {}
        for sector in all_sectors:
            w_port = sector_weights.get(sector, 0.0)
            w_bench = benchmark_sector_weights.get(sector, 0.0)
            r_bench = sector_returns.get(sector, 0.0)
            effect = (w_port - w_bench) * r_bench
            allocation_alpha += effect
            details_per_sector[sector] = {
                "portfolio_weight": round(w_port, 4),
                "benchmark_weight": round(w_bench, 4),
                "sector_return": round(r_bench, 6),
                "allocation_effect": round(effect, 6),
            }
        return {
            "allocation_alpha": round(allocation_alpha, 6),
            "details_per_sector": details_per_sector,
        }

    def timing_alpha(self, portfolio_returns_by_day, benchmark_returns_by_day):
        days = min(len(portfolio_returns_by_day), len(benchmark_returns_by_day))
        if days < 5:
            return {"timing_alpha": 0.0, "correlation": 0.0}
        port_rets = np.array(list(portfolio_returns_by_day.values())[-days:])
        bench_rets = np.array(list(benchmark_returns_by_day.values())[-days:])
        beta_changes = np.diff(port_rets / (bench_rets + 1e-8), prepend=0)
        market_direction = np.sign(bench_rets)
        if np.std(beta_changes) == 0 or np.std(market_direction) == 0:
            return {"timing_alpha": 0.0, "correlation": 0.0}
        corr = float(np.corrcoef(beta_changes, market_direction)[0, 1])
        timing_alpha = corr * float(np.std(port_rets)) * 0.01
        return {
            "timing_alpha": round(timing_alpha, 6),
            "correlation": round(corr, 4),
        }

    def factor_exposure_alpha(self, factor_exposures, factor_returns):
        factor_alpha = 0.0
        details = {}
        for factor, exposure in factor_exposures.items():
            ret = factor_returns.get(factor, 0.0)
            contribution = exposure * ret
            factor_alpha += contribution
            details[factor] = {
                "exposure": round(exposure, 4),
                "factor_return": round(ret, 6),
                "contribution": round(contribution, 6),
            }
        return {
            "factor_alpha": round(factor_alpha, 6),
            "details": details,
        }

    def beta_contribution(self, portfolio_beta, benchmark_return):
        contribution = portfolio_beta * benchmark_return
        return {
            "beta_contribution": round(contribution, 6),
            "portfolio_beta": round(portfolio_beta, 4),
            "benchmark_return": round(benchmark_return, 6),
        }

    def execution_drag(self, trades, cost_model):
        if not trades:
            return {"total_cost_bps": 0.0, "avg_cost_per_trade": 0.0, "total_drag_pct": 0.0}
        total_cost_bps = 0.0
        trade_costs = []
        for trade in trades:
            cap_tier = trade.get("tier", "D")
            bps = cost_model.get(cap_tier, 100)
            notional = abs(trade.get("notional", 0))
            cost_bps = bps
            total_cost_bps += cost_bps
            trade_costs.append(cost_bps)
        avg_cost = np.mean(trade_costs) if trade_costs else 0.0
        total_drag_pct = total_cost_bps / 10000
        return {
            "total_cost_bps": round(float(total_cost_bps), 2),
            "avg_cost_per_trade": round(float(avg_cost), 2),
            "total_drag_pct": round(float(total_drag_pct), 6),
        }

    def turnover_drag(self, turnover_pct, avg_cost_bps):
        drag_pct = turnover_pct * avg_cost_bps / 10000
        return {
            "turnover_pct": round(turnover_pct, 2),
            "avg_cost_bps": round(avg_cost_bps, 2),
            "drag_pct": round(drag_pct, 6),
        }

    def _load_benchmark_return(self, as_of_date, lookback_days=30):
        prev_date = as_of_date - timedelta(days=lookback_days)
        metrics = self.session.query(PortfolioMetrics).filter(
            PortfolioMetrics.date >= prev_date,
            PortfolioMetrics.date <= as_of_date,
        ).order_by(PortfolioMetrics.date.asc()).all()
        if len(metrics) >= 2:
            start_nav = metrics[0].benchmark_nav or 1.0
            end_nav = metrics[-1].benchmark_nav or 1.0
            if start_nav > 0:
                return end_nav / start_nav - 1
        try:
            ticker = yf.Ticker("^NSEI")
            hist = ticker.history(start=as_of_date - timedelta(days=lookback_days), end=as_of_date + timedelta(days=1), auto_adjust=True)
            if len(hist) >= 2:
                return float(hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1)
        except Exception:
            pass
        return 0.0

    def _load_portfolio_positions(self, as_of_date):
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == as_of_date,
        ).all()
        if not positions:
            prev = self.session.query(PortfolioPosition).filter(
                PortfolioPosition.date < as_of_date,
            ).order_by(PortfolioPosition.date.desc()).first()
            if prev:
                positions = self.session.query(PortfolioPosition).filter(
                    PortfolioPosition.date == prev.date,
                ).all()
        return positions

    def _load_factor_exposures(self, as_of_date, positions):
        exposures = {}
        total_score = 0.0
        for pos in positions:
            snapshot = self.session.query(ScoreSnapshot).filter(
                ScoreSnapshot.symbol == pos.symbol,
                ScoreSnapshot.date <= as_of_date,
            ).order_by(ScoreSnapshot.date.desc()).first()
            if not snapshot:
                continue
            layer_json = snapshot.layer_breakdown_json
            if layer_json:
                try:
                    layers = json.loads(layer_json)
                    for factor, value in layers.items():
                        normalized = factor.lower().replace(" ", "_").replace("-", "_")
                        exposures.setdefault(normalized, 0.0)
                        exposures[normalized] += (value or 0) * (pos.allocation or 0)
                except (json.JSONDecodeError, TypeError):
                    pass
            total_score += snapshot.total_score or 0
        if total_score > 0:
            exposures = {k: v / total_score for k, v in exposures.items()}
        return exposures

    def _load_sector_data(self, as_of_date, positions):
        sector_weights = {}
        sector_returns = {}
        for pos in positions:
            sector = pos.sector or "Unknown"
            sector_weights[sector] = sector_weights.get(sector, 0.0) + (pos.allocation or 0)
            sector_returns[sector] = sector_returns.get(sector, 0.0)
        total = sum(sector_weights.values()) or 1.0
        sector_weights = {k: v / total for k, v in sector_weights.items()}
        nifty_sector_weights = {
            "Financial Services": 0.35,
            "Information Technology": 0.15,
            "Energy": 0.12,
            "Consumer Staples": 0.08,
            "Automobile": 0.07,
            "Pharmaceuticals": 0.06,
            "Metals & Mining": 0.05,
            "Consumer Discretionary": 0.04,
            "Healthcare": 0.03,
            "Telecommunications": 0.02,
            "Utilities": 0.02,
            "Unknown": 0.01,
        }
        return sector_weights, sector_returns, nifty_sector_weights

    def _load_trades(self, as_of_date):
        trades = self.session.query(RebalanceHistory).filter(
            RebalanceHistory.date == as_of_date,
        ).all()
        trade_list = []
        for t in trades:
            notional = abs((t.new_weight or 0) - (t.old_weight or 0))
            stock = self.session.query(Stock).filter(
                Stock.symbol == t.symbol,
            ).first()
            mc = stock.market_cap if stock else None
            if mc is None:
                tier = "D"
            elif mc >= 10000e7:
                tier = "A"
            elif mc >= 1000e7:
                tier = "B"
            elif mc >= 100e7:
                tier = "C"
            else:
                tier = "D"
            trade_list.append({
                "symbol": t.symbol,
                "notional": notional,
                "tier": tier,
            })
        return trade_list

    def full_attribution(self, as_of_date):
        positions = self._load_portfolio_positions(as_of_date)
        benchmark_return = self._load_benchmark_return(as_of_date)

        if not positions:
            result = {
                "date": str(as_of_date),
                "total_portfolio_return": 0.0,
                "benchmark_return": round(benchmark_return, 6),
                "excess_return": -benchmark_return,
                "attribution": {
                    "stock_selection_alpha": self.stock_selection_alpha({}, benchmark_return, {}),
                    "sector_allocation_alpha": self.sector_allocation_alpha({}, {}, {}),
                    "timing_alpha": self.timing_alpha({}, {}),
                    "factor_exposure_alpha": self.factor_exposure_alpha({}, {}),
                    "beta_contribution": self.beta_contribution(0.0, benchmark_return),
                    "execution_drag": self.execution_drag([], {}),
                    "turnover_drag": self.turnover_drag(0.0, 0.0),
                },
                "explained_return": 0.0,
                "unexplained_remainder": -benchmark_return,
                "is_balanced": False,
            }
            return result

        portfolio_returns = {}
        holdings_weights = {}
        total_allocation = sum(p.allocation or 0 for p in positions) or 1.0
        for pos in positions:
            holdings_weights[pos.symbol] = (pos.allocation or 0) / total_allocation
            portfolio_returns[pos.symbol] = pos.pnl_pct / 100.0 if pos.pnl_pct else 0.0

        sector_weights, sector_returns, nifty_sector_weights = self._load_sector_data(as_of_date, positions)
        factor_exposures = self._load_factor_exposures(as_of_date, positions)
        trades = self._load_trades(as_of_date)

        cost_model = {"A": 20, "B": 60, "C": 120, "D": 200}
        total_turnover = sum(
            abs((t.new_weight or 0) - (t.old_weight or 0)) for t in
            self.session.query(RebalanceHistory).filter(
                RebalanceHistory.date >= as_of_date - timedelta(days=30),
            ).all()
        ) * (365.0 / 30)

        portfolio_beta = np.mean([p.beta or 1.0 for p in positions]) if positions else 1.0
        avg_cost_bps = 60.0

        ss = self.stock_selection_alpha(portfolio_returns, benchmark_return, holdings_weights)
        sa = self.sector_allocation_alpha(sector_weights, sector_returns, nifty_sector_weights)
        ta = self.timing_alpha({}, {})
        fa = self.factor_exposure_alpha(factor_exposures, {})
        bc = self.beta_contribution(portfolio_beta, benchmark_return)
        ed = self.execution_drag(trades, cost_model)
        td = self.turnover_drag(total_turnover, avg_cost_bps)

        explained_return = (
            ss["selection_alpha"]
            + sa["allocation_alpha"]
            + ta["timing_alpha"]
            + fa["factor_alpha"]
            + bc["beta_contribution"]
            - ed["total_drag_pct"]
            - td["drag_pct"]
        )

        total_portfolio_return = ss["actual_return"]
        excess_return = total_portfolio_return - benchmark_return
        unexplained = excess_return - explained_return

        return {
            "date": str(as_of_date),
            "total_portfolio_return": round(total_portfolio_return, 6),
            "benchmark_return": round(benchmark_return, 6),
            "excess_return": round(excess_return, 6),
            "attribution": {
                "stock_selection_alpha": ss,
                "sector_allocation_alpha": sa,
                "timing_alpha": ta,
                "factor_exposure_alpha": fa,
                "beta_contribution": bc,
                "execution_drag": ed,
                "turnover_drag": td,
            },
            "explained_return": round(explained_return, 6),
            "unexplained_remainder": round(unexplained, 6),
            "is_balanced": abs(excess_return - explained_return) < 0.001,
        }

    def close(self):
        self.session.close()
