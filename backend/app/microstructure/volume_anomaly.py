def volume_score(data):
    avg = data["avg_30d_volume"]
    if avg == 0:
        return 20
    ratio = data["today_volume"] / avg
    if ratio > 3:
        return 100
    elif ratio > 2:
        return 70
    return 20
