import argparse
from account import TradingAccount

def main():
    parser = argparse.ArgumentParser(description='Run Trading Bot')
    parser.add_argument('--account', type=str, required=True, 
                        choices=['PAPER', 'REAL'],
                        help='Account type to use: PAPER or REAL')
    
    args = parser.parse_args()
    
    try:
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
        print(f"Buying Power ({args.account}): ${buying_power}")

        daily_profit = trading_account.get_daily_profit()
        print(f"Daily Profit ({args.account}): ${daily_profit}")  

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
