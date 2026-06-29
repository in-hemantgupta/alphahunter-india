def fundamental_score(data):

    score = 0

    if data.get("roce", 0) > 15:

        score += 30

    if data.get("debt_equity", 1) < 0.7:

        score += 20

    if data.get("operating_cashflow", 0) > 0:

        score += 20

    if data.get("fcf_trend", 0) > 0:

        score += 15

    if data.get("margin_stability", 0) > 0:

        score += 15

    return score
