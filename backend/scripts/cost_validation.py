import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np

SCENARIOS = {
    'optimistic': {'A': 10, 'B': 30, 'C': 60, 'D': 100},
    'realistic': {'A': 20, 'B': 60, 'C': 120, 'D': 200},
    'worst_case': {'A': 40, 'B': 120, 'C': 240, 'D': 400},
}

TIER_NAMES = {'A': 'Large(10000cr+)', 'B': 'Mid(1000-10000cr)', 'C': 'Small(100-1000cr)', 'D': 'Micro(<100cr)'}

json_path = '/Users/hemant/alpha-hunter/reports/alpha_validation.json'
if os.path.exists(json_path):
    with open(json_path) as f:
        d = json.load(f)
    h = d['horizon_results']['60']
    LS_CAGR = h['long_short']['cagr_pct']
    LS_SHARPE = h['long_short']['sharpe_ratio']
    LS_VOL = h['long_short']['volatility_pct']
    LO_CAGR_EXCESS = h['portfolio']['excess_cagr_pct']
    LO_CAGR = h['portfolio']['cagr_pct']
    LO_SHARPE = h['portfolio']['sharpe_ratio']
    DATA_SOURCE = 'alpha_validation.json'
else:
    LS_CAGR = 8.70
    LS_SHARPE = 2.37
    LS_VOL = LS_CAGR / LS_SHARPE if LS_SHARPE > 0 else 3.67
    LO_CAGR_EXCESS = 3.3
    LO_CAGR = LO_CAGR_EXCESS
    LO_SHARPE = 0.76
    DATA_SOURCE = 'reference values (AGENTS.md)'

LO_VOL = LO_CAGR / LO_SHARPE if LO_SHARPE > 0 else 5.0


def compute_drag(turnover_pct, avg_cost_bps):
    return turnover_pct * avg_cost_bps / 10000


