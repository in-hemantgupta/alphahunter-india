def delivery_score(data):
    avg_20 = data["delivery_20d_avg"]
    today = data["delivery_today"]
    if today > avg_20 * 1.3:
        return 100
    elif today > avg_20:
        return 70
    return 30
