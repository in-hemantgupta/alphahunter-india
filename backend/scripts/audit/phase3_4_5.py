"""PHASE 3 — Score Distribution Stress Test
PHASE 4 — Missing Data Bias Test
PHASE 5 — Score Stability Test"""
import json, sys, os, warnings, random, copy
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from scipy.stats import skew, kurtosis, pearsonr, spearmanr
from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.models.stock import Stock

session = SessionLocal()
stocks = session.query(ScoredStock).all()
stock_meta = {s.symbol: s for s in session.query(Stock).all()}
session.close()

scores = np.array([s.total_score for s in stocks if s.total_score is not None])
symbols = [s.symbol for s in stocks if s.total_score is not None]
n = len(scores)

print(f"Total scored stocks: {n}")

# ============================================================
# PHASE 3: Distribution Stress Test
# ============================================================
print("\n" + "="*60)
print("PHASE 3 — SCORE DISTRIBUTION STRESS TEST")
print("="*60)

mean_s = float(np.mean(scores))
median_s = float(np.median(scores))
std_s = float(np.std(scores))
min_s = float(np.min(scores))
max_s = float(np.max(scores))
skew_s = float(skew(scores))
kurt_s = float(kurtosis(scores, fisher=True))  # excess kurtosis

print(f"  Min: {min_s:.2f}")
print(f"  Max: {max_s:.2f}")
print(f"  Avg: {mean_s:.2f}")
print(f"  Median: {median_s:.2f}")
print(f"  Std Dev: {std_s:.2f}")
print(f"  Skewness: {skew_s:.4f}")
print(f"  Kurtosis (excess): {kurt_s:.4f}")

# Bucket concentration
buckets = [(i, i+10) for i in range(0, 100, 10)]
bucket_counts = {}
bucket_pcts = {}
for lo, hi in buckets:
    cnt = int(np.sum((scores >= lo) & (scores < hi)))
    bucket_counts[f"{lo}-{hi}"] = cnt
    bucket_pcts[f"{lo}-{hi}"] = round(cnt / n * 100, 2)

print("\n  Bucket concentration:")
max_bucket_pct = 0
max_bucket_name = ""
for bname, pct in bucket_pcts.items():
    marker = " *** >25% CONCENTRATION" if pct > 25 else ""
    if pct > max_bucket_pct:
        max_bucket_pct = pct
        max_bucket_name = bname
    print(f"    {bname:>5s}: {bucket_counts[bname]:>4d} stocks ({pct:5.2f}%){marker}")

buckets_flagged = {k: v for k, v in bucket_pcts.items() if v > 25}

# Sector-level distribution
sector_scores = {}
stock_meta_map = {s.symbol: s.sector for s in session.query(Stock).all()}
for s in stocks:
    sec = stock_meta_map.get(s.symbol) or "Unknown"
    if sec not in sector_scores:
        sector_scores[sec] = []
    if s.total_score is not None:
        sector_scores[sec].append(s.total_score)

print("\n  Sector-level distributions:")
sector_stats = {}
flagged_sectors = []
for sec in sorted(sector_scores.keys(), key=lambda s: -np.mean(sector_scores[s])):
    vals = sector_scores[sec]
    if len(vals) < 5:
        continue
    m = float(np.mean(vals))
    sd = float(np.std(vals))
    med = float(np.median(vals))
    sector_stats[sec] = {"count": len(vals), "mean": round(m, 2), "median": round(med, 2), "std": round(sd, 2)}
    flag = " *** HIGH" if m > 50 else " *** LOW" if m < 20 else ""
    if flag:
        flagged_sectors.append({"sector": sec, "mean": round(m, 2), "flag": flag.strip()})
    print(f"    {sec:25s}: n={len(vals):>4d} mean={m:6.2f} median={med:6.2f} std={sd:5.2f}{flag}")

phase3 = {
    "n_stocks": n,
    "min_score": round(min_s, 2),
    "max_score": round(max_s, 2),
    "average": round(mean_s, 2),
    "median": round(median_s, 2),
    "std_dev": round(std_s, 2),
    "skewness": round(skew_s, 4),
    "kurtosis_excess": round(kurt_s, 4),
    "bucket_concentration": bucket_pcts,
    "max_bucket": max_bucket_name,
    "max_bucket_pct": max_bucket_pct,
    "buckets_flagged_gt25": buckets_flagged,
    "sector_distributions": sector_stats,
    "flagged_sectors": flagged_sectors,
}

