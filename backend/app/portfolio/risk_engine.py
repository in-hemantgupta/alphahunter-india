def risk_score(data):

    score = 0

    if (data.get("volatility") or 0) > 40:

        score += 40

    if (data.get("max_drawdown") or 0) > 30:

        score += 30

    if (data.get("beta") or 0) > 1.5:

        score += 30

    return score
