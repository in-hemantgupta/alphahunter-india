#!/usr/bin/env python3
"""Daily paper trading runner. Callable from cron."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

from app.portfolio.paper_trading import PaperTradingEngine

def main():
    engine = PaperTradingEngine()
    try:
        decay = engine.refresh()
        os.makedirs("/Users/hemant/alpha-hunter/reports", exist_ok=True)
        with open("/Users/hemant/alpha-hunter/reports/daily_alpha_decay.json", "w") as f:
            json.dump(decay, f, indent=2, default=str)
        print(json.dumps(decay, indent=2))
        print("Done.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.close()

if __name__ == "__main__":
    main()
