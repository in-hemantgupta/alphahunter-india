def detect_regime(index_data):

    trend = index_data["trend"]

    volatility = index_data["volatility"]

    if trend > 0 and volatility < 20:

        return "bull"

    elif trend < 0 and volatility > 30:

        return "bear"

    elif volatility > 25:

        return "rotation"

    return "sideways"
