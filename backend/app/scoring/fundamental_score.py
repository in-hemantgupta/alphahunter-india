def fundamental_score(data):

    roce = data.get("roce") or 0
    debt_equity = data.get("debt_equity") or 1
    operating_cashflow = data.get("operating_cashflow") or 0
    fcf_trend = data.get("fcf_trend") or 0
    margin_stability = data.get("margin_stability") or 0

    if roce >= 25:
        roce_score = 100
    elif roce >= 20:
        roce_score = 85
    elif roce >= 15:
        roce_score = 70
    elif roce >= 10:
        roce_score = 50
    elif roce >= 5:
        roce_score = 30
    else:
        roce_score = 10

    if debt_equity <= 0:
        debt_score = 100
    elif debt_equity < 0.3:
        debt_score = 90
    elif debt_equity < 0.5:
        debt_score = 80
    elif debt_equity < 0.7:
        debt_score = 70
    elif debt_equity < 1.0:
        debt_score = 50
    elif debt_equity < 1.5:
        debt_score = 30
    else:
        debt_score = 10

    if operating_cashflow > 0:
        fcf_score = 70
        if fcf_trend > 0:
            fcf_score = 100
        elif fcf_trend == 0:
            fcf_score = 70
    else:
        fcf_score = 20

    stability = min(100, max(0, margin_stability))

    asset_turnover_score = 60
    revenue = data.get("revenue") or 0
    if revenue > 0:
        asset_turnover_score = 70

    score = (
        roce_score * 0.30 +
        debt_score * 0.20 +
        fcf_score * 0.20 +
        stability * 0.15 +
        asset_turnover_score * 0.15
    )

    return min(100, max(0, score))
