def vwap_score(data):
    close = data["close"]
    if close == 0:
        return 40
    distance = abs(close - data["vwap"])
    percent = distance / close
    if percent < 0.005:
        return 100
    return 40
