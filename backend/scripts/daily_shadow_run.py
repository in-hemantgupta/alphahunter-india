"""Daily shadow fund run. Ties portfolio cycle + fund NAV + kill switch + alerts."""
import sys, os, json, time
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

from app.portfolio.live_portfolio import LivePortfolio
from app.portfolio.shadow_fund import ShadowFund
from app.portfolio.decision_journal import DecisionJournal
from app.portfolio.kill_switch import KillSwitch
from app.portfolio.drift_detector import DriftDetector
from app.services.audit_logger import AuditLogger
from app.db.database import SessionLocal
from app.models.portfolio_position import PortfolioPosition
from app.models.stock import Stock


def main():
    audit = AuditLogger()
    report_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'shadow_run_report.json')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    print("=" * 60)
    print("  ALPHAHUNTER — DAILY SHADOW FUND RUN")
    print("=" * 60)

    start_time = time.time()

    print("\n[STEP 1/8] Checking kill switch...")
    ks = KillSwitch()
    if ks.is_trading_suspended():
        print("  *** KILL SWITCH ENGAGED — TRADING SUSPENDED ***")
        audit.log("shadow_run_blocked", "shadow_fund", "WARNING",
                  details="Shadow run blocked by engaged kill switch",
                  source="daily_shadow_run")
        ks.close()
        audit.close()
        return {"status": "blocked", "reason": "kill_switch_engaged"}
    ks.close()

    print("\n[STEP 2/8] Running live portfolio cycle...")
    lp = LivePortfolio()
    try:
        result = lp.full_daily_cycle()
        print(f"  Portfolio: {result['n_positions']} positions, {len(result['trades'])} trades")
    except Exception as e:
        print(f"  Portfolio cycle failed: {e}")
        audit.log_failure("shadow_run_portfolio", "shadow_fund", str(e), source="daily_shadow_run")
        lp.close()
        audit.close()
        return {"status": "error", "error": str(e)}
    lp.close()

    print("\n[STEP 3/8] Updating shadow fund NAV...")
    fund = ShadowFund()
    fund.initialize()
    try:
        session = SessionLocal()
        positions = session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date.today()
        ).all()
        holdings_dict = {}
        for p in positions:
            stock = session.query(Stock).filter(Stock.symbol == p.symbol).first()
            holdings_dict[p.symbol] = {
                "allocation": p.allocation or 0,
                "current_price": p.current_price or 0,
                "entry_price": p.entry_price or p.current_price or 0,
                "quantity": (p.allocation or 0) / max(p.current_price or 1, 1),
                "pnl_pct": p.pnl_pct or 0,
            }
        session.close()
        fund.update_nav(holdings_dict)
        nav_data = fund.get_nav()
        if nav_data:
            print(f"  NAV: Rs.{nav_data['nav']:,.2f}")
        else:
            print("  NAV: N/A")
    except Exception as e:
        print(f"  NAV update failed: {e}")
        audit.log_failure("shadow_run_nav", "shadow_fund", str(e), source="daily_shadow_run")
    fund.close()

    print("\n[STEP 4/8] Logging trade decisions...")
    dj = DecisionJournal()
    try:
        trades = result.get("trades", [])
        session = SessionLocal()
        positions = session.query(PortfolioPosition).filter(
            PortfolioPosition.date == date.today()
        ).all()
        pos_map = {p.symbol: p for p in positions}
        session.close()
        for t in trades:
            p = pos_map.get(t["symbol"])
            dj.log_decision(
                date=date.today(),
                symbol=t["symbol"],
                action=t["action"],
                score=p.score if p else None,
                rank=p.rank if p else None,
                confidence=p.confidence if p else None,
                exit_trigger=t.get("reason") if t["action"] == "SELL" else None,
                allocation=t.get("target_weight"),
                reason=t.get("reason"),
                sector=p.sector if p else None,
            )
        print(f"  Logged {len(trades)} decisions")
    except Exception as e:
        print(f"  Decision logging failed: {e}")
    dj.close()

    print("\n[STEP 5/8] Checking portfolio drift...")
    try:
        dd = DriftDetector()
        drift = dd.full_drift_report()
        all_alerts = drift.get("alerts", [])
        if all_alerts:
            print(f"  {len(all_alerts)} drift alerts:")
            for a in all_alerts[:5]:
                print(f"    {a}")
        else:
            print("  No drift alerts")
        dd.close()
    except Exception as e:
        print(f"  Drift check failed: {e}")
        all_alerts = []

    print("\n[STEP 6/8] Running kill switch check...")
    try:
        ks = KillSwitch()
        ks_result = ks.check_and_engage()
        if ks_result["action_taken"] == "engaged":
            print("  *** KILL SWITCH ENGAGED ***")
        elif ks_result["breached_count"] > 0:
            print(f"  {ks_result['breached_count']} conditions breached (auto-disarm pending)")
        else:
            print("  All conditions safe")
        ks.close()
    except Exception as e:
        print(f"  Kill switch check failed: {e}")
        ks_result = {}

    print("\n[STEP 7/8] Running alert engine...")
    try:
        from app.portfolio.alert_engine import AlertEngine
        ae = AlertEngine()
        alerts = ae.check_all()
        print(f"  {len(alerts)} alerts generated")
        ae.close()
    except Exception as e:
        print(f"  Alert engine failed: {e}")
        alerts = []

    print("\n[STEP 8/8] Saving daily report...")
    elapsed = time.time() - start_time
    report = {
        "date": str(date.today()),
        "status": "completed",
        "duration_seconds": round(elapsed, 1),
        "n_positions": result.get("n_positions", 0),
        "n_trades": len(result.get("trades", [])),
        "regime": result.get("regime"),
        "n_drift_alerts": len(all_alerts),
        "n_kill_switch_alerts": ks_result.get("breached_count", 0),
        "n_engine_alerts": len(alerts),
    }
    if nav_data:
        report["nav"] = round(nav_data["nav"], 2)
        report["daily_return"] = nav_data.get("daily_return")
        report["alpha"] = nav_data.get("alpha")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Duration: {elapsed:.1f}s")
    print(f"  Report: {report_path}")
    audit.log_success("shadow_run_complete", "shadow_fund",
                      details=json.dumps(report), source="daily_shadow_run",
                      duration_ms=int(elapsed * 1000))
    audit.close()
    return report


if __name__ == "__main__":
    main()
