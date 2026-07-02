from datetime import date
from collections import defaultdict

import numpy as np

from app.db.database import SessionLocal
from app.models.portfolio_position import PortfolioPosition
from app.models.score_snapshot import ScoreSnapshot
from app.portfolio.liquidity_tiers import is_liquid, compute_liquidity_score


class DriftDetector:
    def __init__(self, as_of=None):
        self.as_of = as_of or date.today()
        self.session = SessionLocal()
        self.MAX_SECTOR_PCT = 25
        self.MAX_STOCK_PCT = 5
        self.MAX_BETA = 1.2
        self.MIN_LIQUIDITY_SCORE = 1.0

    def sector_concentration_drift(self):
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == self.as_of
        ).all()
        sector_alloc = defaultdict(float)
        for p in positions:
            if p.allocation and p.sector:
                sector_alloc[p.sector] += p.allocation * 100
        drift = {}
        for sector, pct in sorted(sector_alloc.items()):
            if pct > self.MAX_SECTOR_PCT:
                drift[sector] = {
                    "actual_pct": round(pct, 2),
                    "limit_pct": self.MAX_SECTOR_PCT,
                    "breach_amount": round(pct - self.MAX_SECTOR_PCT, 2),
                }
        return drift

    def beta_drift(self):
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == self.as_of,
            PortfolioPosition.beta.isnot(None),
        ).all()
        total_alloc = sum(p.allocation for p in positions if p.allocation) or 0
        if total_alloc == 0:
            return {"portfolio_beta": 0, "max_beta": self.MAX_BETA, "is_breached": False}
        weighted_beta = (
            sum(p.beta * p.allocation for p in positions if p.allocation and p.beta) / total_alloc
        )
        return {
            "portfolio_beta": round(weighted_beta, 4),
            "max_beta": self.MAX_BETA,
            "is_breached": weighted_beta > self.MAX_BETA,
        }

    def factor_exposure_drift(self):
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == self.as_of
        ).all()
        symbols = [p.symbol for p in positions]
        if not symbols:
            return {}
        snapshots = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == self.as_of,
            ScoreSnapshot.symbol.in_(symbols),
        ).all()
        factors = [
            "quality_score", "growth_score", "technical_score",
            "value_score", "forensic_score", "microstructure_score",
            "lowvol_score",
        ]
        exposures = {}
        for f in factors:
            vals = [getattr(s, f) for s in snapshots if getattr(s, f) is not None]
            exposures[f] = round(float(np.mean(vals)), 2) if vals else None
        return exposures

    def position_size_drift(self):
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == self.as_of,
            PortfolioPosition.allocation.isnot(None),
        ).all()
        drift = {}
        for p in positions:
            pct = p.allocation * 100
            if pct > self.MAX_STOCK_PCT:
                drift[p.symbol] = {
                    "allocation_pct": round(pct, 2),
                    "limit_pct": self.MAX_STOCK_PCT,
                    "breach_amount": round(pct - self.MAX_STOCK_PCT, 2),
                }
        return drift

    def liquidity_deterioration(self):
        positions = self.session.query(PortfolioPosition).filter(
            PortfolioPosition.date == self.as_of
        ).all()
        illiquid = []
        below_threshold = 0
        for p in positions:
            if not is_liquid(p.symbol):
                illiquid.append(p.symbol)
            score = compute_liquidity_score(p.symbol)
            norm_score = min(score / 100.0 * 3, 3)
            if norm_score < self.MIN_LIQUIDITY_SCORE:
                below_threshold += 1
        return {
            "illiquid_symbols": illiquid,
            "illiquid_count": len(illiquid),
            "below_threshold_count": below_threshold,
            "min_liquidity_score": self.MIN_LIQUIDITY_SCORE,
        }

    def full_drift_report(self):
        sector = self.sector_concentration_drift()
        beta = self.beta_drift()
        factor = self.factor_exposure_drift()
        psize = self.position_size_drift()
        liquid = self.liquidity_deterioration()
        report = {
            "as_of": str(self.as_of),
            "sector_concentration": sector,
            "beta": beta,
            "factor_exposures": factor,
            "position_size": psize,
            "liquidity": liquid,
        }
        alerts = []
        for sec, data in sector.items():
            alerts.append(
                f"ALERT: Sector {sec} at {data['actual_pct']}% exceeds {data['limit_pct']}%"
            )
        if beta["is_breached"]:
            alerts.append(
                f"ALERT: Portfolio beta {beta['portfolio_beta']} exceeds {beta['max_beta']}"
            )
        for sym, data in psize.items():
            alerts.append(
                f"ALERT: Position {sym} at {data['allocation_pct']}% exceeds {data['limit_pct']}%"
            )
        for sym in liquid["illiquid_symbols"]:
            alerts.append(f"ALERT: {sym} is no longer liquid")
        report["alerts"] = alerts
        report["has_alerts"] = len(alerts) > 0
        return report

    def should_rebalance(self):
        sector = self.sector_concentration_drift()
        beta = self.beta_drift()
        psize = self.position_size_drift()
        liquid = self.liquidity_deterioration()
        reasons = []
        if sector:
            for s in sector:
                reasons.append(
                    f"Sector {s} at {sector[s]['actual_pct']}% exceeds {self.MAX_SECTOR_PCT}%"
                )
        if beta["is_breached"]:
            reasons.append(
                f"Portfolio beta {beta['portfolio_beta']} exceeds {self.MAX_BETA}"
            )
        if psize:
            for s in psize:
                reasons.append(
                    f"Position {s} at {psize[s]['allocation_pct']}% exceeds {self.MAX_STOCK_PCT}%"
                )
        if liquid["illiquid_count"] > 0:
            reasons.append(f"{liquid['illiquid_count']} position(s) no longer liquid")
        return {
            "should_rebalance": len(reasons) > 0,
            "reasons": reasons,
        }

    def close(self):
        self.session.close()
