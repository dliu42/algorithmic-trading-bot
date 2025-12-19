from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
import os
import dotenv

#Load environment variables from .env file
dotenv.load_dotenv()

api_key = os.getenv("PAPER_API_KEY")
secret_key = os.getenv("PAPER_API_SECRET")

trading_client = TradingClient(api_key, secret_key)

# Get our account information.
account = trading_client.get_account()

# Check if our account is restricted from trading.
if account.trading_blocked:
    print('Account is currently restricted from trading.')

# Check how much money we can use to open new positions.
print('${} is available as buying power.'.format(account.buying_power))