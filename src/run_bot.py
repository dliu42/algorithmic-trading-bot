import argparse
from datetime import datetime, time, timedelta
import pytz
from time import sleep
from account import TradingAccount
from strategies.PairZScore import PairZScoreStrategy
from backtest.BTPairZScore import BTPairZScore
from logger import DualLogger

def print_status(account, now):
    bp = account.get_buying_power()
    profit = account.get_daily_profit()
    print(f"[{now.strftime('%H:%M:%S')}] STATUS UPDATE: Buying Power=${bp}, Daily Profit=${profit}")

def get_strategy(strategy_name, trading_client, data_client):
    strat = None
    if strategy_name == 'PairZScore':
        pairs_to_trade = [("GOOGL", "GOOG"), ("KO", "PEP")]
        strat = PairZScoreStrategy(
            trading_client=trading_client,
            data_client=data_client,
            pairs=pairs_to_trade,
            lookback_window=20,
            z_entry=2.0,
            z_exit=0.5,
        )
        print("Strategy: PairZScore with pairs:", pairs_to_trade)
    return strat

def backtest(strategy_name, data_client):
    if strategy_name == 'PairZScore':
        pairs_to_trade = [("GOOG", "GOOGL"), ("KO", "PEP"), ("FOX", "FOXA")]
        bt = BTPairZScore(
            data_client=data_client,
            pairs=pairs_to_trade,
            lookback_window=20,
            z_entry=2.0,
            z_exit=0.5,
        )

    # backtest from start_date to end_date, and print it all into one log file
    # print final P&L at the end
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    current_date = start_date
    
    print("\n" + "="*50)
    print(f"STARTING BACKTEST: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Initial Portfolio Value: ${bt.bt_cash:,.2f}")
    print("="*50 + "\n")

    initial_portfolio_value = bt.bt_cash

    while current_date <= end_date:
        # Skip weekends (0=Mon, 6=Sun)
        if current_date.weekday() < 5:
            date_str = current_date.strftime("%Y-%m-%d")
            print(f"\n>>> Running Backtest for {date_str}...")
            try:
                bt.backtest(date_yyyymmdd=date_str)
            except Exception as e:
                # log error to file, and keep going
                print(f"Error running backtest for {date_str}: {str(e)}")
        current_date += timedelta(days=1)
        
    final_portfolio_value = bt.bt_cash
    total_pnl = final_portfolio_value - initial_portfolio_value
    return_pct = (total_pnl / initial_portfolio_value) * 100.0
    
    print("\n" + "="*50)
    print(f"BACKTEST COMPLETE: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("="*50)
    print(f"Initial Value:  ${initial_portfolio_value:,.2f}")
    print(f"Final Value:    ${final_portfolio_value:,.2f}")
    print(f"Total P&L:      ${total_pnl:,.2f}")
    print(f"Return:         {return_pct:.2f}%")
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Run Trading Bot')

    parser.add_argument('--account', type=str, required=True, 
                        choices=['PAPER', 'REAL'],
                        help='Account type to use: PAPER or REAL')

    parser.add_argument('--strategy', type=str, required=True, 
                        choices=['PairZScore'],
                        help='Strategy to use: PairZScore')

    parser.add_argument('--backtest', type=str, required=True, 
                        choices=['true', 'false'],
                        help='Backtest mode: true or false')

    args = parser.parse_args()

    try:
        # setup logging
        print("Setting up Dual Logger....")
        DualLogger.setup_logging()
        print("Dual Logger setup successfully.")
        print("...............")

        print(f"Initializing {args.account} account...")
        trading_account = TradingAccount(account_type=args.account)
        print(f"Account initialized successfully.")

        print("...............")

        if trading_account.is_paper():
            print("Paper account. No trading will be executed.")
        else:
            print("Real account. Trading will be executed.")

        print("...............")  

        buying_power = trading_account.get_buying_power()
        print(f"Starting with Buying Power ({args.account}): ${buying_power}")

        print("...............")

        trading_client = trading_account.client
        data_client = trading_account.data_client

        print("Getting strategy...")
        strat = get_strategy(args.strategy, trading_client, data_client)

        print("Strategy initialized successfully.")
        
        print("...............")

        if args.backtest == 'true':
            print("Backtesting Set to True...")
            backtest(args.strategy, data_client)
            print("Backtesting completed.")
            return
        else:
            print("Backtesting Set to False...")

        print("This is for trading through the Alpaca's account")
        print("Starting Real Strategy loop...")
        
        last_status_time = None

        while True:
            # Check time (EST)
            # using pytz if available, else naive with warning or simple offset
            try:
                tz = pytz.timezone('US/Eastern')
                now = datetime.now(tz)
            except ImportError:
                # Fallback to system local if pytz missing (assuming user is in EST or doesn't care strictly)
                # Or better, just print needed dependency
                print("Warning: pytz not installed, using system local time")
                now = datetime.now()

            # Market Hours: 9:30 AM - 4:00 PM
            market_open = time(9, 30)
            market_close = time(16, 0)
            midnight = time(23, 59)
            current_time = now.time()
            
            if midnight >= current_time > market_close:
                print(f"[{now.strftime('%H:%M:%S')}] Market Closed. Stopping service.")
                break
            elif market_open <= current_time <= market_close:
                # Periodic Status Update (Every 30 mins)
                if last_status_time is None or (now - last_status_time).total_seconds() >= 1800:
                    print_status(trading_account, now)
                    last_status_time = now
                print(f"[{now.strftime('%H:%M:%S')}] Market Open. Running step...")
                strat.step()
                sleep(5) # Run every 5 seconds
            else:
                print(f"[{now.strftime('%H:%M:%S')}] Market not open yet. Waiting...")
                sleep(60)

            print("...............")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
