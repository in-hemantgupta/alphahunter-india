def oi_score(data):

    if \

        data["oi_change"] > 10 \

        and \

        data["price_change"] > 2:

        return 100

    return 40
