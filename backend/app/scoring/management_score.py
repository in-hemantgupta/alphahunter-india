def management_score(data, ranker=None, _debug=False):
    """Rule 1/5: a missing input must not silently become "0" or "False" and
    get scored as if that were a real, verified reading - e.g. unknown
    dilution_rate treated as dilution_rate=0 previously handed every stock a
    perfect dilution score whether or not any dilution data actually existed.
    Each component below only contributes to the weighted average when its
    underlying data is actually present; missing components are excluded and
    the remaining weights renormalize, the same pattern alpha_engine.py uses
    at the layer level (Rule 5)."""
    promoter_change = data.get("promoter_change")
    pledge_percent = data.get("pledge_percent")
    roce_trend = data.get("roce_trend")
    capex_efficiency = data.get("capex_efficiency")
    operating_cashflow = data.get("operating_cashflow")
    dilution_rate = data.get("dilution_rate")
    governance_clean = data.get("governance_clean")
    sector = data.get("sector")

    components = {}  # name -> (score, weight, raw)

    if promoter_change is not None:
        if ranker:
            s = ranker.pct("promoter_change", promoter_change)
        else:
            s = min(100, max(0, 50 + promoter_change * 5))
        components["promoter_behavior"] = (s, 0.25, promoter_change)

    if governance_clean is not None:
        s = 85 if governance_clean else 30
        components["governance"] = (s, 0.20, governance_clean)

    if operating_cashflow is not None:
        if ranker:
            s = ranker.pct("operating_cashflow", operating_cashflow, sector=sector)
        else:
            s = 70 if operating_cashflow > 0 else 30
        components["cashflow_quality"] = (s, 0.20, operating_cashflow)

    if pledge_percent is not None:
        if ranker:
            s = ranker.inverse_pct("pledge_percent", min(pledge_percent, 100))
        else:
            s = max(0, 100 - pledge_percent * 2)
        components["pledge_risk"] = (s, 0.20, pledge_percent)

    if dilution_rate is not None:
        if ranker:
            s = ranker.inverse_pct("dilution_rate", min(dilution_rate, 50))
        else:
            s = max(0, 100 - dilution_rate * 3)
        components["dilution"] = (s, 0.10, dilution_rate)

    if capex_efficiency is not None:
        s = min(100, max(0, capex_efficiency))
        components["capex_efficiency"] = (s, 0.05, capex_efficiency)

    total_weight = sum(w for _, w, _ in components.values())
    if total_weight > 0:
        score = sum(s * w for s, w, _ in components.values()) / total_weight
    else:
        score = 50  # no management data at all - neutral, matches forensic_penalty's insufficient-data convention

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
