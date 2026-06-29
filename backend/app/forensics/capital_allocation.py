def capital_allocation_score(data):
    """
    Capital Allocation Quality Engine
    As per RESEARCH_BIBLE.md Section 19.
    """
    roce_trend = (data.get("roce_trend") or 0)
    fcf_trend = (data.get("fcf_trend") or 0)
    capex_efficiency = (data.get("capex_efficiency") or 0)
    debt_management = (data.get("debt_management") or 0)

    score = (
        min(roce_trend * 0.40, 40) +
        min(fcf_trend * 0.20, 20) +
        min(capex_efficiency * 0.20, 20) +
        min(debt_management * 0.20, 20)
    )

    return min(100, score)