# ============================================================
# PHASE 4: Missing Data Bias Test
# ============================================================
print("\n" + "="*60)
print("PHASE 4 — MISSING DATA BIAS TEST")
print("="*60)

LAYER_COLS = [
    "quality_score", "growth_score", "momentum_score", "technical_score",
    "microstructure_score", "management_score", "forensic_score",
    "lowvol_score", "macro_score", "alternative_score", "value_score"
]
QUARTERLY_FIELDS = [
    "roce", "roe", "debt_equity", "revenue_acceleration", "pat_acceleration",
    "margin_expansion", "promoter_change", "pledge_percent"
]
ALL_FIELDS = LAYER_COLS + QUARTERLY_FIELDS

missing_ratios = []
total_scores_4 = []
confidence_scores = []

for s in stocks:
    missing = 0
    total = len(ALL_FIELDS)
    for k in ALL_FIELDS:
        v = getattr(s, k, None)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            missing += 1
    missing_ratios.append(missing / total)
    total_scores_4.append(s.total_score if s.total_score is not None else 0)
    cs = getattr(s, "confidence_score", None)
    confidence_scores.append(cs if cs is not None else 0)

mr_arr = np.array(missing_ratios)
ts_arr = np.array(total_scores_4)
cs_arr = np.array(confidence_scores)

# Correlation: missing_ratio vs total_score
r_miss_score, p_miss_score = pearsonr(mr_arr, ts_arr)
rho_miss_score, p_rho_miss = spearmanr(mr_arr, ts_arr)

# Correlation: total_score vs confidence_score
r_score_conf, p_score_conf = pearsonr(ts_arr, cs_arr)
rho_score_conf, p_rho_conf = spearmanr(ts_arr, cs_arr)

# Correlation: missing_ratio vs confidence_score
r_miss_conf, p_miss_conf = pearsonr(mr_arr, cs_arr)

print(f"  corr(missing_ratio, total_score):  Pearson r={r_miss_score:.4f} (p={p_miss_score:.6f})")
print(f"  corr(missing_ratio, total_score):  Spearman ρ={rho_miss_score:.4f} (p={p_rho_miss:.6f})")
print(f"  corr(total_score, confidence):     Pearson r={r_score_conf:.4f} (p={p_score_conf:.6f})")
print(f"  corr(total_score, confidence):     Spearman ρ={rho_score_conf:.4f} (p={p_rho_conf:.6f})")
print(f"  corr(missing_ratio, confidence):   Pearson r={r_miss_conf:.4f} (p={p_miss_conf:.6f})")

# Check high-score + low-confidence cases
high_score_low_conf = []
for i, s in enumerate(stocks):
    if total_scores_4[i] > 50 and confidence_scores[i] < 0.3:
        high_score_low_conf.append({
            "symbol": s.symbol,
            "total_score": round(total_scores_4[i], 1),
            "confidence": round(confidence_scores[i], 3),
            "missing_ratio": round(missing_ratios[i], 3)
        })

print(f"\n  High-score (>50) + low-confidence (<0.3): {len(high_score_low_conf)} stocks")
for h in high_score_low_conf[:10]:
    print(f"    {h['symbol']}: score={h['total_score']} conf={h['confidence']} missing={h['missing_ratio']}")

phase4 = {
    "n_stocks": n,
    "total_fields_checked": len(ALL_FIELDS),
    "fields": ALL_FIELDS,
    "corr_missing_ratio_vs_total_score": {
        "pearson_r": round(float(r_miss_score), 4),
        "pearson_p": float(p_miss_score),
        "spearman_rho": round(float(rho_miss_score), 4),
        "spearman_p": float(p_rho_miss),
    },
    "corr_total_score_vs_confidence": {
        "pearson_r": round(float(r_score_conf), 4),
        "pearson_p": float(p_score_conf),
        "spearman_rho": round(float(rho_score_conf), 4),
        "spearman_p": float(p_rho_conf),
    },
    "corr_missing_ratio_vs_confidence": {
        "pearson_r": round(float(r_miss_conf), 4),
        "pearson_p": float(p_miss_conf),
    },
    "high_score_low_confidence_count": len(high_score_low_conf),
    "high_score_low_confidence_examples": high_score_low_conf[:20],
}

