"""Daily portfolio run. Cron entry point."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.portfolio.live_portfolio import LivePortfolio

def main():
    lp = LivePortfolio()
    try:
        result = lp.full_daily_cycle()
        print(f"Date: {result['date']}")
        print(f"Regime: {result['regime']}")
        print(f"Positions: {result['n_positions']}")
        print(f"Trades: {len(result['trades'])}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        lp.close()

if __name__ == "__main__":
    main()
