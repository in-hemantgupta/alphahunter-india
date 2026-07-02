"""Final score distribution audit.
PHASE 4 — Score Distribution Verification.

Measures:
  - Score histogram (full distribution)
  - Bucket concentration (pass: 0-10 <10%, no bucket >18%, 90+ >3%)
  - Sector score bias (pass: sector deviation <15%)
  - Extreme tail distribution
  - Confidence distribution
  - Pass/fail summary

Usage:
    PYTHONPATH=. python scripts/final_distribution_audit.py
"""

import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import SessionLocal
from app.models.scored_stock import ScoredStock
from app.models.stock import Stock
from sqlalchemy import func


PASS_THRESHOLDS = {
    "spread": 90.0,
    "bucket_0_10": 10.0,
    "bucket_90plus": 3.0,
    "sector_deviation": 15.0,
    "max_bucket": 18.0,
    "min_score": 8.0,
    "max_score": 97.0,
}


def get_scores(session):
    rows = session.query(
        ScoredStock.total_score,
        ScoredStock.confidence_score,
        Stock.sector,
    ).join(Stock, ScoredStock.symbol == Stock.symbol).all()
    return [
        {"score": r[0], "confidence": r[1], "sector": r[2]}
        for r in rows if r[0] is not None
    ]


def histogram(scores, bins=range(0, 101, 10)):
    counts = {f"{lo}-{hi-1}": 0 for lo, hi in zip(bins, bins[1:])}
    counts["100"] = 0
    for s in scores:
        for lo, hi in zip(bins, bins[1:]):
            if lo <= s["score"] < hi:
                counts[f"{lo}-{hi-1}"] += 1
                break
        else:
            if s["score"] >= 100:
                counts["100"] += 1
    return counts


def bucket_analysis(scores):
    n = len(scores)
    buckets = {}
    for lo in range(0, 100, 10):
        hi = lo + 10
        cnt = sum(1 for s in scores if lo <= s["score"] < hi)
        buckets[f"{lo}-{hi-1}"] = {"count": cnt, "pct": (cnt / n * 100) if n else 0}
    cnt_90 = sum(1 for s in scores if s["score"] >= 90)
    cnt_100 = sum(1 for s in scores if s["score"] >= 100)
    buckets["90+"] = {"count": cnt_90, "pct": (cnt_90 / n * 100) if n else 0}
    buckets["100"] = {"count": cnt_100, "pct": (cnt_100 / n * 100) if n else 0}
    return buckets


def sector_bias(scores, total_n):
    sector_scores = {}
    for s in scores:
        sec = s["sector"] or "Unknown"
        if sec not in sector_scores:
            sector_scores[sec] = []
        sector_scores[sec].append(s["score"])

    overall_avg = sum(s["score"] for s in scores) / total_n if total_n else 0
    results = []
    for sec, sec_scores in sorted(sector_scores.items()):
        avg = sum(sec_scores) / len(sec_scores)
        deviation = abs(avg - overall_avg)
        results.append({
            "sector": sec,
            "count": len(sec_scores),
            "pct": len(sec_scores) / total_n * 100,
            "avg_score": round(avg, 1),
            "deviation": round(deviation, 1),
            "deviation_pct": round(deviation / overall_avg * 100, 1) if overall_avg else 0,
        })
    max_deviation = max((r["deviation"] for r in results), default=0)
    return results, max_deviation, overall_avg


def confidence_analysis(scores):
    confs = [s["confidence"] for s in scores if s["confidence"] is not None]
    n = len(confs)
    if not n:
        return {}
    avg = sum(confs) / n
    buckets = {}
    for lo_hi in [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]:
        lo, hi = lo_hi
        cnt = sum(1 for c in confs if lo <= c < hi)
        buckets[f"{lo:.1f}-{hi:.1f}"] = {"count": cnt, "pct": cnt / n * 100}
    return {
        "avg_confidence": round(avg, 3),
        "min_confidence": round(min(confs), 3),
        "max_confidence": round(max(confs), 3),
        "distribution": buckets,
    }


