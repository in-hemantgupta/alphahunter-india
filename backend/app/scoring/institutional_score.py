def institutional_score(data):

    score = 0

    delivery_ratio = data.get("delivery_ratio", 1)

    if delivery_ratio > 2.0:

        score += 25

    elif delivery_ratio > 1.5:

        score += 15

    if data.get("volume_high", False) and data.get("price_flat", False):

        score += 20

    if data.get("vwap_defense", False):

        score += 15

    if data.get("price_compression", False):

        score += 10

    if data.get("seller_exhaustion", False):

        score += 15

    if data.get("bulk_deal_positive", False):

        score += 15

    return score
