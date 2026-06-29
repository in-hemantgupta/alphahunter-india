def delivery_score(data):
    avg_20 = data.get("delivery_20d_avg") or 0
    today = data.get("delivery_today") or 0
    if today > avg_20 * 1.3:
        return 100
    elif today > avg_20:
        return 70
    return 30
