def risk_score(data):

    score = 0

    if data["volatility"] > 40:

        score += 40

    if data["max_drawdown"] > 30:

        score += 30

    if data["beta"] > 1.5:

        score += 30

    return score
