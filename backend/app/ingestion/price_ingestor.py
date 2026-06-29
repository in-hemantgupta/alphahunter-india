
import yfinance as yf

def fetch_price_history(symbol):
    ticker = yf.Ticker(f"{symbol}.NS")
    data = ticker.history(period="2y")
    return data
