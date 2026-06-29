def technical_score(data):

    score = 0

    rs = data.get("relative_strength", 0)

    if rs > 80:

        score += 30

    elif rs > 50:

        score += 15

    if data.get("trend_strength", 0) > 0.6:

        score += 25

    if data.get("compression_pattern", False):

        score += 20

    if data.get("breakout_probability", 0) > 0.7:

        score += 15

    if data.get("volume_confirmation", False):

        score += 10

    return score
