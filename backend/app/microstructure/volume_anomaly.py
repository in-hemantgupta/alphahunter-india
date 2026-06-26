def volume_score(data):

    ratio = \

        data["today_volume"] / \

        data["avg_30d_volume"]

    if ratio > 3:

        return 100

    elif ratio > 2:

        return 70

    return 20
