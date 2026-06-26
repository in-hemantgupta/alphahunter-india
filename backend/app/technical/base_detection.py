import numpy as np


def base_formation_score(price_series):
    score = 0
    if not price_series or len(price_series) == 0:
        return 0
    volatility = np.std(price_series)
    avg_price = np.mean(price_series)
    if avg_price == 0:
        return 0
    ratio = volatility / avg_price
    if ratio < 0.03:
        score = 5
    elif ratio < 0.06:
        score = 3
    return score
