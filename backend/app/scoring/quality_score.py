def quality_score(data, ranker=None, _debug=False):
    roce = data.get("roce")
    roe = data.get("roe")
    debt_equity = data.get("debt_equity")
    operating_margin = data.get("operating_margin")
    sector = data.get("sector")

    # Purified Piotroski F-Score (no cashflow, no revenue/PAT/growth/margin overlap)
    fscore = 0
    f_components = []

    # 1. Positive ROA (proxy: positive ROCE)
    if roce is not None and roce > 0:
        fscore += 1
        f_components.append("roa_positive")

    # 2. Leverage reduction
    de_prev = data.get("debt_equity_prev")
    if debt_equity is not None and de_prev is not None:
        if debt_equity < de_prev:
            fscore += 1
            f_components.append("leverage_reducing")

    # 3. No dilution
    dilution = data.get("dilution_rate") or 0
    if dilution == 0:
        fscore += 1
        f_components.append("no_dilution")

    fscore_score = min(100, fscore * 33)

    if ranker:
        roce_score = ranker.pct("roce", roce, sector=sector) if roce is not None else 50
        roe_score = ranker.pct("roe", roe, sector=sector) if roe is not None else 50
        de_score = ranker.inverse_pct("debt_equity", min(debt_equity, 10), sector=sector) if debt_equity is not None else 50
        om_score = ranker.pct("operating_margin", operating_margin, sector=sector) if operating_margin is not None else 50
    else:
        roce_score = min(100, (roce or 0) * 4)
        roe_score = min(100, (roe or 0) * 4)
        de_score = max(0, 100 - min(debt_equity or 1, 5) * 20)
        om_score = min(100, max(0, (operating_margin or 0) * 5))

    score = (
        roce_score * 0.30 +
        roe_score * 0.15 +
        de_score * 0.15 +
        om_score * 0.20 +
        fscore_score * 0.20
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "roce": {"raw": roce, "score": roce_score, "weight": 0.30},
                "roe": {"raw": roe, "score": roe_score, "weight": 0.15},
                "debt_equity": {"raw": debt_equity, "score": de_score, "weight": 0.15},
                "operating_margin": {"raw": operating_margin, "score": om_score, "weight": 0.20},
                "fscore": {"raw": f"f{fscore}/{len(f_components)}", "score": fscore_score, "weight": 0.20},
            }
        }

    return final