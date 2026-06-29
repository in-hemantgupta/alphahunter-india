def load_snapshot(date):

    prices = get_prices(before=date)

    financials = get_financials(before=date)

    return {

        "prices": prices,

        "financials": financials

    }
