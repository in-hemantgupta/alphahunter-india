import yfinance as yf


def fetch_price_history(symbol):
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        data = ticker.history(period="2y")

        if data is None or data.empty:
            return None

        return data

    except Exception as e:
        print(f"Price fetch error {symbol}: {e}")
        return None
