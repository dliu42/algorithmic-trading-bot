from datetime import datetime
from time import sleep
from collections import deque
import numpy as np

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

class PairZScoreStrategy:
    def __init__(
        self,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        lookback_window: int = 20,
        z_entry: float = 2.0,
        z_exit: float = 0.5,
        symbol_a: str = "GOOGL",
        symbol_b: str = "GOOG",
    ):
        self.trading_client = trading_client
        self.data_client = data_client
        self.lookback_window = lookback_window
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b

        # rolling window of spreads
        self.spreads = deque(maxlen=lookback_window)

        # state
        self.in_position = False
        self.long_spread = None  # True: long A/short B, False: short A/long B

    def _get_latest_prices(self):
        # use latest trades via alpaca-py StockHistoricalDataClient [[Alpaca-py intro](https://alpaca.markets/sdks/python/getting_started.html)]
        req = StockLatestTradeRequest(symbol_or_symbols=[self.symbol_a, self.symbol_b])
        latest = self.data_client.get_stock_latest_trades(req)
        pa = float(latest[self.symbol_a].price)
        pb = float(latest[self.symbol_b].price)
        return pa, pb

    def _update_spread(self, spread: float):
        self.spreads.append(spread)

    def _compute_zscore(self, spread: float):
        if len(self.spreads) < self.lookback_window:
            return None, None, None
        arr = np.array(self.spreads, dtype=float)
        mean = arr.mean()
        std = arr.std(ddof=1)
        if std == 0:
            return None, mean, std
        z = (spread - mean) / std
        return z, mean, std

    def _position_sizes(self, price_a: float, price_b: float):
        # simple sizing using account buying power [[Pairs trading orders](https://alpaca.markets/learn/pairs-trading-with-crypto-and-equities#placing-orders-via-trade-api)]
        acct = self.trading_client.get_account()
        bp = float(acct.buying_power)
        notional_each = bp / 200.0
        qty_a = max(int(notional_each // price_a), 1)
        qty_b = max(int(notional_each // price_b), 1)
        return qty_a, qty_b

    def _submit_market_order(self, symbol: str, qty: int, side: OrderSide):
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        self.trading_client.submit_order(order)

    def _enter_long_spread(self, qty_a: int, qty_b: int):
        # Buy GOOGL, Sell GOOG
        self._submit_market_order(self.symbol_a, qty_a, OrderSide.BUY)
        self._submit_market_order(self.symbol_b, qty_b, OrderSide.SELL)
        self.in_position = True
        self.long_spread = True

    def _enter_short_spread(self, qty_a: int, qty_b: int):
        # Sell GOOGL, Buy GOOG
        self._submit_market_order(self.symbol_a, qty_a, OrderSide.SELL)
        self._submit_market_order(self.symbol_b, qty_b, OrderSide.BUY)
        self.in_position = True
        self.long_spread = False

    def _close_positions(self):
        # close both legs using TradingClient.close_all_positions for simplicity [[Pairs trading orders](https://alpaca.markets/learn/pairs-trading-with-crypto-and-equities#placing-orders-via-trade-api)]
        self.trading_client.close_all_positions(cancel_orders=True)
        self.in_position = False
        self.long_spread = None

    def step(self):
        pa, pb = self._get_latest_prices()
        spread = pa - pb  # GOOGL - GOOG
        self._update_spread(spread)

        z, mean, std = self._compute_zscore(spread)
        if z is None:
            print(f"{datetime.utcnow()} not enough data yet, window={len(self.spreads)}")
            return

        print(f"{datetime.utcnow()} spread={spread:.4f} mean={mean:.4f} std={std:.4f} z={z:.2f}")

        if not self.in_position:
            qty_a, qty_b = self._position_sizes(pa, pb)
            if z > self.z_entry:
                # Sell spread: Sell GOOGL, Buy GOOG
                self._enter_short_spread(qty_a, qty_b)
                print("Entered SHORT spread (Sell GOOGL, Buy GOOG)")
            elif z < -self.z_entry:
                # Buy spread: Buy GOOGL, Sell GOOG
                self._enter_long_spread(qty_a, qty_b)
                print("Entered LONG spread (Buy GOOGL, Sell GOOG)")
        else:
            if abs(z) < self.z_exit:
                self._close_positions()
                print("Closed spread (|z| < exit threshold)")