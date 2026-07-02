"""Daily monitoring and signal decay report."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.portfolio.monitoring import PortfolioMonitor
from app.portfolio.signal_decay import SignalDecayTracker

def main():
    monitor = PortfolioMonitor()
    tracker = SignalDecayTracker()
    try:
        report = monitor.daily_report()
        print("=== Daily Monitoring Report ===")
        for k, v in report.items():
            print(f"  {k}: {v}")

        decay = tracker.run_full_decay_analysis()
        optimal = tracker.optimal_holding_period()
        half_life = tracker.compute_alpha_half_life()
        efficiency = tracker.holding_period_efficiency()

        os.makedirs("/tmp", exist_ok=True)
        with open("/tmp/daily_monitoring.json", "w") as f:
            json.dump({
                "monitoring": report,
                "signal_decay": decay,
                "optimal_holding": optimal,
                "alpha_half_life": half_life,
                "holding_period_efficiency": efficiency,
            }, f, indent=2)
        print("Report saved to /tmp/daily_monitoring.json")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        monitor.close()
        tracker.close()

if __name__ == "__main__":
    main()
