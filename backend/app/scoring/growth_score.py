def growth_score(data):

    revenue_accel = data.get("revenue_acceleration") or 0
    pat_accel = data.get("pat_acceleration") or 0
    margin_exp = data.get("margin_expansion") or 0
    cf_improve = data.get("cashflow_improvement") or 0

    if revenue_accel >= 30:
        rev_score = 100
    elif revenue_accel >= 20:
        rev_score = 90
    elif revenue_accel >= 15:
        rev_score = 80
    elif revenue_accel >= 10:
        rev_score = 70
    elif revenue_accel >= 5:
        rev_score = 55
    elif revenue_accel >= 0:
        rev_score = 35
    elif revenue_accel >= -5:
        rev_score = 20
    else:
        rev_score = 10

    if pat_accel >= 40:
        pat_score = 100
    elif pat_accel >= 30:
        pat_score = 90
    elif pat_accel >= 20:
        pat_score = 80
    elif pat_accel >= 15:
        pat_score = 70
    elif pat_accel >= 10:
        pat_score = 55
    elif pat_accel >= 5:
        pat_score = 40
    elif pat_accel >= 0:
        pat_score = 25
    else:
        pat_score = 10

    if margin_exp >= 300:
        margin_score = 100
    elif margin_exp >= 200:
        margin_score = 90
    elif margin_exp >= 150:
        margin_score = 80
    elif margin_exp >= 100:
        margin_score = 70
    elif margin_exp >= 50:
        margin_score = 55
    elif margin_exp >= 0:
        margin_score = 35
    else:
        margin_score = 15

    operating_cashflow = data.get("operating_cashflow") or 0
    if cf_improve > 0 or (operating_cashflow > 0 and margin_exp > 0):
        cf_score = 80
    elif operating_cashflow > 0:
        cf_score = 60
    else:
        cf_score = 30

    score = (
        rev_score * 0.35 +
        pat_score * 0.35 +
        margin_score * 0.20 +
        cf_score * 0.10
    )

    return min(100, max(0, score))
