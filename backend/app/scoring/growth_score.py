def growth_score(data, ranker=None, _debug=False):
    revenue_accel = data.get("revenue_acceleration") or 0
    pat_accel = data.get("pat_acceleration") or 0
    margin_exp = data.get("margin_expansion") or 0
    cf_improve = data.get("cashflow_improvement") or 0
    eps = data.get("eps") or 0
    revenue = data.get("revenue") or 0
    sector = data.get("sector")

    if ranker:
        rev_score = ranker.pct("revenue_acceleration", max(min(revenue_accel, 200), -200), sector=sector)
        pat_score_val = ranker.pct("pat_acceleration", max(min(pat_accel, 200), -200), sector=sector)
        margin_score = ranker.pct("margin_expansion", max(min(margin_exp, 500), -500), sector=sector)
        cf_score = ranker.pct("cashflow_improvement", cf_improve, sector=sector)
    else:
        rev_score = min(100, max(0, (revenue_accel + 50) / 2))
        pat_score_val = min(100, max(0, (pat_accel + 50) / 2))
        margin_score = min(100, max(0, (margin_exp + 100) / 5))
        cf_score = 60 if cf_improve > 0 else 40

    eps_score = min(100, max(0, eps * 5)) if eps else 40
    revenue_health = 60 if revenue > 0 else 30

    score = (
        rev_score * 0.25 +
        pat_score_val * 0.25 +
        margin_score * 0.15 +
        cf_score * 0.15 +
        eps_score * 0.10 +
        revenue_health * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "revenue_acceleration": {"raw": revenue_accel, "score": rev_score, "weight": 0.25},
                "pat_acceleration": {"raw": pat_accel, "score": pat_score_val, "weight": 0.25},
                "margin_expansion": {"raw": margin_exp, "score": margin_score, "weight": 0.15},
                "cashflow_improvement": {"raw": cf_improve, "score": cf_score, "weight": 0.15},
                "eps": {"raw": eps, "score": eps_score, "weight": 0.10},
                "revenue_health": {"raw": revenue, "score": revenue_health, "weight": 0.10},
            }
        }

    return final
