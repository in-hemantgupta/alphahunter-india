"""PHASE 8 — Future Return Validation
PHASE 9 — Remove Dead Factors
PHASE 10 — Final Institutional Score"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.models.stock import Stock

session = SessionLocal()
stocks = session.query(ScoredStock).all()
stock_meta = {s.symbol: s for s in session.query(Stock).all()}
session.close()
print(f"Loaded {len(stocks)} scored stocks")

LAYERS = [
    "quality_score", "growth_score", "momentum_score", "technical_score",
    "microstructure_score", "management_score", "forensic_score",
    "lowvol_score", "macro_score", "alternative_score", "value_score"
]

# ============================================================
# PHASE 8: Future Return Validation
# ============================================================
print("="*60)
print("PHASE 8 — FUTURE RETURN VALIDATION")
print("="*60)

# Check earliest scored_at date
scored_dates = set()
for s in stocks:
    if s.scored_at:
        scored_dates.add(s.scored_at.date())
print(f"  Score dates: {sorted(scored_dates)}")

phase8 = {
    "status": "BLOCKED",
    "reason": "No historical score snapshots available. All 2395 stocks scored at 2026-06-30. "
              "Price history ends at 2026-06-30. Cannot compute forward returns.",
    "infrastructure_gap": "score_snapshots table does not exist. Without periodic score snapshots "
                          "and walk-forward validation, future return testing is impossible.",
    "score_dates": [str(d) for d in sorted(scored_dates)],
    "n_stocks": len(stocks),
    "price_history_range": "2024-06-26 to 2026-06-30",
    "recommendation": "Implement monthly score_snapshots table and rebuild backtest with "
                      "walk-forward validation before claiming predictive power.",
    "proxy_test_summary": None,
}
print(f"  BLOCKED: {phase8['reason']}")

# ============================================================
# PHASE 9: Remove Dead Factors
# ============================================================
print("\n" + "="*60)
print("PHASE 9 — REMOVE DEAD FACTORS")
print("="*60)

# Load importance and correlation data from prior phases
imp_path = "/Users/hemant/alpha-hunter/reports/feature_importance.json"
corr_path = "/Users/hemant/alpha-hunter/reports/factor_correlation.json"

imp_data = {}
if os.path.exists(imp_path):
    with open(imp_path) as f:
        imp_data = json.load(f)

corr_data = {}
if os.path.exists(corr_path):
    with open(corr_path) as f:
        corr_data = json.load(f)

# Extract importance for 6m returns target (most reliable)
importance_6m = {}
rf_6m = imp_data.get("results", {}).get("past_6m_return", {}).get("feature_importance", {})
if not rf_6m:
    rf_6m = imp_data.get("results", {}).get("past_6m_return", {}).get("feature_importance_sorted", [])
    if rf_6m and isinstance(rf_6m, list):
        importance_6m = {k: v for k, v in rf_6m}
else:
    importance_6m = rf_6m

# Extract max inter-factor correlations
max_corr = {}
for row in corr_data.get("pearson_matrix", []):
    layer = row.get("layer")
    if layer:
        max_val = 0
        max_pair = ""
        for k, v in row.items():
            if k != "layer" and isinstance(v, (int, float)) and not np.isnan(v) and abs(v) > abs(max_val) and k != layer:
                max_val = v
                max_pair = k
        max_corr[layer] = {"max_corr_with": max_pair, "value": round(max_val, 3)}

print("  Factor evaluation (importance < 3% AND correlation > 0.50):")
candidates_for_removal = []
for layer in LAYERS:
    imp_val = importance_6m.get(layer, 0) * 100  # convert to %
    corr_val = abs(max_corr.get(layer, {}).get("value", 0))
    corr_with = max_corr.get(layer, {}).get("max_corr_with", "")
    meets_criteria = imp_val < 3.0 and corr_val > 0.50
    flag = " *** REMOVE" if meets_criteria else ""
    if meets_criteria:
        candidates_for_removal.append({
            "layer": layer,
            "importance_pct": round(imp_val, 1),
            "max_correlation": round(corr_val, 3),
            "correlated_with": corr_with
        })
    print(f"    {layer:25s}: imp={imp_val:5.1f}%  max_corr={corr_val:.3f} ({corr_with}){flag}")

phase9 = {
    "methodology": "Remove factors meeting BOTH: importance < 3% AND correlation > 0.50 with another factor",
    "importance_source": "RandomForest on past_6m_return target",
    "correlation_source": "Pearson matrix from factor_correlation.json",
    "dead_factors": candidates_for_removal,
    "retained_factors": [k for k in LAYERS if k not in [c["layer"] for c in candidates_for_removal]],
    "note": "Only remove if both conditions met. Importance < 3% alone is not enough."
}
print(f"\n  Dead factors to remove: {[c['layer'] for c in candidates_for_removal]}")
print(f"  Retained: {phase9['retained_factors']}")

# ============================================================
# PHASE 10: Final Institutional Score
# ============================================================
print("\n" + "="*60)
print("PHASE 10 — FINAL INSTITUTIONAL SCORE")
print("="*60)

# Load all report data
def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

p1 = load_json(corr_path)
p2 = imp_data
p3 = load_json("/Users/hemant/alpha-hunter/reports/distribution_audit.json") or {}
p6 = load_json("/Users/hemant/alpha-hunter/reports/top100_manual_audit.json") or {}

p3d = p3.get("phase_3_distribution", {})
p4 = p3.get("phase_4_missing_data_bias", {})
p5 = p3.get("phase_5_stability_test", {})

# Score each dimension /100
scores = {}

# 1. Factor Independence (correlation < 0.40 ideal)
corr_flags = p1.get("flags", {})
over_40 = len(corr_flags.get("over_40", []))
over_60 = len(corr_flags.get("over_60_critical", []))
max_corr_val = 0
for row in p1.get("pearson_matrix", []):
    for k, v in row.items():
        if k != "layer" and isinstance(v, (int, float)) and not (v != v) and abs(v) > max_corr_val:
            max_corr_val = abs(v)
# Score: penalty for correlations > 0.40
factor_indep = 100
factor_indep -= over_40 * 10  # -10 per warning
factor_indep -= over_60 * 25  # -25 per critical
factor_indep = max(0, min(100, factor_indep))
scores["factor_independence"] = {
    "score": factor_indep,
    "max_correlation": round(max_corr_val, 3),
    "over_40_count": over_40,
    "over_60_count": over_60,
    "deductions": f"-{over_40*10}(over_40) -{over_60*25}(over_60)"
}

# 2. Predictive Power
# No forward returns available — score reflects this
pp_reason = ""
if phase8["status"] == "BLOCKED":
    pp_score = 0
    pp_reason = "Cannot compute — no historical score snapshots"
else:
    rf_r2 = p2.get("results", {}).get("past_6m_return", {}).get("rf_cv_r2", 0)
    rf_ic = p2.get("results", {}).get("past_6m_return", {}).get("spearman_ic", 0)
    pp_score = min(100, max(0, (rf_r2 * 50 + rf_ic * 100)))
    pp_reason = f"Based on past_6m_return: R²={rf_r2}, IC={rf_ic}"

scores["predictive_power"] = {
    "score": pp_score,
    "reason": pp_reason
}

# 3. Stability
mean_vol = p5.get("mean_score_volatility", 0)
unstable = p5.get("unstable_stocks_count", 0)
if mean_vol < 2:
    stab_score = 95
elif mean_vol < 5:
    stab_score = 80
elif mean_vol < 10:
    stab_score = 60
else:
    stab_score = 30
stab_score -= min(30, unstable * 5)
stab_score = max(0, min(100, stab_score))
scores["stability"] = {
    "score": stab_score,
    "mean_volatility": mean_vol,
    "unstable_stocks": unstable
}

# 4. Distribution
max_bucket = p3d.get("max_bucket_pct", 0)
min_score = p3d.get("min_score", 0)
max_score = p3d.get("max_score", 0)
spread = max_score - min_score
buckets_flagged = p3d.get("buckets_flagged_gt25", {})

dist_score = 100
if spread < 50:
    dist_score -= 25
elif spread < 70:
    dist_score -= 10
if max_bucket > 25:
    dist_score -= 20  # concentration penalty
if max_score < 80:
    dist_score -= 15  # ceiling too low
dist_score = max(0, min(100, dist_score))
scores["distribution"] = {
    "score": dist_score,
    "spread": round(spread, 1),
    "max_bucket_pct": max_bucket,
    "buckets_flagged": buckets_flagged,
    "max_score": max_score,
    "min_score": min_score
}

# 5. Data Coverage
# From pipeline output: roce 48%, eps 42.6%, operating_margin 40.9%, debt 22.7%
coverage_fields = {
    "roce": 48.0, "eps": 42.6, "operating_margin": 40.9,
    "debt": 22.7, "inventory": 19.3, "receivables": 22.3
}
avg_coverage = np.mean(list(coverage_fields.values()))
cov_score = min(100, avg_coverage * 1.2)  # scale up since 70% target
scores["data_coverage"] = {
    "score": round(cov_score, 1),
    "avg_coverage_pct": round(avg_coverage, 1),
    "target": 70,
    "fields": coverage_fields
}

# 6. Missing Data Bias
mr_score_corr = p4.get("corr_missing_ratio_vs_total_score", {}).get("pearson_r", 0)
hlc = p4.get("high_score_low_confidence_count", 0)
bias_score = 100
if mr_score_corr < -0.3:
    bias_score -= 20  # missing data reduces scores (actually good)
elif mr_score_corr > 0.1:
    bias_score -= 40  # missing data inflates scores (bad)
if hlc > 0:
    bias_score -= 30
bias_score = max(0, min(100, bias_score))
scores["missing_data_bias"] = {
    "score": bias_score,
    "corr_missing_vs_score": round(mr_score_corr, 3),
    "high_score_low_confidence": hlc,
    "interpretation": "Negative correlation means missing data -> lower scores (GOOD)"
}

# 7. Explainability
absurd = len(p6.get("phase_6_top100_sanity", {}).get("absurd_cases", []))
issues = p6.get("phase_6_top100_sanity", {}).get("stocks_with_issues", 0)
explain_score = 100
explain_score -= absurd * 30  # -30 per absurd case
explain_score -= int(issues / 10) * 5  # -5 per 10 issues
explain_score = max(0, min(100, explain_score))
scores["explainability"] = {
    "score": explain_score,
    "absurd_cases": absurd,
    "issues_in_top100": issues
}

# Final weighted score
weights = {
    "factor_independence": 0.15,
    "predictive_power": 0.20,
    "stability": 0.10,
    "distribution": 0.15,
    "data_coverage": 0.15,
    "missing_data_bias": 0.10,
    "explainability": 0.15,
}
final_score = sum(scores[k]["score"] * weights[k] for k in weights)

phase10 = {
    "dimensions": scores,
    "weights": weights,
    "final_institutional_score": round(final_score, 1),
    "pass_threshold": 80,
    "pass_status": "PASS" if final_score >= 80 else "FAIL",
}

print("\n  FINAL INSTITUTIONAL SCORE:")
for dim, data in scores.items():
    bar = '█' * max(1, int(data["score"] / 5))
    print(f"    {dim:25s}: {data['score']:3.0f}/100 {bar}")
print(f"    {'─' * 40}")
print(f"    {'WEIGHTED TOTAL':25s}: {round(final_score, 1):3.0f}/100")
print(f"    {'THRESHOLD (80+)':25s}: {'PASS' if final_score >= 80 else 'FAIL'}")

# Combine
report = {
    "phase_8_future_return_validation": phase8,
    "phase_9_remove_dead_factors": phase9,
    "phase_10_final_institutional_score": phase10,
}

with open("/Users/hemant/alpha-hunter/reports/predictive_power.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print("\n" + "="*60)
print("Phases 8-10 complete — saved to reports/predictive_power.json")
