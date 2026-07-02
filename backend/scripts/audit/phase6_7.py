"""PHASE 6 — Top 100 Stock Sanity Check
PHASE 7 — Score Explainability Audit (top 50 decomposition)"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.models.stock import Stock
from app.models.quarterly import QuarterlyFinancials

session = SessionLocal()

stocks = session.query(ScoredStock).order_by(ScoredStock.total_score.desc()).all()
stock_meta = {s.symbol: s for s in session.query(Stock).all()}

# Get latest quarterly data for top 100
top100_symbols = [s.symbol for s in stocks[:100] if s.total_score is not None]
latest_q = {}
for sym in top100_symbols:
    q = session.query(QuarterlyFinancials).filter_by(symbol=sym).order_by(
        QuarterlyFinancials.quarter.desc()).first()
    prev_q = session.query(QuarterlyFinancials).filter_by(symbol=sym).order_by(
        QuarterlyFinancials.quarter.desc()).offset(1).first()
    latest_q[sym] = {"latest": q, "prev": prev_q}

session.close()

# ============================================================
# PHASE 6: Top 100 Sanity Check
# ============================================================
print("="*60)
print("PHASE 6 — TOP 100 SANITY CHECK")
print("="*60)

audit_results = []
absurd_cases = []

for i, s in enumerate(stocks[:100]):
    if s.total_score is None:
        continue
    meta = stock_meta.get(s.symbol)
    qdata = latest_q.get(s.symbol, {})
    lq = qdata.get("latest")
    pq = qdata.get("prev")

    # Check revenue growth
    rev_growth = None
    if lq and pq and lq.revenue and pq.revenue and pq.revenue > 0:
        rev_growth = (lq.revenue - pq.revenue) / pq.revenue * 100

    # Check PAT growth
    pat_growth = None
    if lq and pq and lq.pat and pq.pat and pq.pat > 0:
        pat_growth = (lq.pat - pq.pat) / pq.pat * 100

    # Check debt
    debt_eq = lq.debt_equity if lq else None
    has_pledge = s.pledge_percent is not None and s.pledge_percent > 0

    # Check momentum (returns_6m stored in scored_stocks)
    mom_positive = s.returns_6m is not None and s.returns_6m > 0

    # Check liquidity (volume_ratio)
    liq_ok = s.volume_ratio is not None and s.volume_ratio > 0.5

    # Flag issues
    issues = []
    if rev_growth is not None and rev_growth < 0:
        issues.append(f"revenue_declining({rev_growth:.1f}%)")
    if pat_growth is not None and pat_growth < 0:
        issues.append(f"pat_declining({pat_growth:.1f}%)")
    if debt_eq is not None and debt_eq > 3:
        issues.append(f"high_debt({debt_eq:.1f})")
    if has_pledge:
        issues.append(f"pledge({s.pledge_percent:.1f}%)")
    if not mom_positive:
        issues.append("negative_momentum")
    if not liq_ok:
        issues.append("low_liquidity")

    is_absurd = len(issues) >= 2 and "pat_declining" in str(issues) and "revenue_declining" in str(issues)

    record = {
        "rank": i + 1,
        "symbol": s.symbol,
        "company": s.company_name or meta.company_name if meta else "",
        "sector": meta.sector if meta else "Unknown",
        "total_score": round(s.total_score, 1),
        "revenue_growth_pct": round(rev_growth, 1) if rev_growth is not None else None,
        "pat_growth_pct": round(pat_growth, 1) if pat_growth is not None else None,
        "debt_equity": round(debt_eq, 2) if debt_eq is not None else None,
        "pledge_pct": round(s.pledge_percent, 1) if s.pledge_percent is not None else None,
        "momentum_positive": mom_positive,
        "liquidity_ok": liq_ok,
        "issues": issues,
        "absurd_flag": is_absurd,
    }
    audit_results.append(record)
    if is_absurd:
        absurd_cases.append(record)
        print(f"  #{i+1} {s.symbol}: ABSURD — {', '.join(issues)}")

# Summary stats
total_issues = sum(1 for r in audit_results if r["issues"])
rev_declining = sum(1 for r in audit_results if any("revenue_declining" in x for x in r["issues"]))
pat_declining = sum(1 for r in audit_results if any("pat_declining" in x for x in r["issues"]))
high_debt = sum(1 for r in audit_results if any("high_debt" in x for x in r["issues"]))
has_pledge_count = sum(1 for r in audit_results if any("pledge" in x for x in r["issues"]))
neg_mom = sum(1 for r in audit_results if any("negative_momentum" in x for x in r["issues"]))
low_liq = sum(1 for r in audit_results if any("low_liquidity" in x for x in r["issues"]))

print(f"\nTop 100 Sanity Check Results:")
print(f"  Stocks with issues: {total_issues}/100")
print(f"  Revenue declining: {rev_declining}")
print(f"  PAT declining: {pat_declining}")
print(f"  High debt: {high_debt}")
print(f"  Has pledge: {has_pledge_count}")
print(f"  Negative momentum: {neg_mom}")
print(f"  Low liquidity: {low_liq}")
print(f"  Absurd cases (revenue+PAT declining): {len(absurd_cases)}")
for a in absurd_cases:
    print(f"    #{a['rank']} {a['symbol']} score={a['total_score']}")

phase6 = {
    "n_audited": len(audit_results),
    "stocks_with_issues": total_issues,
    "revenue_declining": rev_declining,
    "pat_declining": pat_declining,
    "high_debt_gt3": high_debt,
    "has_pledge": has_pledge_count,
    "negative_momentum": neg_mom,
    "low_liquidity": low_liq,
    "absurd_cases": absurd_cases,
    "all_audits": audit_results,
}

# ============================================================
# PHASE 7: Explainability Audit
# ============================================================
print("\n" + "="*60)
print("PHASE 7 — SCORE EXPLAINABILITY AUDIT (Top 50)")
print("="*60)

LAYER_NAMES = [
    "quality_score", "growth_score", "momentum_score", "technical_score",
    "microstructure_score", "management_score", "forensic_score",
    "lowvol_score", "macro_score", "alternative_score", "value_score"
]
LAYER_DISPLAY = {
    "quality_score": "Quality", "growth_score": "Growth", "momentum_score": "Momentum",
    "technical_score": "Technical", "microstructure_score": "Microstr.", "management_score": "Management",
    "forensic_score": "Forensic", "lowvol_score": "LowVol",
    "macro_score": "Macro", "alternative_score": "Alternative", "value_score": "Value"
}

explainability_rows = []

for i, s in enumerate(stocks[:50]):
    if s.total_score is None:
        continue
    layers = {}
    for k in LAYER_NAMES:
        v = getattr(s, k, None)
        layers[LAYER_DISPLAY[k]] = round(v, 1) if v is not None else None

    row = {
        "rank": i + 1,
        "symbol": s.symbol,
        "total_score": round(s.total_score, 1),
        "confidence": round(getattr(s, "confidence_score", 0) or 0, 3),
        "layers": layers,
    }

    # Detect issues
    if s.total_score > 50 and any(v is None or v < 30 for v in layers.values() if v is not None):
        row["hidden_weighting_issue"] = True
    else:
        row["hidden_weighting_issue"] = False

    explainability_rows.append(row)

    print(f"\n  #{i+1} {s.symbol:12s} Score: {s.total_score:.1f}  Confidence: {getattr(s, 'confidence_score', 0):.3f}")
    for dname in LAYER_DISPLAY.values():
        v = layers.get(dname)
        if v is not None:
            bar = '█' * max(1, int(v / 5))
            print(f"    {dname:15s}: {v:5.1f} {bar}")
        else:
            print(f"    {dname:15s}: {'N/A':>5s}")

# Check for weighting errors
weighting_issues = [r for r in explainability_rows if r.get("hidden_weighting_issue")]
print(f"\nHidden weighting issues detected: {len(weighting_issues)}/50")
if weighting_issues:
    print("  Stocks with high score but weak layer components:")
    for w in weighting_issues[:5]:
        print(f"    #{w['rank']} {w['symbol']}: score={w['total_score']}")

phase7 = {
    "n_top_stocks": len(explainability_rows),
    "hidden_weighting_issues": len(weighting_issues),
    "explainability": explainability_rows,
}

report = {
    "phase_6_top100_sanity": phase6,
    "phase_7_explainability": phase7,
}

with open("/Users/hemant/alpha-hunter/reports/top100_manual_audit.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print("\n" + "="*60)
print("Phases 6 & 7 complete — saved to reports/top100_manual_audit.json")
