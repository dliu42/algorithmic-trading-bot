import os
from dotenv import load_dotenv, find_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

# Load env from parent dir
load_dotenv(find_dotenv(usecwd=True))

api_key = os.getenv("PAPER_API_KEY")
secret_key = os.getenv("PAPER_API_SECRET")

if not api_key:
    # Try looking in the current folder's .env if not found above
    load_dotenv()
    api_key = os.getenv("PAPER_API_KEY")
    secret_key = os.getenv("PAPER_API_SECRET")

print(f"Testing data fetch with Key: {str(api_key)[:5]}...")

try:
    client = StockHistoricalDataClient(api_key, secret_key)
    req = StockLatestTradeRequest(symbol_or_symbols=["GOOG", "GOOGL"])
    
    # NOTE: singular method name
    res = client.get_stock_latest_trade(req)

    print("Success! Fetched latest trades:")
    for sym, trade in res.items():
        print(f"{sym}: ${trade.price} at {trade.timestamp}")

except Exception as e:
    print(f"Error: {e}")