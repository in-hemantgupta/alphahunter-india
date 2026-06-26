def simulate_portfolio(stocks, start, end):

    returns = []

    for stock in stocks:

        buy = get_price(stock, start)

        sell = get_price(stock, end)

        r = (sell - buy) / buy

        returns.append(r)

    return returns