# ============================================================
# PHASE 5: Score Stability Test (simplified — model-level)
# ============================================================
print("\n" + "="*60)
print("PHASE 5 — SCORE STABILITY TEST")
print("="*60)

# Since we can't re-run the full scoring pipeline for 100 MC sims x 2395 stocks,
# we use the layer_breakdown_json to recompute scores with ±5% perturbed components.
# For stocks without breakdown, use sensitivity estimation.

def perturb_value(v, pct=0.05):
    if v is None or v == 0:
        return v
    delta = v * pct * random.uniform(-1, 1)
    return v + delta

n_sim = 100
n_sample = 500  # sample 500 for speed

stable_scores = []
unstable_stocks = []

for idx in range(min(n_sample, len(stocks))):
    s = stocks[idx]
    base_score = s.total_score if s.total_score else 0
    sim_scores = []

    for _ in range(n_sim):
        # Perturb each layer score by ±5%
        perturbed = {}
        for k in LAYER_COLS:
            v = getattr(s, k, None)
            perturbed[k] = perturb_value(v)
        # Recompute composite from perturbed scores (= rough estimate)
        weights = {
            "quality_score": 0.125, "growth_score": 0.125, "momentum_score": 0.15,
            "technical_score": 0.12, "microstructure_score": 0.12, "management_score": 0.10,
            "forensic_score": 0.10, "lowvol_score": 0.05, "macro_score": 0.03,
            "alternative_score": 0.03, "value_score": 0.05
        }
        # Penalty from forensic
        pen = max(0, min(100, 100 - (perturbed.get("forensic_score") or 50)))
        sim = 0
        tw = 0
        for k, w in weights.items():
            v = perturbed.get(k)
            if v is not None and v >= 0:
                # Check data quality (layer active only if >= 30% populated)
                # Skip management if missing
                if k == "management_score" and v == 50:
                    continue
                sim += v * w
                tw += w
        sim = sim / tw if tw > 0 else 0
        sim_score = sim * (1 - pen / 100)
        sim_scores.append(sim_score)

    sim_arr = np.array(sim_scores)
    score_vol = float(np.std(sim_arr))
    stable_scores.append({"symbol": s.symbol, "base_score": round(base_score, 1),
                          "volatility": round(score_vol, 3),
                          "volatility_pct": round(score_vol / max(base_score, 1) * 100, 1)})
    if score_vol > 15:
        unstable_stocks.append({"symbol": s.symbol, "base_score": round(base_score, 1),
                                "volatility": round(score_vol, 3)})

all_vols = [x["volatility"] for x in stable_scores]
print(f"  MC simulations per stock: {n_sim}")
print(f"  Stocks sampled: {len(stable_scores)}")
print(f"  Mean score volatility: {np.mean(all_vols):.3f}")
print(f"  Median score volatility: {np.median(all_vols):.3f}")
print(f"  Max score volatility: {np.max(all_vols):.3f}")
print(f"  Unstable stocks (vol >15): {len(unstable_stocks)}")
for u in unstable_stocks[:5]:
    print(f"    {u['symbol']}: base={u['base_score']} vol={u['volatility']}")

phase5 = {
    "methodology": "Monte Carlo ±5% perturbation of each layer score, 100 sims per stock, n=500 sample",
    "n_simulations": n_sim,
    "n_stocks_sampled": len(stable_scores),
    "mean_score_volatility": round(float(np.mean(all_vols)), 3),
    "median_score_volatility": round(float(np.median(all_vols)), 3),
    "max_score_volatility": round(float(np.max(all_vols)), 3),
    "unstable_stocks_count": len(unstable_stocks),
    "unstable_stocks": unstable_stocks[:20],
    "all_stock_stabilities": [x for x in stable_scores if x["volatility"] > 5][:30],
    "flag": "VOLATILITY > 15 DETECTED" if len(unstable_stocks) > 0 else "PASS"
}

# Combine all three phases
report = {
    "phase_3_distribution": phase3,
    "phase_4_missing_data_bias": phase4,
    "phase_5_stability_test": phase5,
}

with open("/Users/hemant/alpha-hunter/reports/distribution_audit.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print("\n" + "="*60)
print("Phases 3-5 complete — saved to reports/distribution_audit.json")
