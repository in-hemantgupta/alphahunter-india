from concurrent.futures import ThreadPoolExecutor
from app.ingestion.price_ingestor import fetch_price_history

def load_all_history(symbols):
    with ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(fetch_price_history, symbols)
