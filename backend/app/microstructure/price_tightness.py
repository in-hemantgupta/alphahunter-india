def tightness_score(data):
    if (data.get("atr_14") or 0) < 3 and data.get("volume_spike", False):
        return 100
    return 40