def run():
    print("=" * 72)
    print("  TRANSACTION COST VALIDATION")
    print("=" * 72)

    print(f"\n  Data source: {DATA_SOURCE}")
    print(f"  {'Metric':<30s} {'Long-Short':>15s} {'Long-Only':>15s}")
    print(f"  {'-'*30} {'-'*15} {'-'*15}")
    print(f"  {'CAGR (%)':<30s} {LS_CAGR:>15.2f} {LO_CAGR:>15.2f}")
    print(f"  {'Sharpe':<30s} {LS_SHARPE:>15.3f} {LO_SHARPE:>15.3f}")
    print(f"  {'Volatility (%)':<30s} {LS_VOL:>15.2f} {LO_VOL:>15.2f}")
    print(f"  {'Excess CAGR (%)':<30s} {'—':>15s} {LO_CAGR_EXCESS:>15.2f}")

    # 1. Scenario costs table
    print(f"\n  ┌─── Cost Scenarios (bps per tier) ───────────────────────────────┐")
    print(f"  {'Scenario':<18s} {'A':>6s} {'B':>6s} {'C':>6s} {'D':>6s} {'Avg':>7s}")
    print(f"  {'─'*18} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*7}")
    for name, costs in SCENARIOS.items():
        avg = np.mean(list(costs.values()))
        print(f"  {name:<18s} {costs['A']:>6d} {costs['B']:>6d} {costs['C']:>6d} {costs['D']:>6d} {avg:>7.1f}")
    print(f"  └{'─'*52}┘")

    # 2. Annual cost drag at estimated turnover
    est_turnover = 30.0
    print(f"\n  ┌─── Annual Cost Drag @ {est_turnover:.0f}% Monthly Turnover ──────────────┐")
    print(f"  {'Scenario':<18s} {'AvgCost(bps)':>12s} {'Drag(%)':>9s}")
    print(f"  {'─'*18} {'─'*12} {'─'*9}")
    drag_results = {}
    for name, costs in SCENARIOS.items():
        avg_cost = np.mean(list(costs.values()))
        drag = compute_drag(est_turnover, avg_cost)
        drag_results[name] = {'avg_cost': avg_cost, 'cost_drag_pct': drag}
        print(f"  {name:<18s} {avg_cost:>12.1f} {drag:>8.2f}%")
    print(f"  └{'─'*42}┘")

    # 3. CAGR impact
    print(f"\n  ┌─── CAGR Impact (After Costs) ─────────────────────────────────┐")
    print(f"  {'Scenario':<18s} {'Before(%)':>10s} {'Drag(%)':>9s} {'After(%)':>10s}")
    print(f"  {'─'*18} {'─'*10} {'─'*9} {'─'*10}")

    results = {}
    for label, cagr, vol, sharpe in [('Long-Short', LS_CAGR, LS_VOL, LS_SHARPE),
                                      ('Long-Only', LO_CAGR, LO_VOL, LO_SHARPE)]:
        print(f"\n  {label}:")
        for name, costs in SCENARIOS.items():
            drag = drag_results[name]['cost_drag_pct']
            after = cagr - drag
            new_sharpe = (cagr - drag) / vol if vol > 0 else 0
            print(f"    {name:<16s} {cagr:>10.2f} {drag:>8.2f}% {after:>10.2f}%  Sharpe: {sharpe:.3f} → {new_sharpe:.3f}")
            if label == 'Long-Short':
                results[name] = {'cagr': after, 'sharpe': new_sharpe}
    print(f"  └{'─'*52}┘")

    # 4. Sensitivity analysis
    print(f"\n  ┌─── Sensitivity: Turnover → Cost Drag (%) ─────────────────────┐")
    header = f"  {'Turnover':>10s}"
    for name in SCENARIOS:
        header += f"  {name:>12s}"
    print(header)
    print(f"  {'─'*10}  {'─'*12}  {'─'*12}  {'─'*12}")
    for turnover in range(10, 160, 10):
        line = f"  {turnover:>8d}%  "
        for name, costs in SCENARIOS.items():
            avg_cost = np.mean(list(costs.values()))
            drag = compute_drag(float(turnover), avg_cost)
            line += f"{drag:>12.2f}%"
        print(line)
    print(f"  └{'─'*55}┘")

    # 5. Breakeven turnover analysis
    print(f"\n  ┌─── Breakeven Turnover (where cost drag = excess CAGR) ────────┐")
    for name, costs in SCENARIOS.items():
        avg_cost = np.mean(list(costs.values()))
        if avg_cost > 0:
            be_turnover = (LO_CAGR_EXCESS * 10000) / avg_cost
            print(f"  {name:<18s}: {be_turnover:>6.1f}% monthly turnover (excess={LO_CAGR_EXCESS:.2f}%)")
    print(f"  └{'─'*55}┘")

    # 6. Verdict
    print(f"\n  ┌─── VERDICT ───────────────────────────────────────────────────┐")
    worst_sharpe = results['worst_case']['sharpe']
    verdict = "PASS" if worst_sharpe > 1.0 else "FAIL"
    print(f"  {'':<5s}Worst-case long-short Sharpe after costs: {worst_sharpe:.3f}")
    print(f"  {'':<5s}Threshold: Sharpe > 1.0")
    print(f"  {'':<5s}Verdict: {verdict}")
    print(f"  └{'─'*55}┘")

    # Return report dict
    report = {
        'data_source': DATA_SOURCE,
        'reference_metrics': {
            'long_short': {'cagr_pct': LS_CAGR, 'sharpe': LS_SHARPE, 'volatility_pct': LS_VOL},
            'long_only': {'cagr_pct': LO_CAGR, 'sharpe': LO_SHARPE, 'volatility_pct': LO_VOL,
                          'excess_cagr_pct': LO_CAGR_EXCESS},
        },
        'scenario_costs': {name: {'bps_per_tier': costs, 'avg_bps': np.mean(list(costs.values()))}
                           for name, costs in SCENARIOS.items()},
        'estimated_turnover_pct': est_turnover,
        'annual_cost_drag': drag_results,
        'cagr_impact': results,
        'sensitivity': {
            'turnover_range_pct': list(range(10, 160, 10)),
            'cost_drag_by_scenario': {
                name: [compute_drag(float(t), np.mean(list(SCENARIOS[name].values())))
                       for t in range(10, 160, 10)]
                for name in SCENARIOS
            }
        },
        'verdict': verdict,
        'worst_case_sharpe_after_costs': worst_sharpe,
    }

    print(f"\n  Report dict ready. {len(json.dumps(report, indent=2))} chars.")
    return report


if __name__ == '__main__':
    run()
