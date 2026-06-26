def tightness_score(data):

    if \

        data["atr_14"] < 3 \

        and \

        data["volume_spike"]:

        return 100

    return 40
