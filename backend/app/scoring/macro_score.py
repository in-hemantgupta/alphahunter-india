def macro_score(data, ranker=None, _debug=False):
    sector_rotation = data.get("sector_rotation") or 50
    returns_1y = data.get("returns_1y") or 0
    benchmark_return = data.get("benchmark_return") or 0
    fii_change = data.get("fii_change")
    market_cap = data.get("market_cap")

    sector_rot_score = max(0, min(100, sector_rotation))

    relative_perf = returns_1y - benchmark_return
    rs_score = 50
    if ranker:
        rel_key = "relative_performance_1y"
        rs_score = ranker.pct(rel_key, min(max(relative_perf, -100), 200))
    else:
        rs_score = min(100, max(0, 50 + relative_perf))

    fii_score = 50
    if fii_change is not None:
        fii_score = min(100, max(0, 50 + fii_change * 5))

    index_member = data.get("nifty_500_member")
    index_score = 60 if index_member else 40

    score = (
        sector_rot_score * 0.30 +
        rs_score * 0.30 +
        fii_score * 0.20 +
        index_score * 0.20
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "sector_rotation": {"raw": sector_rotation, "score": sector_rot_score, "weight": 0.30},
                "relative_performance": {"raw": round(relative_perf, 1), "score": rs_score, "weight": 0.30},
                "fii_flows": {"raw": fii_change, "score": fii_score, "weight": 0.20},
                "index_membership": {"raw": index_member, "score": index_score, "weight": 0.20},
            }
        }

    return final
