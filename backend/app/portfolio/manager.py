from datetime import date, timedelta
from collections import defaultdict

from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.stock import Stock

from app.portfolio.regime import detect_regime, get_regime
from app.portfolio.liquidity_tiers import get_market_cap_tier, get_liquidity_allocation_limit, is_liquid
from app.portfolio.entry_filters import check_entry
from app.portfolio.exit_rules import check_exit
from app.portfolio.position_sizing import size_position
from app.portfolio.conviction import compute_conviction_weight, normalize_conviction
from app.portfolio.optimizer import optimize_weights
from app.portfolio.execution import simulate_rebalance_cost


class PortfolioManager:
    """Ties all portfolio construction modules together."""

    def __init__(self, as_of=None):
        self.as_of = as_of or date.today()
        self.regime = None
        self.portfolio = {}
        self.holdings = {}
        self.entry_prices = {}
        self.rebalance_log = []

    def build_portfolio(self, top_n=50):
        """Full portfolio construction pipeline."""
        # Step 1: Detect regime
        self.regime = get_regime(self.as_of)
        regime_name = self.regime["regime"]

        # Step 2: Load scored stocks
        session = SessionLocal()
        scored = session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == self.as_of
        ).order_by(ScoreSnapshot.total_score.desc()).all()

        if not scored:
            scored = session.query(ScoredStock).order_by(ScoredStock.total_score.desc()).all()

        # Step 3: Enrich with sector, market cap, price data
        candidates = []
        sectors_map = {}
        market_caps = {}
        price_map = {}

        for s in scored:
            stock = session.query(Stock).filter(Stock.symbol == s.symbol).first()
            sector = stock.sector if stock else "Unknown"
            market_cap = stock.market_cap if stock else None
            sectors_map[s.symbol] = sector
            market_caps[s.symbol] = market_cap

            # Latest price
            pr = session.query(PriceHistory).filter(
                PriceHistory.symbol == s.symbol
            ).order_by(PriceHistory.date.desc()).first()
            price_map[s.symbol] = pr.close if pr else None

            candidates.append({
                "symbol": s.symbol,
                "score": s.total_score or 0,
                "confidence": s.confidence_score or 0.5,
                "sector": sector,
                "market_cap": market_cap,
                "beta": 1.0,
                "price": price_map.get(s.symbol),
            })

        session.close()

        # Step 4: Liquidity filter (Tier C allocation limit)
        tier_counts = defaultdict(int)
        tier_max = {"A": top_n, "B": top_n, "C": int(top_n * 0.15)}
        filtered = []
        for c in candidates:
            tier = get_market_cap_tier(c["symbol"])
            c["tier"] = tier
            if tier_counts[tier] < tier_max.get(tier, top_n):
                if is_liquid(c["symbol"]):
                    filtered.append(c)
                    tier_counts[tier] += 1

        candidates = filtered

        # Step 5: Rank by score
        candidates.sort(key=lambda x: -x["score"])
        total = len(candidates)

        # Step 6: Apply entry filters
        buy_list = []
        for i, c in enumerate(candidates[:top_n * 2]):
            score_rank = (i / total) * 100 if total > 0 else 0

            session = SessionLocal()
            price_rows = session.query(PriceHistory.close).filter(
                PriceHistory.symbol == c["symbol"],
                PriceHistory.date <= self.as_of,
            ).order_by(PriceHistory.date.desc()).limit(200).all()
            session.close()
            prices = [r[0] for r in price_rows if r[0] is not None]

            passed, reasons = check_entry(
                symbol=c["symbol"],
                score_rank=score_rank,
                price_data=prices,
                sector=c["sector"],
                volume_ratio=None,
            )

            if passed:
                buy_list.append(c)

            if len(buy_list) >= top_n:
                break

        # Step 7: Position sizing with conviction weighting
        sized = []
        for c in buy_list:
            raw = compute_conviction_weight(c["score"], c["confidence"])
            size = size_position(c["score"], c["confidence"], c["symbol"])
            sized.append({
                **c,
                "conviction_weight": raw,
                "position_size": size,
            })

        # Step 8: Portfolio optimization
        self.portfolio = optimize_weights(
            sized,
            regime_name,
            correlation_matrix=None,
        )

        return self.portfolio

    def rebalance(self, current_holdings=None, current_prices=None):
        """Calculate rebalance trades with costs."""
        if current_holdings is None:
            current_holdings = self.holdings
        if current_prices is None:
            current_prices = {}

        session = SessionLocal()
        market_cap_map = {}
        for sym in set(list(current_holdings.keys()) + list(self.portfolio.keys())):
            stock = session.query(Stock).filter(Stock.symbol == sym).first()
            market_cap_map[sym] = stock.market_cap if stock else None
        session.close()

        turnover_pct, avg_cost = simulate_rebalance_cost(
            current_holdings, self.portfolio,
            current_prices, market_cap_map,
        )

        self.rebalance_log.append({
            "date": self.as_of,
            "regime": self.regime["regime"] if self.regime else None,
            "n_holdings": len(self.portfolio),
            "turnover_pct": turnover_pct,
            "avg_cost_bps": avg_cost,
        })

        return {
            "target_weights": self.portfolio,
            "turnover_pct": turnover_pct,
            "avg_cost_bps": avg_cost,
        }


def run_portfolio_engine(as_of=None):
    """Convenience function to run full pipeline."""
    mgr = PortfolioManager(as_of)
    portfolio = mgr.build_portfolio(top_n=50)
    result = mgr.rebalance()
    return {
        "date": str(mgr.as_of),
        "regime": mgr.regime,
        "portfolio": portfolio,
        "rebalance": result,
        "log": mgr.rebalance_log,
    }
