"""PHASE 2 — Feature Importance Test
No forward returns available (scores from 2026-06-30, no future prices).
Use returns_1y (stored in scored_stocks) as target, exclude momentum_score.
Impute missing factors with 50 (neutral PercentileRanker default)."""
import json, sys, os, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from scipy.stats import spearmanr, pearsonr
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score, KFold
from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock

ALL_LAYERS = [
    "quality_score", "growth_score", "momentum_score", "technical_score",
    "microstructure_score", "management_score", "forensic_score",
    "lowvol_score", "macro_score", "alternative_score", "value_score"
]

# Exclude momentum from feature set when predicting returns (circular)
# Also exclude management (only 13/2395)
FEATURE_LAYERS = [k for k in ALL_LAYERS if k not in ("momentum_score", "management_score")]

session = SessionLocal()
stocks = session.query(ScoredStock).all()
session.close()
print(f"Loaded {len(stocks)} scored stocks")

# Feature matrix with imputation (neutral 50)
X = np.zeros((len(stocks), len(FEATURE_LAYERS)))
Y_1y = np.zeros(len(stocks))
Y_6m = np.zeros(len(stocks))
Y_score = np.zeros(len(stocks))
valid_mask = np.ones(len(stocks), dtype=bool)

for i, s in enumerate(stocks):
    for j, k in enumerate(FEATURE_LAYERS):
        v = getattr(s, k, None)
        X[i, j] = v if v is not None else 50.0  # impute neutral
    Y_1y[i] = s.returns_1y if s.returns_1y is not None else 0
    Y_6m[i] = s.returns_6m if s.returns_6m is not None else 0
    Y_score[i] = s.total_score if s.total_score is not None else 0

# Remove NaN rows
nan_mask = ~(np.isnan(X).any(axis=1) | np.isnan(Y_1y))
# But with imputation there should be no NaNs
print(f"Feature matrix shape: {X.shape}")
print(f"Features: {FEATURE_LAYERS}")

# Target 1: returns_1y
y_targets = {
    "past_1y_return": Y_1y,
    "past_6m_return": Y_6m,
    "total_score": Y_score,
}

results = {}
for tname, y in y_targets.items():
    print(f"\n{'='*50}")
    print(f"TARGET: {tname}")
    print(f"Y range: {y.min():.2f} to {y.max():.2f}, mean={y.mean():.2f}")

    rf = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    imp = {FEATURE_LAYERS[i]: round(float(rf.feature_importances_[i]), 4) for i in range(len(FEATURE_LAYERS))}
    imp_sorted = sorted(imp.items(), key=lambda x: -x[1])

    cv_r2 = cross_val_score(rf, X, y, cv=KFold(5, shuffle=True, random_state=42), scoring='r2').mean()

    pred = rf.predict(X)
    ic, ic_p = spearmanr(pred, y)

    print(f"  RF CV R² = {cv_r2:.4f}")
    print(f"  Spearman IC = {ic:.4f} (p={ic_p:.6f})")
    print("  Feature Importance:")
    for k, v in imp_sorted:
        bar = '█' * max(1, int(v * 200))
        print(f"    {k:20s}: {v:.4f} {bar}")

    zero_imp = [k for k, v in imp.items() if v < 0.01]
    if zero_imp:
        print(f"  LOW/ZERO importance (<1%): {zero_imp}")

    results[tname] = {
        "n_stocks": len(stocks),
        "n_features": len(FEATURE_LAYERS),
        "rf_cv_r2": round(float(cv_r2), 4),
        "spearman_ic": round(float(ic), 4),
        "ic_p_value": float(ic_p),
        "feature_importance": imp,
        "feature_importance_sorted": [(k, v) for k, v in imp_sorted],
        "low_importance_features": zero_imp,
    }

# Also compute simple pairwise IC: each factor score vs returns_1y
pairwise_ic = {}
for k in ALL_LAYERS:
    vals = np.array([float(getattr(s, k, 50) or 50) for s in stocks])
    ic, p = spearmanr(vals, Y_1y)
    pairwise_ic[k] = {"spearman_r": round(float(ic), 4), "p_value": float(p)}

results["pairwise_ic_vs_returns_1y"] = pairwise_ic

report = {
    "methodology": "RandomForestRegressor CV R² + Spearman IC, impute missing=50, exclude momentum from feature set",
    "n_stocks": len(stocks),
    "features": FEATURE_LAYERS,
    "all_layers": ALL_LAYERS,
    "score_date": "2026-06-30",
    "limitations": [
        "No forward returns available — scores are from today, price history ends today",
        "Using past returns (returns_1y, returns_6m) as proxy targets",
        "management_score only has 13/2395 values — excluded from feature set",
        "Missing factor scores imputed to 50 (neutral percentile rank)"
    ],
    "results": results,
}

with open("/Users/hemant/alpha-hunter/reports/feature_importance.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print("\n" + "=" * 60)
print("PHASE 2 COMPLETE — saved to reports/feature_importance.json")
