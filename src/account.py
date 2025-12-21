import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient

class TradingAccount:
    def __init__(self, account_type: str):
        load_dotenv()
        self.account_type = account_type.upper()
        
        if self.account_type == "PAPER":
            api_key = os.getenv("PAPER_API_KEY")
            secret_key = os.getenv("PAPER_API_SECRET")
            self.paper = True
        elif self.account_type == "REAL":
            api_key = os.getenv("REAL_API_KEY")
            secret_key = os.getenv("REAL_API_SECRET")
            self.paper = False
        else:
            raise ValueError("account_type must be either 'PAPER' or 'REAL'")
            
        if not api_key or not secret_key:
            raise ValueError(f"Missing API credentials for {self.account_type} account.")
            
        self.client = TradingClient(api_key=api_key, secret_key=secret_key, paper=self.paper)
        self.account = self.client.get_account() 
        self.data_client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)

    # Account Information
    def get_account_type(self):
        return self.account_type
    
    def get_buying_power(self):
        return self.account.buying_power
    
    def get_daily_profit(self):
        # Check our current balance vs. our balance at the last market close
        balance_change = float(self.account.equity) - float(self.account.last_equity)
        return balance_change
    
    def is_paper(self):
        return self.paper