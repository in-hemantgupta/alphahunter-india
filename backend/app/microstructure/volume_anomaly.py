def volume_score(data):
    avg = data.get("avg_30d_volume") or 0
    if avg == 0:
        return 20
    ratio = (data.get("today_volume") or 0) / avg
    if ratio > 3:
        return 100
    elif ratio > 2:
        return 70
    return 20
