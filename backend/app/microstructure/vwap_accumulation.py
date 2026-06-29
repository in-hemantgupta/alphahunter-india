def vwap_score(data):
    close = data.get("close") or 0
    if close == 0:
        return 40
    distance = abs(close - (data.get("vwap") or close))
    percent = distance / close
    if percent < 0.005:
        return 100
    return 40
