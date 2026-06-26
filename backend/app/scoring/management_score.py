def management_score(data):

    score = 0

    promoter_change = data.get("promoter_change", 0)

    if promoter_change > 2:

        score += 20

    elif promoter_change > 0:

        score += 15

    elif promoter_change > -2:

        score += 8

    if data.get("pledge_percent", 0) < 5:

        score += 15

    if data.get("roce_trend", 0) > 0:

        score += 20

    if data.get("capex_efficiency", 0) > 0:

        score += 20

    if data.get("governance_clean", True):

        score += 25

    return score
