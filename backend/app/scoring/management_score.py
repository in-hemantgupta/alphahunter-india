def management_score(data, ranker=None, _debug=False):
    promoter_change = data.get("promoter_change") or 0
    pledge_percent = data.get("pledge_percent") or 0
    roce_trend = data.get("roce_trend") or 0
    capex_efficiency = data.get("capex_efficiency") or 0
    operating_cashflow = data.get("operating_cashflow") or 0
    dilution_rate = data.get("dilution_rate") or 0
    governance_clean = data.get("governance_clean", True)
    sector = data.get("sector")

    if ranker:
        promoter_score = ranker.pct("promoter_change", promoter_change)
        pledge_score = ranker.inverse_pct("pledge_percent", min(pledge_percent, 100))
        dilution_score = ranker.inverse_pct("dilution_rate", min(dilution_rate, 50))
        cashflow_score = ranker.pct("operating_cashflow", operating_cashflow, sector=sector)
    else:
        promoter_score = min(100, max(0, 50 + promoter_change * 5))
        pledge_score = max(0, 100 - pledge_percent * 2)
        dilution_score = max(0, 100 - dilution_rate * 3)
        cashflow_score = 70 if operating_cashflow > 0 else 30

    governance_score = 85 if governance_clean else 30
    capex_score = min(100, max(0, capex_efficiency))

    score = (
        promoter_score * 0.25 +
        governance_score * 0.20 +
        cashflow_score * 0.20 +
        pledge_score * 0.20 +
        dilution_score * 0.10 +
        capex_score * 0.05
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "promoter_behavior": {"raw": promoter_change, "score": promoter_score, "weight": 0.25},
                "governance": {"raw": governance_clean, "score": governance_score, "weight": 0.20},
                "cashflow_quality": {"raw": operating_cashflow, "score": cashflow_score, "weight": 0.20},
                "pledge_risk": {"raw": pledge_percent, "score": pledge_score, "weight": 0.20},
                "dilution": {"raw": dilution_rate, "score": dilution_score, "weight": 0.10},
                "capex_efficiency": {"raw": capex_efficiency, "score": capex_score, "weight": 0.05},
            }
        }

    return final
