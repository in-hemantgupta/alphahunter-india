import yfinance as yf


def fetch_price_history(

    symbol
):

    ticker = yf.Ticker(

        symbol + ".NS"
    )

    data = ticker.history(

        period="5y"
    )

    return data
