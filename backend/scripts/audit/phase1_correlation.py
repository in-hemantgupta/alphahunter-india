"""PHASE 1 — Factor Correlation Deep Audit"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from scipy.stats import pearsonr, spearmanr
from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock

LAYERS = [
    "quality_score", "growth_score", "momentum_score", "technical_score",
    "microstructure_score", "management_score", "forensic_score",
    "lowvol_score", "macro_score", "alternative_score", "value_score"
]

session = SessionLocal()
stocks = session.query(ScoredStock).all()
session.close()

data = {k: [] for k in LAYERS}
symbols = []
for s in stocks:
    symbols.append(s.symbol)
    for k in LAYERS:
        v = getattr(s, k, None)
        data[k].append(v if v is not None else np.nan)

arr = np.column_stack([data[k] for k in LAYERS])
n = len(LAYERS)

# Pearson
pearson_mat = np.full((n, n), np.nan)
for i in range(n):
    for j in range(n):
        mask = ~(np.isnan(arr[:, i]) | np.isnan(arr[:, j]))
        if mask.sum() > 10:
            r, p = pearsonr(arr[mask, i], arr[mask, j])
            pearson_mat[i, j] = round(r, 4)

# Spearman
spearman_mat = np.full((n, n), np.nan)
for i in range(n):
    for j in range(n):
        mask = ~(np.isnan(arr[:, i]) | np.isnan(arr[:, j]))
        if mask.sum() > 10:
            r, p = spearmanr(arr[mask, i], arr[mask, j])
            spearman_mat[i, j] = round(r, 4)

# Flag correlations
flags = {"over_40": [], "over_60_critical": []}
for i in range(n):
    for j in range(i+1, n):
        v = pearson_mat[i, j]
        if not np.isnan(v):
            if v > 0.60:
                flags["over_60_critical"].append({
                    "pair": f"{LAYERS[i]} vs {LAYERS[j]}", "pearson_r": v
                })
            elif v > 0.40:
                flags["over_40"].append({
                    "pair": f"{LAYERS[i]} vs {LAYERS[j]}", "pearson_r": v
                })

pearson_rows = []
for i in range(n):
    row = {"layer": LAYERS[i]}
    for j in range(n):
        row[LAYERS[j]] = pearson_mat[i, j]
    pearson_rows.append(row)

spearman_rows = []
for i in range(n):
    row = {"layer": LAYERS[i]}
    for j in range(n):
        row[LAYERS[j]] = spearman_mat[i, j]
    spearman_rows.append(row)

result = {
    "n_stocks": len(stocks),
    "layers": LAYERS,
    "pearson_matrix": pearson_rows,
    "spearman_matrix": spearman_rows,
    "flags": flags,
    "summary": {
        "total_pairs": n * (n - 1) // 2,
        "over_40_count": len(flags["over_40"]),
        "over_60_count": len(flags["over_60_critical"]),
    }
}

os.makedirs("/Users/hemant/alpha-hunter/reports", exist_ok=True)
with open("/Users/hemant/alpha-hunter/reports/factor_correlation.json", "w") as f:
    json.dump(result, f, indent=2, default=str)

# Print summary
print("=" * 60)
print("PHASE 1 — FACTOR CORRELATION DEEP AUDIT")
print("=" * 60)
print(f"Stocks analyzed: {len(stocks)}")
print(f"Layers: {len(LAYERS)}")
print(f"Pairs above 0.40: {len(flags['over_40'])}")
print(f"Pairs above 0.60 (critical): {len(flags['over_60_critical'])}")
print()
if flags["over_40"]:
    print("CORRELATION WARNINGS (>0.40):")
    for f in flags["over_40"]:
        print(f"  {f['pair']}: {f['pearson_r']:.3f}")
if flags["over_60_critical"]:
    print("CRITICAL DUPLICATION (>0.60):")
    for f in flags["over_60_critical"]:
        print(f"  {f['pair']}: {f['pearson_r']:.3f}")

print()
print("Pearson matrix (upper triangle):")
for i in range(n):
    row_vals = []
    for j in range(i+1, n):
        v = pearson_mat[i, j]
        row_vals.append(f"{f'{LAYERS[j][:8]}={v:.3f}' if not np.isnan(v) else 'N/A'}")
    if row_vals:
        print(f"  {LAYERS[i][:15]:15s}: {', '.join(row_vals)}")

print()
if not flags["over_40"] and not flags["over_60_critical"]:
    print("PASS: No layer correlation > 0.40")
else:
    print(f"ISSUE: {len(flags['over_40'])} pairs > 0.40, {len(flags['over_60_critical'])} > 0.60")
