def vwap_score(data):

    distance = abs(

        data["close"]

        -

        data["vwap"]
    )

    percent = \

        distance /

        data["close"]

    if percent < 0.005:

        return 100

    return 40
