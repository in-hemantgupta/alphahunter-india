def fundamental_score(data, ranker=None, _debug=False):
    roce = data.get("roce") or 0
    debt_equity = data.get("debt_equity") or 1
    operating_margin = data.get("operating_margin") or 0
    margin_stability = data.get("margin_stability") or 0
    revenue = data.get("revenue") or 0
    pat = data.get("pat") or 0
    sector = data.get("sector")

    if ranker:
        roce_score = ranker.pct("roce", roce, sector=sector)
        debt_score = ranker.inverse_pct("debt_equity", min(debt_equity, 10), sector=sector)
        margin_score = ranker.pct("operating_margin", operating_margin, sector=sector)
        stability_val = ranker.pct("margin_stability", margin_stability, sector=sector)
    else:
        roce_score = min(100, roce * 4)
        debt_score = max(0, 100 - min(debt_equity, 5) * 20)
        margin_score = min(100, max(0, operating_margin * 5))
        stability_val = min(100, margin_stability)

    revenue_score = 60 if revenue > 0 else 30
    pat_score = 60 if pat > 0 else 20

    score = (
        roce_score * 0.30 +
        debt_score * 0.20 +
        margin_score * 0.15 +
        stability_val * 0.15 +
        revenue_score * 0.10 +
        pat_score * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "roce": {"raw": roce, "score": roce_score, "weight": 0.30},
                "debt_equity": {"raw": debt_equity, "score": debt_score, "weight": 0.20},
                "operating_margin": {"raw": operating_margin, "score": margin_score, "weight": 0.15},
                "margin_stability": {"raw": margin_stability, "score": stability_val, "weight": 0.15},
                "revenue": {"raw": revenue, "score": revenue_score, "weight": 0.10},
                "profitability": {"raw": pat, "score": pat_score, "weight": 0.10},
            }
        }

    return final
