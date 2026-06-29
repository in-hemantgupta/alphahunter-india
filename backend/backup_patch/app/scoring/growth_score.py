def growth_score(data):

    score = 0

    revenue_accel = data.get("revenue_acceleration", 0)

    pat_accel = data.get("pat_acceleration", 0)

    margin_exp = data.get("margin_expansion", 0)

    cf_improve = data.get("cashflow_improvement", 0)

    score += min(revenue_accel * 0.35, 35)

    score += min(pat_accel * 0.35, 35)

    score += min(margin_exp * 0.20, 20)

    score += min(cf_improve * 0.10, 10)

    return score
