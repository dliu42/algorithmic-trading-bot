from datetime import datetime
from collections import deque
import numpy as np

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

class PairState:
    def __init__(self, symbol_a: str, symbol_b: str, lookback_window: int):
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.spreads = deque(maxlen=lookback_window)
        self.in_position = False

class PairZScoreStrategy:
    def __init__(
        self,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        pairs: list, # List of tuples [("GOOGL", "GOOG"), ("KO", "PEP")]
        lookback_window: int = 20,
        z_entry: float = 2.0,
        z_exit: float = 0.5,
    ):
        self.trading_client = trading_client
        self.data_client = data_client
        self.lookback_window = lookback_window
        self.z_entry = z_entry
        self.z_exit = z_exit
        
        # multidimensional state
        self.pairs_state = []
        for (a, b) in pairs:
            self.pairs_state.append(PairState(a, b, lookback_window))

        # Flatten list of all symbols for batch data fetching
        self.all_symbols = []
        for pair in self.pairs_state:
            if pair.symbol_a not in self.all_symbols: self.all_symbols.append(pair.symbol_a)
            if pair.symbol_b not in self.all_symbols: self.all_symbols.append(pair.symbol_b)

    def _get_latest_prices(self):
        # Fetch all symbols in one batch request
        # Returns a dict: {symbol: price}
        req = StockLatestTradeRequest(symbol_or_symbols=self.all_symbols)
        latest = self.data_client.get_stock_latest_trade(req)
        
        prices = {}
        for sym in self.all_symbols:
            if sym in latest:
                prices[sym] = float(latest[sym].price)
            else:
                print(f"Warning: No quote for {sym}")
                prices[sym] = None
        return prices

    def _update_spread(self, pair_state, spread: float):
        pair_state.spreads.append(spread)

    def _compute_zscore(self, pair_state, spread: float):
        if len(pair_state.spreads) < self.lookback_window:
            return None, None, None
        
        arr = np.array(pair_state.spreads, dtype=float)
        mean = arr.mean()
        std = arr.std(ddof=1)
        
        if std == 0:
            return None, mean, std
            
        z = (spread - mean) / std
        return z, mean, std

    def _position_sizes(self, price_a: float, price_b: float):
        # simple sizing using account buying power
        # For multi-pair, we might want to split capital or just use small fixed size
        acct = self.trading_client.get_account()
        bp = float(acct.buying_power)
        
        # dividing by 10 per pair means each pair gets ~1% capital
        # This is safe for now.
        notional_each = bp / 10.0 
        
        qty_a = max(int(notional_each // price_a), 1)
        qty_b = max(int(notional_each // price_b), 1)
        return qty_a, qty_b

    def _submit_market_order(self, symbol: str, qty: int, side: OrderSide):
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY
        )
        self.trading_client.submit_order(req)
        print(f"Submitted {side} order for {qty} {symbol}")

    def _enter_long_spread(self, pair_state, qty_a: int, qty_b: int):
        # Buy A, Sell B
        print(f"[{pair_state.symbol_a}/{pair_state.symbol_b}] Enter LONG: Buy {qty_a} {pair_state.symbol_a}, Sell {qty_b} {pair_state.symbol_b}")
        self._submit_market_order(pair_state.symbol_a, qty_a, OrderSide.BUY)
        self._submit_market_order(pair_state.symbol_b, qty_b, OrderSide.SELL)
        pair_state.in_position = True

    def _enter_short_spread(self, pair_state, qty_a: int, qty_b: int):
        # Sell A, Buy B
        print(f"[{pair_state.symbol_a}/{pair_state.symbol_b}] Enter SHORT: Sell {qty_a} {pair_state.symbol_a}, Buy {qty_b} {pair_state.symbol_b}")
        self._submit_market_order(pair_state.symbol_a, qty_a, OrderSide.SELL)
        self._submit_market_order(pair_state.symbol_b, qty_b, OrderSide.BUY)
        pair_state.in_position = True

    def _close_positions(self, pair_state):
        # We need to target specific symbols for this pair logic to be correct in multi-pair
        # BUT TradingClient.close_all_positions() closes EVERYTHING (all pairs)
        # For now, we MUST change this to close only the specific positions.
        
        print(f"[{pair_state.symbol_a}/{pair_state.symbol_b}] Closing positions.")
        # Close A
        try:
            self.trading_client.close_position(pair_state.symbol_a)
        except Exception as e:
            print(f"Error closing {pair_state.symbol_a}: {e}")
            
        # Close B
        try:
            self.trading_client.close_position(pair_state.symbol_b)
        except Exception as e:
            print(f"Error closing {pair_state.symbol_b}: {e}")
            
        pair_state.in_position = False

    def step(self):
        prices = self._get_latest_prices()
        
        for pair in self.pairs_state:
            pa = prices[pair.symbol_a]
            pb = prices[pair.symbol_b]
            
            if pa is None or pb is None:
                continue
                
            spread = pa - pb
            self._update_spread(pair, spread)
            
            z, mean, std = self._compute_zscore(pair, spread)
            
            log_prefix = f"[{pair.symbol_a}/{pair.symbol_b}]"
            
            if z is None:
                print(f"{datetime.utcnow()} {log_prefix} not enough data, window={len(pair.spreads)}")
                continue

            print(f"{datetime.utcnow()} {log_prefix} spread={spread:.2f} z={z:.2f}")

            if not pair.in_position:
                qty_a, qty_b = self._position_sizes(pa, pb)
                if z > self.z_entry:
                    self._enter_short_spread(pair, qty_a, qty_b)
                elif z < -self.z_entry:
                    self._enter_long_spread(pair, qty_a, qty_b)
            else:
                if abs(z) < self.z_exit:
                    self._close_positions(pair)