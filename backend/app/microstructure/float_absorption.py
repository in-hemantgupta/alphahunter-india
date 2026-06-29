def float_score(data):
    if (data.get("delivery_percent") or 0) > 60 and abs(data.get("price_change") or 0) < 2:
        return 100
    return 30