def run_audit():
    session = SessionLocal()
    try:
        raw = get_scores(session)
        n = len(raw)
        print(f"Total scored stocks: {n}")
        print()

        # Basic stats
        scores_vals = [s["score"] for s in raw]
        min_s = min(scores_vals)
        max_s = max(scores_vals)
        spread = max_s - min_s
        avg_s = sum(scores_vals) / n
        median_s = sorted(scores_vals)[n // 2]

        print("=== BASIC STATS ===")
        print(f"  Min:     {min_s:.1f}")
        print(f"  Max:     {max_s:.1f}")
        print(f"  Spread:  {spread:.1f}")
        print(f"  Mean:    {avg_s:.1f}")
        print(f"  Median:  {median_s:.1f}")
        print()

        # Histogram
        buckets = bucket_analysis(raw)
        print("=== BUCKET DISTRIBUTION ===")
        for lo in range(0, 100, 10):
            key = f"{lo}-{lo+9}"
            b = buckets[key]
            bar = "#" * (int(b["pct"]) // 2)
            print(f"  {key:>5}: {b['count']:4d} ({b['pct']:5.1f}%) |{bar}")
        b90 = buckets["90+"]
        bar90 = "#" * (int(b90["pct"]) // 2)
        print(f"   90+ : {b90['count']:4d} ({b90['pct']:5.1f}%) |{bar90}")
        print()

        # Max bucket
        max_bucket_pct = max(
            b["pct"] for k, b in buckets.items() if k not in ("90+", "100")
        )
        max_bucket_key = max(
            ((k, b["pct"]) for k, b in buckets.items() if k not in ("90+", "100")),
            key=lambda x: x[1],
        )[0]

        # Sector bias
        sec_results, max_dev, overall_avg = sector_bias(raw, n)
        print("=== SECTOR BIAS ===")
        print(f"  Overall avg: {overall_avg:.1f}")
        for r in sec_results[:10]:
            flag = " <-- HIGH" if r["deviation"] > PASS_THRESHOLDS["sector_deviation"] else ""
            print(f"  {r['sector']:20s}: n={r['count']:4d} avg={r['avg_score']:5.1f} "
                  f"dev={r['deviation']:5.1f}{flag}")
        if len(sec_results) > 10:
            print(f"  ... ({len(sec_results)} sectors total)")
        print(f"  Max deviation: {max_dev:.1f}")
        print()

        # Confidence analysis
        conf = confidence_analysis(raw)
        print("=== CONFIDENCE DISTRIBUTION ===")
        print(f"  Avg: {conf['avg_confidence']:.3f}  Min: {conf['min_confidence']:.3f}  "
              f"Max: {conf['max_confidence']:.3f}")
        for k, v in sorted(conf["distribution"].items()):
            bar_c = "#" * max(1, int(v["pct"] // 2))
            print(f"  {k}: {v['count']:4d} ({v['pct']:5.1f}%) |{bar_c}")
        print()

        # Pass/fail
        print("=== PASS/FAIL ===")
        checks = [
            ("Spread > 90", spread > PASS_THRESHOLDS["spread"],
             f"{spread:.1f} > {PASS_THRESHOLDS['spread']:.0f}"),
            ("Min score > 8", min_s > PASS_THRESHOLDS["min_score"],
             f"{min_s:.1f} > {PASS_THRESHOLDS['min_score']:.0f}"),
            ("Max score > 97", max_s > PASS_THRESHOLDS["max_score"],
             f"{max_s:.1f} > {PASS_THRESHOLDS['max_score']:.0f}"),
            ("0-10 bucket < 10%",
             buckets.get("0-9", {}).get("pct", 0) < PASS_THRESHOLDS["bucket_0_10"],
             f"{buckets.get('0-9', {}).get('pct', 0):.1f}% < {PASS_THRESHOLDS['bucket_0_10']:.0f}%"),
            ("90+ bucket > 3%",
             buckets["90+"]["pct"] > PASS_THRESHOLDS["bucket_90plus"],
             f"{buckets['90+']['pct']:.1f}% > {PASS_THRESHOLDS['bucket_90plus']:.0f}%"),
            ("Max bucket < 18%",
             max_bucket_pct < PASS_THRESHOLDS["max_bucket"],
             f"{max_bucket_pct:.1f}% < {PASS_THRESHOLDS['max_bucket']:.0f}%"),
            ("Sector deviation < 15",
             max_dev < PASS_THRESHOLDS["sector_deviation"],
             f"{max_dev:.1f} < {PASS_THRESHOLDS['sector_deviation']:.0f}"),
        ]
        passed = 0
        for name, ok, detail in checks:
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"  [{status}] {name:30s} ({detail})")
        print(f"\n  Score: {passed}/{len(checks)} checks passed")
        if passed == len(checks):
            print("  VERDICT: DISTRIBUTION PASS")
        elif passed >= len(checks) * 0.7:
            print("  VERDICT: DISTRIBUTION ACCEPTABLE")
        else:
            print("  VERDICT: DISTRIBUTION FAIL — corrective action needed")

        # Summary JSON
        summary = {
            "n": n,
            "min": min_s,
            "max": max_s,
            "spread": spread,
            "mean": round(avg_s, 1),
            "median": round(median_s, 1),
            "buckets": {k: round(v["pct"], 1) for k, v in buckets.items()},
            "max_bucket_pct": round(max_bucket_pct, 1),
            "max_bucket_key": max_bucket_key,
            "max_sector_deviation": round(max_dev, 1),
            "confidence": conf,
            "checks": {name: "pass" if ok else "fail" for name, ok, _ in checks},
            "score": f"{passed}/{len(checks)}",
        }
        json_path = "/tmp/distribution_audit.json"
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nReport saved to {json_path}")
        return summary

    finally:
        session.close()


if __name__ == "__main__":
    run_audit()
