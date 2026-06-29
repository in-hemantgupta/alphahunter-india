import pandas as pd


def build_stock_universe():
    """Fetch NSE equity list from official source."""
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df = pd.read_csv(url)
        return df
    except Exception as e:
        print(f"Error fetching universe: {e}")
        return None
