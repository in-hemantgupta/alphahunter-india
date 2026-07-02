"""Live portfolio engine. Daily workflow orchestrator."""
from datetime import date, timedelta
import numpy as np
from collections import defaultdict
from app.db.database import SessionLocal
from app.models.portfolio_position import PortfolioPosition
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.score_snapshot import ScoreSnapshot
from app.models.stock import Stock
from app.models.price_history import PriceHistory
from app.models.rebalance_history import RebalanceHistory
from app.portfolio.regime import get_regime
from app.portfolio.manager import PortfolioManager
from app.services.audit_logger import AuditLogger
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


class LivePortfolio:
    """Daily portfolio management system."""

    def __init__(self):
        self.session = SessionLocal()
        self.today = date.today()
        self.regime = None
        self.audit = AuditLogger()

    def refresh_market_data(self, lookback_days=5):
        """Refresh prices for stocks that need it (portfolio holdings + recent tops)."""
        previous = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date < self.today
        ).order_by(PortfolioPosition.date.desc()).first()
        prev_date = previous.date if previous else self.today - timedelta(days=1)

        holdings = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == prev_date
        ).all()
        portfolio_symbols = {p.symbol for p in holdings}

        top_ranked = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == self.today
        ).order_by(ScoreSnapshot.total_score.desc()).limit(100).all()
        top_symbols = {s.symbol for s in top_ranked}

        need_update = portfolio_symbols | top_symbols

        for symbol in need_update:
            existing = self.session.query(PriceHistory).filter(
                PriceHistory.symbol == symbol,
                PriceHistory.date == self.today
            ).first()
            if existing:
                continue
            try:
                ticker = yf.Ticker(symbol + ".NS")
                hist = ticker.history(period="5d", auto_adjust=True)
                if not hist.empty:
                    for _, row in hist.iterrows():
                        row_date = row.name.date() if hasattr(row.name, 'date') else self.today
                        if self.session.query(PriceHistory).filter(
                            PriceHistory.symbol == symbol,
                            PriceHistory.date == row_date
                        ).first():
                            continue
                        ph = PriceHistory(
                            symbol=symbol,
                            date=row_date,
                            open=float(row["Open"]),
                            high=float(row["High"]),
                            low=float(row["Low"]),
                            close=float(row["Close"]),
                            volume=int(row["Volume"]) if "Volume" in row else 0,
                        )
                        self.session.add(ph)
                    self.session.commit()
            except Exception as e:
                logger.debug(f"Price refresh failed for {symbol}: {e}")

    def run_scoring(self):
        """07:30 — Run full scoring pipeline."""
        from app.services.pipeline import run_full_pipeline
        run_full_pipeline()

    def rank_universe(self):
        """08:00 — Rank entire universe and store positions."""
        scored = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == self.today
        ).order_by(ScoreSnapshot.total_score.desc()).all()

        if not scored:
            scored = self.session.query(ScoreSnapshot).order_by(
                ScoreSnapshot.total_score.desc()
            ).all()

        self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == self.today
        ).delete()

        for rank, s in enumerate(scored, 1):
            stock = self.session.query(Stock).filter(
                Stock.symbol == s.symbol
            ).first()
            ph = self.session.query(PriceHistory).filter(
                PriceHistory.symbol == s.symbol,
                PriceHistory.date == self.today
            ).order_by(PriceHistory.date.desc()).first()
            if not ph:
                ph = self.session.query(PriceHistory).filter(
                    PriceHistory.symbol == s.symbol
                ).order_by(PriceHistory.date.desc()).first()

            pos = PortfolioPosition(
                symbol=s.symbol,
                date=self.today,
                score=s.total_score or 0,
                rank=rank,
                current_price=ph.close if ph else None,
                sector=stock.sector if stock else "Unknown",
                confidence=s.confidence_score or 0.5,
                regime=self.regime["regime"] if self.regime else None,
                beta=1.0,
            )
            self.session.add(pos)

        self.session.commit()
        logger.info(f"Ranked {len(scored)} stocks for {self.today}")

    def generate_portfolio(self):
        """08:10 — Generate portfolio from top-ranked stocks."""
        mgr = PortfolioManager(self.today)
        portfolio = mgr.build_portfolio(top_n=50)
        rebalance = mgr.rebalance()
        return portfolio, rebalance

    def generate_trade_list(self, portfolio):
        """08:15 — Generate trade list: BUY new, SELL dropped, HOLD kept."""
        prev_positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date < self.today
        ).order_by(PortfolioPosition.date.desc()).all()

        prev_holdings = {}
        if prev_positions:
            prev_date = prev_positions[0].date
            prev_holdings = {
                p.symbol: p
                for p in self.session.query(PortfolioPosition).filter(
                    PortfolioPosition.date == prev_date
                ).all()
            }

        target_symbols = set(portfolio.keys())
        current_symbols = set(prev_holdings.keys())

        trades = []
        for symbol in target_symbols - current_symbols:
            trades.append({
                "symbol": symbol,
                "action": "BUY",
                "target_weight": round(portfolio[symbol] * 100, 2),
                "reason": "new_entry",
            })
        for symbol in current_symbols - target_symbols:
            trades.append({
                "symbol": symbol,
                "action": "SELL",
                "target_weight": 0,
                "reason": "dropped",
            })
        for symbol in target_symbols & current_symbols:
            trades.append({
                "symbol": symbol,
                "action": "HOLD",
                "target_weight": round(portfolio[symbol] * 100, 2),
                "reason": "maintain",
            })

        return trades

    def compute_metrics(self, portfolio):
        """Compute daily portfolio metrics with real NAV and benchmark returns."""
        total_nav = sum(portfolio.values())

        try:
            nf = yf.Ticker("^NSEI")
            hist = nf.history(start=self.today - timedelta(days=5), end=self.today + timedelta(days=1), auto_adjust=True)
            if not hist.empty:
                benchmark_nav = float(hist["Close"].iloc[-1])
            else:
                benchmark_nav = 1.0
        except Exception:
            benchmark_nav = 1.0

        prev = self.session.query(PortfolioMetrics).order_by(
            PortfolioMetrics.date.desc()
        ).first()
        prev_nav = prev.nav if prev and prev.nav else None
        prev_benchmark = prev.benchmark_nav if prev and prev.benchmark_nav else None

        daily_return = (total_nav / prev_nav - 1) if prev_nav and prev_nav > 0 else 0.0
        benchmark_return = (benchmark_nav / prev_benchmark - 1) if prev_benchmark and prev_benchmark > 0 else 0.0

        trailing = self.session.query(PortfolioMetrics).order_by(
            PortfolioMetrics.date.desc()
        ).limit(95).all()
        trailing_returns = [m.daily_return for m in trailing if m.daily_return is not None]

        sharpe_30d = 0.0
        sharpe_90d = 0.0
        if len(trailing_returns) >= 30:
            r30 = trailing_returns[:30]
            if np.std(r30) > 0:
                sharpe_30d = round(float(np.mean(r30) / np.std(r30) * np.sqrt(252)), 2)
        if len(trailing_returns) >= 90:
            r90 = trailing_returns[:90]
            if np.std(r90) > 0:
                sharpe_90d = round(float(np.mean(r90) / np.std(r90) * np.sqrt(252)), 2)

        navs = [m.nav for m in trailing if m.nav is not None]
        drawdown = 0.0
        if len(navs) >= 2:
            peak = max(navs)
            current = navs[0]
            drawdown = round(float((peak - current) / peak * 100), 2)

        vol_30d = 0.0
        if len(trailing_returns) >= 30:
            r30 = trailing_returns[:30]
            vol_30d = round(float(np.std(r30) * np.sqrt(252) * 100), 2)

        turnover = 0.0
        rebalances = self.session.query(RebalanceHistory).filter(
            RebalanceHistory.date >= self.today - timedelta(days=30)
        ).all()
        if rebalances:
            total_change = sum(abs((r.new_weight or 0) - (r.old_weight or 0)) for r in rebalances)
            turnover = round(float(total_change * (365 / 30)), 1)

        alpha = round(float(daily_return - benchmark_return), 4)

        self.session.merge(PortfolioMetrics(
            date=self.today,
            nav=round(total_nav, 4),
            benchmark_nav=round(benchmark_nav, 4),
            daily_return=round(daily_return, 6),
            benchmark_return=round(benchmark_return, 6),
            alpha=alpha,
            sharpe_30d=sharpe_30d,
            sharpe_90d=sharpe_90d,
            drawdown=drawdown,
            volatility_30d=vol_30d,
            turnover_annual=turnover,
            n_holdings=len(portfolio),
        ))
        self.session.commit()

    def full_daily_cycle(self):
        """Run the complete daily portfolio cycle."""
        import time
        logger.info("=== Live Portfolio Daily Cycle ===")
        logger.info("07:00 — Refreshing market data...")
        _t = time.time()
        self.refresh_market_data()
        self.audit.log_success("refresh_market_data", "portfolio", source="live_portfolio", duration_ms=int((time.time()-_t)*1000))
        logger.info("07:30 — Running scoring pipeline...")
        _t = time.time()
        self.run_scoring()
        self.audit.log_success("run_scoring", "portfolio", source="live_portfolio", duration_ms=int((time.time()-_t)*1000))
        logger.info("08:00 — Ranking universe...")
        _t = time.time()
        self.regime = get_regime(self.today)
        self.rank_universe()
        self.audit.log_success("rank_universe", "portfolio", source="live_portfolio", duration_ms=int((time.time()-_t)*1000))
        logger.info("08:10 — Generating portfolio...")
        _t = time.time()
        portfolio, rebalance = self.generate_portfolio()
        self.audit.log_success("generate_portfolio", "portfolio", source="live_portfolio", duration_ms=int((time.time()-_t)*1000))
        logger.info("08:15 — Generating trade list...")
        _t = time.time()
        trades = self.generate_trade_list(portfolio)
        self.audit.log_success("generate_trade_list", "portfolio", source="live_portfolio", duration_ms=int((time.time()-_t)*1000))
        _t = time.time()
        self.compute_metrics(portfolio)
        self.audit.log_success("compute_metrics", "portfolio", source="live_portfolio", duration_ms=int((time.time()-_t)*1000))
        logger.info(f"Done. Portfolio: {len(portfolio)} positions, Regime: {self.regime}")
        return {
            "date": str(self.today),
            "regime": self.regime["regime"] if self.regime else None,
            "n_positions": len(portfolio),
            "portfolio": portfolio,
            "trades": trades,
            "rebalance": rebalance,
        }

    def close(self):
        self.audit.close()
        self.session.close()
