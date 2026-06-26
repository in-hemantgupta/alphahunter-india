import numpy as np


def volatility_score(recent_returns):
    score = 0
    std = np.std(recent_returns)
    if std < 0.015:
        score = 5
    elif std < 0.025:
        score = 3
    return score
