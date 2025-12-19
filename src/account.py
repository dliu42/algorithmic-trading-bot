import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

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
    
    ###################
    # Order Functions #
    ###################
    
    # Terms
    # type = buy or sell
    # symbol = stock symbol
    # side = buy or sell

    # qty = quantity
    # notional = # Total $ amount you want to trade
    # Choose between qty or notional

    # time_in_force = FOK (Fill or Kill) or DAY (Good 'til canceled)
    # limit_price = limit price
    
    def put_market_order(self, type: str, symbol: str, qty: float):
        try:
            if type == "BUY":
                side = OrderSide.BUY
            elif type == "SELL":
                side = OrderSide.SELL
            else:
                raise ValueError("type must be either 'BUY' or 'SELL'")

            market_order_data = MarketOrderData(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.FOK
            )

            order = self.client.submit_order(market_order_data)
            print(f"Order submitted: {order}")
            return order

        except Exception as e:
            print(f"Error submitting order: {e}")
            return None

    def put_limit_order(self, type: str, symbol: str, notional: float, limit_price: float):
        try:
            if type == "BUY":
                side = OrderSide.BUY
            elif type == "SELL":
                side = OrderSide.SELL
            else:
                raise ValueError("type must be either 'BUY' or 'SELL'")

            limit_order_data = LimitOrderRequest(
                symbol=symbol,
                limit_price=limit_price,
                notional=notional,
                side=side,
                time_in_force=TimeInForce.FOK
            )

            order = self.client.submit_order(limit_order_data)
            print(f"Order submitted: {order}")
            return order
        
        except Exception as e:
            print(f"Error submitting order: {e}")
            return None
    
    def get_closed_orders(self, limit: int = 100):
        try:
            get_orders_data = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                limit=limit,
                nested=True
                )
            orders = self.client.get_orders(filter=get_orders_data)
            return orders
        except Exception as e:
            print(f"Error getting orders: {e}")
            return None