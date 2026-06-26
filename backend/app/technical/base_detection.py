import numpy as np


def base_formation_score(

    price_series

):

    score = 0

    volatility = np.std(
        price_series
    )

    avg_price = np.mean(
        price_series
    )

    ratio = (

        volatility

        /

        avg_price
    )

    if ratio < 0.03:

        score = 5

    elif ratio < 0.06:

        score = 3

    return score
