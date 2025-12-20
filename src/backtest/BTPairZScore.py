from datetime import datetime, timedelta, timezone
from collections import deque
import numpy as np

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

class BTPairState:
    def __init__(self, symbol_a: str, symbol_b: str, lookback_window: int):
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.spreads = deque(maxlen=lookback_window)
        self.in_position = False
        # Positions for this specific pair
        self.pos_a = 0
        self.pos_b = 0

class BTPairZScore:
    def __init__(
        self,
        data_client: StockHistoricalDataClient,
        pairs: list,
        lookback_window: int = 20,
        z_entry: float = 2.0,
        z_exit: float = 0.5,
        initial_cash: float = 200000.0
    ):
        self.data_client = data_client
        self.lookback_window = lookback_window
        self.z_entry = z_entry
        self.z_exit = z_exit
        
        # State
        self.pairs_state = [BTPairState(a, b, lookback_window) for (a, b) in pairs]
        
        # We share one cash pool across all pairs
        self.bt_cash = initial_cash
        self.bt_pnl_history = []
        
        self.all_symbols = []
        for p in self.pairs_state:
            if p.symbol_a not in self.all_symbols: self.all_symbols.append(p.symbol_a)
            if p.symbol_b not in self.all_symbols: self.all_symbols.append(p.symbol_b)

    def _update_spread(self, state: BTPairState, spread: float):
        state.spreads.append(spread)

    def _compute_zscore(self, state: BTPairState, spread: float):
        if len(state.spreads) < self.lookback_window:
            return None, None, None
        arr = np.array(state.spreads, dtype=float)
        mean = arr.mean()
        std = arr.std(ddof=1)
        if std == 0:
            return None, mean, std
        z = (spread - mean) / std
        return z, mean, std

    def _bt_position_sizes(self, state: BTPairState, price_a: float, price_b: float, current_equity: float):
        # Sizing: equity / 200 per pair deployment
        notional_each = current_equity / 10.0
        
        qty_a = max(int(notional_each // price_a), 1)
        qty_b = max(int(notional_each // price_b), 1)
        return qty_a, qty_b

    def _bt_enter_long_spread(self, state: BTPairState, pa: float, pb: float, current_equity: float):
        # Long Spread: Buy A, Sell B
        qty_a, qty_b = self._bt_position_sizes(state, pa, pb, current_equity)
        
        val_a = qty_a * pa
        val_b = qty_b * pb
        print(f"  [{state.symbol_a}/{state.symbol_b}] [BUY SPREAD] Buy {qty_a} {state.symbol_a} @ {pa:.2f} (${val_a:,.2f}) | Sell {qty_b} {state.symbol_b} @ {pb:.2f} (${val_b:,.2f})")

        self.bt_cash -= qty_a * pa
        state.pos_a += qty_a
        
        self.bt_cash += qty_b * pb
        state.pos_b -= qty_b
        
        state.in_position = True

    def _bt_enter_short_spread(self, state: BTPairState, pa: float, pb: float, current_equity: float):
        # Short Spread: Sell A, Buy B
        qty_a, qty_b = self._bt_position_sizes(state, pa, pb, current_equity)
        
        val_a = qty_a * pa
        val_b = qty_b * pb
        print(f"  [{state.symbol_a}/{state.symbol_b}] [SELL SPREAD] Sell {qty_a} {state.symbol_a} @ {pa:.2f} (${val_a:,.2f}) | Buy {qty_b} {state.symbol_b} @ {pb:.2f} (${val_b:,.2f})")

        self.bt_cash += qty_a * pa
        state.pos_a -= qty_a
        
        self.bt_cash -= qty_b * pb
        state.pos_b += qty_b

        state.in_position = True

    def _bt_close_positions(self, state: BTPairState, pa: float, pb: float):
        val_a = abs(state.pos_a * pa)
        val_b = abs(state.pos_b * pb)
        print(f"  [{state.symbol_a}/{state.symbol_b}] [CLOSE] Closing {state.pos_a} {state.symbol_a} @ {pa:.2f} (${val_a:,.2f}) and {state.pos_b} {state.symbol_b} @ {pb:.2f} (${val_b:,.2f})")
        
        self.bt_cash += state.pos_a * pa
        self.bt_cash += state.pos_b * pb
        state.pos_a = 0
        state.pos_b = 0
        state.in_position = False

    def _get_total_equity(self, current_prices: dict):
        # Equity = Cash + Sum(Position Value of all pairs)
        equity = self.bt_cash
        for state in self.pairs_state:
            pa = current_prices.get(state.symbol_a)
            pb = current_prices.get(state.symbol_b)
            if pa and pb:
                equity += (state.pos_a * pa) + (state.pos_b * pb)
        return equity

    def step_backtest(self, current_prices: dict, ts: datetime = None):
        # Process each pair
        current_equity = self._get_total_equity(current_prices)
        
        for state in self.pairs_state:
            pa = current_prices.get(state.symbol_a)
            pb = current_prices.get(state.symbol_b)
            
            if pa is None or pb is None:
                continue

            spread = pa - pb
            self._update_spread(state, spread)
            z, mean, std = self._compute_zscore(state, spread)
            
            if z is None: continue

            if not state.in_position:
                if z > self.z_entry:
                    self._bt_enter_short_spread(state, pa, pb, current_equity)
                elif z < -self.z_entry:
                    self._bt_enter_long_spread(state, pa, pb, current_equity)
            else:
                if abs(z) < self.z_exit:
                    self._bt_close_positions(state, pa, pb)

        # Record portfolio-wide equity
        # (Recalculate after trades)
        new_equity = self._get_total_equity(current_prices)
        self.bt_pnl_history.append((ts, new_equity))

    def backtest(self, date_yyyymmdd: str, step_seconds: int = 60):
        print("Starting backtest...")
        print(f"Backtesting pairs on {date_yyyymmdd}: {[ (p.symbol_a, p.symbol_b) for p in self.pairs_state ]}")
        
        # Window setup
        date_obj = datetime.strptime(date_yyyymmdd, "%Y-%m-%d").date()
        start_utc = datetime(date_obj.year, date_obj.month, date_obj.day, 14, 30, tzinfo=timezone.utc)
        end_utc   = datetime(date_obj.year, date_obj.month, date_obj.day, 21, 0, tzinfo=timezone.utc)
        
        # Fetch Data
        print("Fetching historical data...")
        req = StockBarsRequest(
            symbol_or_symbols=self.all_symbols,
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
            start=start_utc,
            end=end_utc,
        )
        bars = self.data_client.get_stock_bars(req).df
        
        if bars.empty:
            print("No data found.")
            return

        closes = bars["close"].unstack(level="symbol")
        # Ensure we have data for needed symbols
        valid_symbols = [s for s in self.all_symbols if s in closes.columns]
        closes = closes[valid_symbols].dropna()
        
        print(f"Loaded {len(closes)} minutes of overlapping data.")
        
        initial_equity = self.bt_cash
        
        # Iterate
        for bar_ts, row in closes.iterrows():
            # Build current_prices dict
            current_prices = { sym: float(row[sym]) for sym in valid_symbols }
            
            ts = bar_ts.to_pydatetime()
            self.step_backtest(current_prices, ts=ts)
            
        # Force close all
        last_row = closes.iloc[-1]
        last_prices = { sym: float(last_row[sym]) for sym in valid_symbols }
        
        for state in self.pairs_state:
            if state.in_position:
                pa = last_prices.get(state.symbol_a)
                pb = last_prices.get(state.symbol_b)
                if pa and pb:
                    self._bt_close_positions(state, pa, pb)

        final_equity = self._get_total_equity(last_prices)
        total_pnl = final_equity - initial_equity
        ret_pct = (total_pnl / initial_equity) * 100.0

        print("....................")
        print(f"Initial Equity: ${initial_equity:,.2f}")
        print(f"Final Equity:   ${final_equity:,.2f}")
        print(f"Total P&L:      ${total_pnl:,.2f} ({ret_pct:.2f}%)")
        print("....................")

        return {
            "initial_equity": initial_equity,
            "final_equity": final_equity,
            "total_pnl": total_pnl,
            "return_pct": ret_pct,
        }
