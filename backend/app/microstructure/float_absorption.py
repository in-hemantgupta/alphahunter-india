def float_score(data):

    if \

        data["delivery_percent"] > 60 \

        and \

        data["price_change"] < 2:

        return 100

    return 30
