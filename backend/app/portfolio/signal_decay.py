"""Alpha decay tracker. Measures signal persistence over time."""
from datetime import date, timedelta
import numpy as np
from scipy.stats import spearmanr
from collections import defaultdict
from app.db.database import SessionLocal
from app.models.score_snapshot import ScoreSnapshot
from app.models.price_history import PriceHistory
from app.models.stock import Stock
import yfinance as yf


class SignalDecayTracker:
    """Track alpha decay for every scored stock recommendation."""

    def __init__(self):
        self.session = SessionLocal()

    def get_top_stocks(self, snapshot_date, n=100):
        """Get top N stocks from a snapshot date."""
        snapshots = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.date == snapshot_date
        ).order_by(ScoreSnapshot.total_score.desc()).limit(n).all()
        return [(s.symbol, s.total_score) for s in snapshots]

    def compute_excess_return(self, symbol, entry_date, holding_days):
        """Compute excess return vs Nifty 50 for a stock over holding period."""
        exit_date = entry_date + timedelta(days=holding_days * 2)
        try:
            stock = yf.Ticker(symbol + ".NS")
            hist = stock.history(start=entry_date, end=exit_date, auto_adjust=True)
            if hist.empty or len(hist) < holding_days:
                return None

            entry_price = hist["Close"].iloc[0]
            exit_price = hist["Close"].iloc[min(holding_days - 1, len(hist) - 1)]
            stock_return = exit_price / entry_price - 1

            nifty = yf.Ticker("^NSEI")
            n_hist = nifty.history(start=entry_date, end=exit_date, auto_adjust=True)
            if not n_hist.empty and len(n_hist) > 1:
                nifty_return = n_hist["Close"].iloc[min(holding_days - 1, len(n_hist) - 1)] / n_hist["Close"].iloc[0] - 1
                return round(float(stock_return - nifty_return), 4)
            return round(float(stock_return), 4)
        except Exception:
            return None

    def compute_rank_persistence(self, snapshot_dates, symbol):
        """Track how a stock's rank changes over consecutive snapshots."""
        scores = self.session.query(ScoreSnapshot).filter(
            ScoreSnapshot.symbol == symbol,
            ScoreSnapshot.date.in_(snapshot_dates),
        ).order_by(ScoreSnapshot.date).all()

        ranks = []
        for s in scores:
            all_scores = self.session.query(ScoreSnapshot).filter(
                ScoreSnapshot.date == s.date
            ).order_by(ScoreSnapshot.total_score.desc()).all()

            for i, a in enumerate(all_scores):
                if a.symbol == symbol:
                    ranks.append((s.date, i + 1, len(all_scores)))
                    break

        return ranks

    def compute_decay_curve(self, snapshot_date):
        """Compute alpha decay curve for a single snapshot date.
        Returns: {days: mean_excess_return} for days 1, 7, 15, 30, 60, 90
        """
        top_stocks = self.get_top_stocks(snapshot_date, 50)
        if not top_stocks:
            return {}

        horizons = [1, 7, 15, 30, 60, 90]
        decay = {h: [] for h in horizons}

        for symbol, score in top_stocks:
            for h in horizons:
                excess = self.compute_excess_return(symbol, snapshot_date, h)
                if excess is not None:
                    decay[h].append(excess)

        result = {}
        for h, returns in decay.items():
            if len(returns) >= 5:
                mean_ret = float(np.mean(returns))
                std_ret = float(np.std(returns))
                sharpe = mean_ret / max(std_ret, 1e-6) * np.sqrt(252 / max(h, 1))
                positive_pct = sum(1 for r in returns if r > 0) / len(returns) * 100
                result[str(h)] = {
                    "mean_excess_return": round(mean_ret, 4),
                    "std": round(std_ret, 4),
                    "sharpe": round(sharpe, 2),
                    "positive_pct": round(positive_pct, 1),
                    "n": len(returns),
                }

        return result

    def run_full_decay_analysis(self):
        """Run decay analysis across all historical snapshots."""
        dates = [r[0] for r in self.session.query(
            ScoreSnapshot.date
        ).distinct().order_by(ScoreSnapshot.date).all()]

        print(f"Running decay analysis on {len(dates)} snapshots...")
        all_horizons = defaultdict(list)

        for d in dates[-10:]:
            decay = self.compute_decay_curve(d)
            for h, metrics in decay.items():
                all_horizons[h].append(metrics["mean_excess_return"])

        print("\n=== Signal Decay Summary ===")
        results = {}
        for h, returns in sorted(all_horizons.items(), key=lambda x: int(x[0])):
            if returns:
                mean = float(np.mean(returns))
                std = float(np.std(returns))
                sharpe = mean / max(std, 1e-6) * np.sqrt(252 / max(int(h), 1))
                results[h] = {
                    "mean_excess_return": round(mean, 4),
                    "sharpe": round(sharpe, 2),
                    "n_snapshots": len(returns),
                }
                print(f"  Day {h:>3s}: excess={mean:+.4f} Sharpe={sharpe:.2f}")

        return results

    def optimal_holding_period(self):
        """Determine optimal holding period from decay curve."""
        results = self.run_full_decay_analysis()
        if not results:
            return 60

        best_horizon = max(results.items(), key=lambda x: x[1]["sharpe"])
        print(f"\nOptimal holding period: Day {best_horizon[0]} (Sharpe {best_horizon[1]['sharpe']:.2f})")
        return int(best_horizon[0])

    def compute_alpha_half_life(self):
        results = self.run_full_decay_analysis()
        if not results:
            return {"peak_horizon": None, "peak_excess_return": None, "half_life_days": None}

        horizons = sorted(results.keys(), key=int)
        peak_h = max(horizons, key=lambda h: results[h]["mean_excess_return"])
        peak_val = results[peak_h]["mean_excess_return"]
        half_target = peak_val / 2

        if half_target <= 0 or peak_val <= 0:
            return {"peak_horizon": int(peak_h), "peak_excess_return": peak_val, "half_life_days": None}

        half_life = None
        for i, h in enumerate(horizons):
            if results[h]["mean_excess_return"] <= half_target:
                if i == 0:
                    half_life = int(h)
                else:
                    prev_h = horizons[i - 1]
                    prev_val = results[prev_h]["mean_excess_return"]
                    curr_val = results[h]["mean_excess_return"]
                    if prev_val != curr_val:
                        frac = (prev_val - half_target) / (prev_val - curr_val)
                        half_life = int(int(prev_h) + frac * (int(h) - int(prev_h)))
                break

        return {
            "peak_horizon": int(peak_h),
            "peak_excess_return": peak_val,
            "half_life_days": half_life,
        }

    def holding_period_efficiency(self):
        results = self.run_full_decay_analysis()
        efficiency = {}
        for h_str, metrics in results.items():
            days = int(h_str)
            excess_per_day = metrics["mean_excess_return"] / days
            efficiency[int(h_str)] = {
                "excess_return_per_day": round(excess_per_day, 6),
                "mean_excess_return": metrics["mean_excess_return"],
                "sharpe": metrics["sharpe"],
            }
        return efficiency

    def close(self):
        self.session.close()
