from datetime import date, timedelta
from sqlalchemy import text
import yfinance as yf
from app.db.database import engine, SessionLocal


class ShadowFund:
    def __init__(self, initial_capital=1_00_00_000):
        self.initial_capital = initial_capital
        self.session = SessionLocal()
        self._ensure_table()

    def _ensure_table(self):
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS fund_nav (
                    date DATE PRIMARY KEY,
                    nav FLOAT,
                    cash FLOAT,
                    invested_capital FLOAT,
                    realized_pnl FLOAT,
                    unrealized_pnl FLOAT,
                    benchmark_nav FLOAT,
                    daily_return FLOAT,
                    benchmark_return FLOAT,
                    alpha FLOAT,
                    n_holdings INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_fund_nav_date ON fund_nav(date)"))
            conn.commit()

    def _get_benchmark_nav(self):
        try:
            nf = yf.Ticker("^NSEI")
            hist = nf.history(period="1d", auto_adjust=True)
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        return 1.0

    def initialize(self):
        today = date.today()
        existing = self.session.execute(
            text("SELECT date FROM fund_nav WHERE date = :d"), {"d": today}
        ).fetchone()
        if existing:
            return
        bnav = self._get_benchmark_nav()
        self.session.execute(text("""
            INSERT INTO fund_nav (date, nav, cash, invested_capital, realized_pnl, unrealized_pnl, benchmark_nav, daily_return, benchmark_return, alpha, n_holdings)
            VALUES (:date, :nav, :cash, :invested, :rp, :up, :bnav, :dr, :br, :alpha, :n)
        """), {
            "date": today,
            "nav": self.initial_capital,
            "cash": self.initial_capital,
            "invested": 0.0,
            "rp": 0.0,
            "up": 0.0,
            "bnav": bnav,
            "dr": 0.0,
            "br": 0.0,
            "alpha": 0.0,
            "n": 0,
        })
        self.session.commit()

    def update_nav(self, holdings_dict, benchmark_value=None):
        today = date.today()
        if benchmark_value is None:
            benchmark_value = self._get_benchmark_nav()

        prev = self.session.execute(
            text("SELECT nav, cash, invested_capital, realized_pnl, benchmark_nav FROM fund_nav ORDER BY date DESC LIMIT 1")
        ).fetchone()

        prev_nav = prev[0] if prev else self.initial_capital
        prev_cash = prev[1] if prev else self.initial_capital
        prev_invested = prev[2] if prev else 0.0
        prev_realized = prev[3] if prev else 0.0
        prev_bnav = prev[4] if prev else 1.0

        realized_pnl = float(prev_realized)
        total_unrealized = 0.0
        total_invested = 0.0

        for symbol, data in holdings_dict.items():
            allocation = float(data.get("allocation", 0))
            current_price = float(data.get("current_price", 0))
            entry_price = float(data.get("entry_price", 0))
            quantity = float(data.get("quantity", 0))
            total_invested += allocation
            if quantity > 0 and entry_price > 0:
                total_unrealized += (current_price - entry_price) * quantity

        new_investment = total_invested - float(prev_invested)
        cash = float(prev_cash) - new_investment + realized_pnl
        nav = cash + total_invested + total_unrealized
        daily_return = (nav / prev_nav - 1) if prev_nav > 0 else 0.0
        benchmark_return = (benchmark_value / prev_bnav - 1) if prev_bnav > 0 else 0.0
        alpha = daily_return - benchmark_return

        existing = self.session.execute(
            text("SELECT date FROM fund_nav WHERE date = :d"), {"d": today}
        ).fetchone()

        if existing:
            self.session.execute(text("""
                UPDATE fund_nav SET nav = :nav, cash = :cash, invested_capital = :invested,
                    realized_pnl = :rp, unrealized_pnl = :up, benchmark_nav = :bnav,
                    daily_return = :dr, benchmark_return = :br, alpha = :alpha, n_holdings = :n
                WHERE date = :date
            """), {
                "nav": round(nav, 4),
                "cash": round(cash, 4),
                "invested": round(total_invested, 4),
                "rp": round(realized_pnl, 4),
                "up": round(total_unrealized, 4),
                "bnav": round(benchmark_value, 4),
                "dr": round(daily_return, 6),
                "br": round(benchmark_return, 6),
                "alpha": round(alpha, 6),
                "n": len(holdings_dict),
                "date": today,
            })
        else:
            self.session.execute(text("""
                INSERT INTO fund_nav (date, nav, cash, invested_capital, realized_pnl, unrealized_pnl, benchmark_nav, daily_return, benchmark_return, alpha, n_holdings)
                VALUES (:date, :nav, :cash, :invested, :rp, :up, :bnav, :dr, :br, :alpha, :n)
            """), {
                "date": today,
                "nav": round(nav, 4),
                "cash": round(cash, 4),
                "invested": round(total_invested, 4),
                "rp": round(realized_pnl, 4),
                "up": round(total_unrealized, 4),
                "bnav": round(benchmark_value, 4),
                "dr": round(daily_return, 6),
                "br": round(benchmark_return, 6),
                "alpha": round(alpha, 6),
                "n": len(holdings_dict),
            })
        self.session.commit()

    def get_nav(self, as_of=None):
        if as_of:
            row = self.session.execute(
                text("SELECT * FROM fund_nav WHERE date <= :d ORDER BY date DESC LIMIT 1"),
                {"d": as_of}
            ).fetchone()
        else:
            row = self.session.execute(
                text("SELECT * FROM fund_nav ORDER BY date DESC LIMIT 1")
            ).fetchone()
        if not row:
            return None
        cols = ["date", "nav", "cash", "invested_capital", "realized_pnl",
                "unrealized_pnl", "benchmark_nav", "daily_return",
                "benchmark_return", "alpha", "n_holdings", "created_at"]
        return dict(zip(cols, row))

    def get_nav_curve(self):
        rows = self.session.execute(
            text("SELECT * FROM fund_nav ORDER BY date ASC")
        ).fetchall()
        cols = ["date", "nav", "cash", "invested_capital", "realized_pnl",
                "unrealized_pnl", "benchmark_nav", "daily_return",
                "benchmark_return", "alpha", "n_holdings", "created_at"]
        return [dict(zip(cols, r)) for r in rows]

    def compute_returns(self, from_date, to_date):
        f_row = self.session.execute(
            text("SELECT nav, benchmark_nav FROM fund_nav WHERE date >= :d ORDER BY date ASC LIMIT 1"),
            {"d": from_date}
        ).fetchone()
        t_row = self.session.execute(
            text("SELECT nav, benchmark_nav FROM fund_nav WHERE date <= :d ORDER BY date DESC LIMIT 1"),
            {"d": to_date}
        ).fetchone()
        if not f_row or not t_row:
            return None, None
        port_ret = t_row[0] / f_row[0] - 1
        bench_ret = t_row[1] / f_row[1] - 1
        return port_ret, bench_ret

    def get_current_cash(self):
        row = self.session.execute(
            text("SELECT cash FROM fund_nav ORDER BY date DESC LIMIT 1")
        ).fetchone()
        return float(row[0]) if row else self.initial_capital

    def record_realized_pnl(self, symbol, pnl, reason=None):
        today = date.today()
        existing = self.session.execute(
            text("SELECT realized_pnl FROM fund_nav WHERE date = :d"), {"d": today}
        ).fetchone()
        if existing:
            self.session.execute(text("""
                UPDATE fund_nav SET realized_pnl = realized_pnl + :pnl WHERE date = :date
            """), {"pnl": pnl, "date": today})
        else:
            prev = self.session.execute(
                text("SELECT realized_pnl FROM fund_nav ORDER BY date DESC LIMIT 1")
            ).fetchone()
            base = float(prev[0]) if prev else 0.0
            self.session.execute(text("""
                INSERT INTO fund_nav (date, realized_pnl, nav, cash, invested_capital, unrealized_pnl, benchmark_nav, daily_return, benchmark_return, alpha, n_holdings)
                VALUES (:date, :rp, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """), {"date": today, "rp": base + pnl})
        self.session.commit()

    def close(self):
        self.session.close()
