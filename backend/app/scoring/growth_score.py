def growth_score(data, ranker=None, _debug=False):
    """Rule 1/5: each component only contributes when its underlying field is
    actually known. `revenue_acceleration or 0` used to treat "no data" and
    "confirmed zero acceleration" as the same input, diluting the score with
    default-driven values instead of excluding the missing ones and
    renormalizing the remaining weights (same pattern as management_score.py)."""
    revenue_accel = data.get("revenue_acceleration")
    pat_accel = data.get("pat_acceleration")
    margin_exp = data.get("margin_expansion")
    cf_improve = data.get("cashflow_improvement")
    eps = data.get("eps")
    revenue = data.get("revenue")
    sector = data.get("sector")

    components = {}  # name -> (score, weight, raw)

    if revenue_accel is not None:
        clamped = max(min(revenue_accel, 200), -200)
        s = ranker.pct("revenue_acceleration", clamped, sector=sector) if ranker else min(100, max(0, (clamped + 50) / 2))
        components["revenue_acceleration"] = (s, 0.25, revenue_accel)

    if pat_accel is not None:
        clamped = max(min(pat_accel, 200), -200)
        s = ranker.pct("pat_acceleration", clamped, sector=sector) if ranker else min(100, max(0, (clamped + 50) / 2))
        components["pat_acceleration"] = (s, 0.25, pat_accel)

    if margin_exp is not None:
        clamped = max(min(margin_exp, 500), -500)
        s = ranker.pct("margin_expansion", clamped, sector=sector) if ranker else min(100, max(0, (clamped + 100) / 5))
        components["margin_expansion"] = (s, 0.15, margin_exp)

    if cf_improve is not None:
        s = ranker.pct("cashflow_improvement", cf_improve, sector=sector) if ranker else (60 if cf_improve > 0 else 40)
        components["cashflow_improvement"] = (s, 0.15, cf_improve)

    if eps is not None:
        components["eps"] = (min(100, max(0, eps * 5)), 0.10, eps)

    if revenue is not None:
        components["revenue_health"] = (60 if revenue > 0 else 30, 0.10, revenue)

    total_weight = sum(w for _, w, _ in components.values())
    score = sum(s * w for s, w, _ in components.values()) / total_weight if total_weight > 0 else 50

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                name: {"raw": raw, "score": s, "weight": w}
                for name, (s, w, raw) in components.items()
            },
        }

    return final
