"""Daily portfolio monitoring system. Tracks returns, risk, exposure."""
from datetime import date, timedelta
import numpy as np
from collections import defaultdict
from app.db.database import SessionLocal
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.portfolio_position import PortfolioPosition
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.stock import Stock
from app.models.rebalance_history import RebalanceHistory
from app.scoring.alpha_engine import LAYER_WEIGHTS
import yfinance as yf
from sqlalchemy import func, text
import json


class PortfolioMonitor:
    """Daily portfolio monitoring and reporting."""

    def __init__(self):
        self.session = SessionLocal()

    def get_nifty_benchmark(self, date_from, date_to):
        """Get Nifty 50 benchmark returns."""
        try:
            nf = yf.Ticker("^NSEI")
            hist = nf.history(start=date_from, end=date_to, auto_adjust=True)
            if not hist.empty:
                return hist["Close"].tolist()
        except Exception:
            pass
        return []

    def compute_portfolio_return(self, date_from, date_to):
        """Compute portfolio return over period."""
        positions_start = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date_from
        ).all()
        positions_end = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date_to
        ).all()

        if not positions_start or not positions_end:
            return 0.0

        p_start = {p.symbol: p.current_price for p in positions_start if p.current_price}
        p_end = {p.symbol: p.current_price for p in positions_end if p.current_price}

        common = set(p_start.keys()) & set(p_end.keys())
        if not common:
            return 0.0

        returns = [p_end[s] / p_start[s] - 1 for s in common if p_start[s] and p_start[s] > 0]
        return float(np.mean(returns)) if returns else 0.0

    def compute_sharpe(self, days=30):
        """Compute rolling Sharpe ratio over N days."""
        metrics = self.session.query(PortfolioMetrics).order_by(
            PortfolioMetrics.date.desc()
        ).limit(days + 10).all()

        if len(metrics) < days:
            return 0.0

        returns = [m.daily_return for m in metrics[:days] if m.daily_return is not None]
        if len(returns) < 5:
            return 0.0

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret == 0:
            return 0.0

        sharpe = mean_ret / std_ret * np.sqrt(252)
        return round(float(sharpe), 2)

    def compute_drawdown(self):
        """Compute current drawdown from peak."""
        metrics = self.session.query(PortfolioMetrics).order_by(
            PortfolioMetrics.date.asc()
        ).all()

        navs = [m.nav for m in metrics if m.nav is not None]
        if len(navs) < 2:
            return 0.0

        peak = max(navs)
        current = navs[-1]
        dd = (peak - current) / peak * 100
        return round(float(dd), 2)

    def compute_volatility(self, days=30):
        """Compute rolling volatility."""
        metrics = self.session.query(PortfolioMetrics).order_by(
            PortfolioMetrics.date.desc()
        ).limit(days + 5).all()

        returns = [m.daily_return for m in metrics[:days] if m.daily_return is not None]
        if len(returns) < 5:
            return 0.0

        vol = np.std(returns) * np.sqrt(252) * 100
        return round(float(vol), 2)

    def compute_turnover(self, days=30):
        """Compute annualized turnover over period."""
        rebalances = self.session.query(RebalanceHistory).filter(
            RebalanceHistory.date >= date.today() - timedelta(days=days)
        ).all()

        total_change = 0.0
        for r in rebalances:
            old = r.old_weight if r.old_weight else 0
            new = r.new_weight if r.new_weight else 0
            total_change += abs(new - old)

        annual_turnover = total_change * (365 / max(days, 1))
        return round(float(annual_turnover), 1)

    def compute_hit_rate(self, days=90):
        """Compute percentage of profitable positions."""
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date.today(),
            PortfolioPosition.pnl_pct.isnot(None),
        ).all()

        if not positions:
            return 0.0

        profitable = sum(1 for p in positions if p.pnl_pct > 0)
        return round(profitable / len(positions) * 100, 1)

    def sector_exposure(self):
        """Compute current sector exposure breakdown."""
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date.today()
        ).all()

        sectors = defaultdict(float)
        for p in positions:
            weight = p.allocation or 0
            sector = p.sector or "Unknown"
            sectors[sector] += weight

        return {s: round(w, 2) for s, w in sorted(sectors.items(), key=lambda x: -x[1])}

    def factor_exposure(self):
        """Compute portfolio factor exposure."""
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date.today()
        ).all()

        symbols = [p.symbol for p in positions]
        if not symbols:
            return {}

        snapshots = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == date.today(),
            ScoreSnapshot.symbol.in_(symbols),
        ).all()

        factors = ["quality", "growth", "technical",
                    "microstructure", "value", "lowvol", "forensic"]

        exposure = {}
        for f in factors:
            vals = []
            for s in snapshots:
                val = getattr(s, f"{f}_score", None)
                if val is not None:
                    vals.append(val)
            exposure[f] = round(float(np.mean(vals)), 1) if vals else 0

        return exposure

    def daily_report(self):
        """Generate complete daily monitoring report."""
        report = {
            "date": str(date.today()),
            "portfolio_return": self.compute_portfolio_return(
                date.today() - timedelta(days=1), date.today()
            ),
            "sharpe_30d": self.compute_sharpe(30),
            "sharpe_90d": self.compute_sharpe(90),
            "drawdown": self.compute_drawdown(),
            "volatility_30d": self.compute_volatility(30),
            "turnover_annual": self.compute_turnover(30),
            "hit_rate": self.compute_hit_rate(),
            "sector_exposure": self.sector_exposure(),
            "factor_exposure": self.factor_exposure(),
        }
        return report

    def close(self):
        self.session.close()
