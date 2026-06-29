def attribute_factors(backtest_results):

    factors = {}

    for factor in backtest_results["factors"]:

        contribution = calculate_contribution(factor)

        factors[factor] = contribution

    return factors
