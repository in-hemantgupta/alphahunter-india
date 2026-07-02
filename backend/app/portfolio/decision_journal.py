import json
from datetime import date, timedelta
from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.models.trade_decision_log import TradeDecisionLog


class DecisionJournal:
    def __init__(self):
        self.session = SessionLocal()
        self._ensure_table()

    def _ensure_table(self):
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS trade_decision_log (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    action VARCHAR(10) NOT NULL,
                    score FLOAT,
                    rank INTEGER,
                    confidence FLOAT,
                    factors_responsible TEXT,
                    exit_trigger VARCHAR(30),
                    allocation FLOAT,
                    price FLOAT,
                    reason TEXT,
                    sector VARCHAR(100),
                    regime VARCHAR(30),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tdl_date ON trade_decision_log(date)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tdl_symbol ON trade_decision_log(symbol)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tdl_action ON trade_decision_log(action)"))
            conn.commit()

    def log_decision(self, date, symbol, action, score=None, rank=None, confidence=None, factors=None, exit_trigger=None, allocation=None, price=None, reason=None, sector=None, regime=None):
        factors_json = json.dumps(factors) if factors else None
        self.session.execute(text("""
            INSERT INTO trade_decision_log
                (date, symbol, action, score, rank, confidence, factors_responsible,
                 exit_trigger, allocation, price, reason, sector, regime)
            VALUES
                (:date, :symbol, :action, :score, :rank, :confidence, :factors,
                 :exit_trigger, :allocation, :price, :reason, :sector, :regime)
        """), {
            "date": date,
            "symbol": symbol,
            "action": action,
            "score": score,
            "rank": rank,
            "confidence": confidence,
            "factors": factors_json,
            "exit_trigger": exit_trigger,
            "allocation": allocation,
            "price": price,
            "reason": reason,
            "sector": sector,
            "regime": regime,
        })
        self.session.commit()

    def log_buy(self, symbol, score, rank, confidence, factors, allocation, price, sector, regime, reason="new_entry"):
        self.log_decision(
            date=date.today(),
            symbol=symbol,
            action="BUY",
            score=score,
            rank=rank,
            confidence=confidence,
            factors=factors,
            allocation=allocation,
            price=price,
            sector=sector,
            regime=regime,
            reason=reason,
        )

    def log_sell(self, symbol, score=None, rank=None, exit_trigger=None, price=None, reason=None, sector=None):
        self.log_decision(
            date=date.today(),
            symbol=symbol,
            action="SELL",
            score=score,
            rank=rank,
            exit_trigger=exit_trigger,
            price=price,
            sector=sector,
            reason=reason,
        )

    def get_decisions(self, date=None, symbol=None, action=None, limit=100):
        query = self.session.query(TradeDecisionLog)
        if date:
            query = query.filter(TradeDecisionLog.date == date)
        if symbol:
            query = query.filter(TradeDecisionLog.symbol == symbol)
        if action:
            query = query.filter(TradeDecisionLog.action == action)
        rows = query.order_by(TradeDecisionLog.date.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "date": str(r.date),
                "symbol": r.symbol,
                "action": r.action,
                "score": r.score,
                "rank": r.rank,
                "confidence": r.confidence,
                "factors_responsible": json.loads(r.factors_responsible) if r.factors_responsible else None,
                "exit_trigger": r.exit_trigger,
                "allocation": r.allocation,
                "price": r.price,
                "reason": r.reason,
                "sector": r.sector,
                "regime": r.regime,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ]

    def get_recent_trades(self, days=7):
        cutoff = date.today() - timedelta(days=days)
        rows = self.session.query(TradeDecisionLog).filter(
            TradeDecisionLog.date >= cutoff,
            TradeDecisionLog.action.in_(["BUY", "SELL"]),
        ).order_by(TradeDecisionLog.date.desc()).all()
        return [
            {
                "id": r.id,
                "date": str(r.date),
                "symbol": r.symbol,
                "action": r.action,
                "score": r.score,
                "rank": r.rank,
                "exit_trigger": r.exit_trigger,
                "allocation": r.allocation,
                "price": r.price,
                "reason": r.reason,
                "sector": r.sector,
                "regime": r.regime,
            }
            for r in rows
        ]

    def get_symbol_history(self, symbol, limit=50):
        rows = self.session.query(TradeDecisionLog).filter(
            TradeDecisionLog.symbol == symbol,
        ).order_by(TradeDecisionLog.date.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "date": str(r.date),
                "symbol": r.symbol,
                "action": r.action,
                "score": r.score,
                "rank": r.rank,
                "confidence": r.confidence,
                "factors_responsible": json.loads(r.factors_responsible) if r.factors_responsible else None,
                "exit_trigger": r.exit_trigger,
                "allocation": r.allocation,
                "price": r.price,
                "reason": r.reason,
                "sector": r.sector,
                "regime": r.regime,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ]

    def close(self):
        self.session.close()
