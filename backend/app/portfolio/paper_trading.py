"""Daily paper trading engine.
Runs daily scoring, stores picks, tracks forward returns.
"""
import sys, os, json
from datetime import datetime, date, timedelta
import numpy as np
import yfinance as yf
from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.models.score_snapshot import ScoreSnapshot
from app.services.pipeline import run_full_pipeline
from app.services.audit_logger import AuditLogger


class PaperTradingEngine:
    def __init__(self):
        self.session = SessionLocal()
        self.audit = AuditLogger()
        self._ensure_table()

    def _ensure_table(self):
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS paper_daily_picks (
                    id SERIAL PRIMARY KEY,
                    pick_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    score FLOAT,
                    rank INTEGER,
                    ret_7d FLOAT,
                    ret_30d FLOAT,
                    ret_60d FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pick_date ON paper_daily_picks(pick_date)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_symbol ON paper_daily_picks(symbol)"))
            for col in ["ret_1d", "ret_15d", "ret_90d"]:
                try:
                    conn.execute(text(f"ALTER TABLE paper_daily_picks ADD COLUMN {col} FLOAT"))
                except Exception:
                    pass
            conn.commit()

    def run_daily_scoring(self):
        print("  Running full pipeline...")
        run_full_pipeline()
        today = date.today()
        snapshot = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == today
        ).order_by(ScoreSnapshot.total_score.desc()).all()
        if not snapshot:
            latest = self.session.query(ScoreSnapshot).order_by(
                ScoreSnapshot.date.desc()
            ).first()
            if latest:
                snapshot = self.session.query(ScoreSnapshot).filter(
                    ScoreSnapshot.date == latest.date
                ).order_by(ScoreSnapshot.total_score.desc()).all()
        top_50 = [(s.symbol, s.total_score) for s in snapshot[:50]]
        return top_50, snapshot

    def store_daily_picks(self, top_50):
        today = date.today()
        for rank, (symbol, score) in enumerate(top_50, 1):
            self.session.execute(text("""
                INSERT INTO paper_daily_picks (pick_date, symbol, score, rank)
                VALUES (:pick_date, :symbol, :score, :rank)
            """), {
                "pick_date": today,
                "symbol": symbol,
                "score": float(score) if score else 0,
                "rank": rank,
            })
        self.session.commit()

    def update_forward_returns(self):
        today = date.today()
        rows = self.session.execute(text("""
            SELECT id, pick_date, symbol FROM paper_daily_picks
            WHERE ret_60d IS NULL
        """)).fetchall()

        for row in rows:
            pick_id, pick_date, symbol = row
            days_elapsed = (today - pick_date).days

            try:
                ticker = yf.Ticker(symbol + ".NS")
                hist = ticker.history(start=pick_date, end=today + timedelta(days=1), auto_adjust=True)
                if hist.empty or len(hist) < 2:
                    continue

                close = hist["Close"]
                entry_price = close.iloc[0]

                def compute_ret(trading_days):
                    if len(close) >= trading_days:
                        return float(close.iloc[trading_days - 1] / entry_price - 1)
                    return None

                ret_1d = compute_ret(1) if days_elapsed >= 1 else None
                ret_7d = compute_ret(7) if days_elapsed >= 7 else None
                ret_15d = compute_ret(15) if days_elapsed >= 15 else None
                ret_30d = compute_ret(30) if days_elapsed >= 30 else None
                ret_60d = compute_ret(60) if days_elapsed >= 60 else None
                ret_90d = compute_ret(90) if days_elapsed >= 90 else None

                update_fields = []
                if ret_1d is not None:
                    update_fields.append(f"ret_1d = {ret_1d}")
                if ret_7d is not None:
                    update_fields.append(f"ret_7d = {ret_7d}")
                if ret_15d is not None:
                    update_fields.append(f"ret_15d = {ret_15d}")
                if ret_30d is not None:
                    update_fields.append(f"ret_30d = {ret_30d}")
                if ret_60d is not None:
                    update_fields.append(f"ret_60d = {ret_60d}")
                if ret_90d is not None:
                    update_fields.append(f"ret_90d = {ret_90d}")

                if update_fields:
                    self.session.execute(text(f"""
                        UPDATE paper_daily_picks SET {', '.join(update_fields)}
                        WHERE id = {pick_id}
                    """))
                    self.session.commit()
            except Exception as e:
                print(f"  Error updating {symbol}: {e}")

    def compute_alpha_decay(self):
        rows = self.session.execute(text("""
            SELECT ret_1d, ret_7d, ret_15d, ret_30d, ret_60d, ret_90d FROM paper_daily_picks
            WHERE ret_1d IS NOT NULL OR ret_7d IS NOT NULL OR ret_15d IS NOT NULL
               OR ret_30d IS NOT NULL OR ret_60d IS NOT NULL OR ret_90d IS NOT NULL
        """)).fetchall()

        rets = {"1d": [], "7d": [], "15d": [], "30d": [], "60d": [], "90d": []}
        key_map = {"ret_1d": "1d", "ret_7d": "7d", "ret_15d": "15d",
                   "ret_30d": "30d", "ret_60d": "60d", "ret_90d": "90d"}
        columns = ["ret_1d", "ret_7d", "ret_15d", "ret_30d", "ret_60d", "ret_90d"]
        for row in rows:
            for db_key, label in key_map.items():
                idx = columns.index(db_key)
                val = row[idx]
                if val is not None:
                    rets[label].append(val)

        result = {}
        for horizon, vals in rets.items():
            if len(vals) > 5:
                mean_ret = np.mean(vals)
                std_ret = np.std(vals)
                sharpe = mean_ret / max(std_ret, 1e-6) * np.sqrt(252)
                result[horizon] = {
                    "mean_return": round(float(mean_ret), 4),
                    "std": round(float(std_ret), 4),
                    "sharpe": round(float(sharpe), 2),
                    "n": len(vals),
                    "positive_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
                }
        return result

    def refresh(self):
        import time
        print("=== Paper Trading Daily Refresh ===")
        print("Running daily scoring...")
        _t = time.time()
        try:
            top_50, _ = self.run_daily_scoring()
            self.audit.log_success("run_daily_scoring", "paper_trading", source="paper_trading", duration_ms=int((time.time()-_t)*1000))
        except Exception as e:
            self.audit.log_failure("run_daily_scoring", "paper_trading", str(e), source="paper_trading")
            raise

        if not top_50:
            self.audit.log_warning("run_daily_scoring", "paper_trading", details="No scored stocks found", source="paper_trading")
            print("  No scored stocks found!")
            return {}

        print(f"  Top pick: {top_50[0][0]} ({top_50[0][1]:.1f})")

        _t = time.time()
        try:
            self.store_daily_picks(top_50)
            n_picks = self.session.execute(text("SELECT COUNT(*) FROM paper_daily_picks")).scalar()
            print(f"  Total picks in DB: {n_picks}")
            self.audit.log_success("store_daily_picks", "paper_trading", details=f"{len(top_50)} picks stored", source="paper_trading", duration_ms=int((time.time()-_t)*1000))
        except Exception as e:
            self.audit.log_failure("store_daily_picks", "paper_trading", str(e), source="paper_trading")
            raise

        _t = time.time()
        try:
            self.update_forward_returns()
            self.audit.log_success("update_forward_returns", "paper_trading", source="paper_trading", duration_ms=int((time.time()-_t)*1000))
        except Exception as e:
            self.audit.log_failure("update_forward_returns", "paper_trading", str(e), source="paper_trading")

        decay = self.compute_alpha_decay()

        print("\nAlpha Decay Report:")
        for h, d in decay.items():
            print(f"  {h}: sharpe={d['sharpe']:.2f} mean={d['mean_return']:.4f} pos={d['positive_pct']:.0f}% n={d['n']}")

        return decay

    def close(self):
        self.audit.close()
        self.session.close()
