#!/usr/bin/env python3
"""
ETL to populate fx_rate with UVA and USD data

Schema:
- UVA: Returns 'index' rates (reference value)
- USD: Returns 'bid' and 'ask' rates (buy, sell)
  Note: mid point should be calculated at query time, not stored

Equivalent to the JavaScript ETL bitfinex_candles.js
Follows the same logic: fetch → pull → insert → add → commit → push

To run:
    export DOLT_DB='mysql://<user>:@localhost:PORT/macroeconomia'
    python etl/populate_usd_uva.py
"""

import os
from datetime import datetime, date, timedelta
from utils.fetch_uva import fetch_uva_data
from utils.fetch_usd_data import fetch_ambito_dolar
from utils.db_manager import DoltDBManager


def to_iso_date_string(dt):
    """Converts datetime to string YYYY-MM-DD"""
    if isinstance(dt, str):
        return dt
    return dt.strftime('%Y-%m-%d')


def run_pair(symbol: str, data_rows: list, db: DoltDBManager, pair: str, local_mode: bool = False):
    """
    Processes and inserts data for a specific currency pair
    
    Args:
        symbol: Symbol name for display (e.g., 'UVA', 'USD_OFICIAL')
        data_rows: List of data to insert (each row must have 'date', 'kind', 'rate')
        db: Database manager
        pair: Currency pair (e.g., 'USD_ARS', 'UVA_ARS')
        local_mode: If True, skip dolt pull/add/commit/push operations
    """
    try:
        print(f"\n{'='*70}")
        print(f"📊 Processing: {symbol} ({pair})")
        print(f"{'='*70}")
        
        # 1. Pull (use CLI: dolt pull) - Skip in local mode
        if not local_mode:
            pull_res = db.dolt_pull()
            print(f"✅ dolt_pull: {pull_res}")
        else:
            print("ℹ️  Local mode: Skipping dolt_pull")

        # 2. Filter today's data to avoid duplicates
        today = to_iso_date_string(datetime.now())
        filtered_data = [dp for dp in data_rows if dp.get('date') != today]
        
        print(f"📝 Records to insert: {len(filtered_data)} (excluding today)")
        
        # 3. Insert data points with INSERT IGNORE
        insert_results = []
        for i, dp in enumerate(filtered_data):
            try:
                result = db.insert_fx_rate(
                    date=dp['date'],
                    kind=dp['kind'],
                    pair=pair,
                    rate=dp['rate']
                )
                insert_results.append(result)
                    
            except Exception as e:
                print(f"⚠️  Error inserting {dp}: {e}")
                continue
        
        # 4. Dolt operations (use CLI for add/commit/push) - Skip in local mode
        if not local_mode:
            add_res = db.dolt_add('fx_rate')
            commit_msg = f"fx_rate update {symbol} {to_iso_date_string(datetime.now())}"
            commit_res = db.dolt_commit(commit_msg)
            push_res = db.dolt_push()
            
            print(f"\n✅ Completed {symbol}:")
            print(f"   - Records successfully inserted: {len(insert_results)}")
            print(f"   - dolt_add: {add_res}")
            print(f"   - dolt_commit: {commit_res}")
            print(f"   - dolt_push: {push_res}")
        else:
            print(f"\n✅ Completed {symbol} (local mode):")
            print(f"   - Records successfully inserted: {len(insert_results)}")
            print(f"   - Dolt operations skipped (local mode)")
        print(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ run_pair() failed for {symbol}: {e}")
        return False


def run(start_date: date, end_date: date | None = None, local_mode: bool = False):
    """
    Main ETL function
    
    Args:
        start_date: Start date for data fetch
        end_date: End date for data fetch (default: now)
        local_mode: If True, skip dolt pull/add/commit/push operations
    """
    if end_date is None:
        end_date = datetime.now()
    try:
        # 1. Connect to database
        db = DoltDBManager()
        db.connect()
        
        # 2. Calculate date range
        
        start_str = to_iso_date_string(start_date)
        end_str = to_iso_date_string(end_date)
        
        print("\n" + "🇦🇷" * 35)
        print("   ETL: POPULATE USD & UVA DATA")
        print("🇦🇷" * 35)
        print(f"\n📅 Period: {start_str} to {end_str}\n")
        
        # 3. Fetch and load UVA data
        print("\n🔵 Fetching UVA data...")
        uva_data = fetch_uva_data()
        
        if uva_data:
            run_pair('UVA', uva_data, db, pair='UVA_ARS', local_mode=local_mode)
        
        # 4. Fetch and load USD data
        # Each fetch returns bid/ask rates (mid can be calculated at query time)
        usd_types = [
            ('formal', 'USD_OFICIAL', 'USD_ARS'),    # Official Dollar
            ('mep', 'USD_MEP', 'USDM_ARS'),          # MEP Dollar
            ('informal', 'USD_BLUE', 'USDB_ARS'),    # Blue Dollar
            ('cripto', 'USD_CRIPTO', 'USDC_ARS')     # Crypto Dollar
        ]
        
        for kind, symbol, pair in usd_types:
            print(f"\n🔵 Fetching {symbol} data (pair: {pair})...")
            usd_data = fetch_ambito_dolar(kind, start_str, end_str)
            
            if usd_data:
                run_pair(symbol, usd_data, db, pair=pair, local_mode=local_mode)
        
        print("\n" + "="*70)
        print("✅ ETL COMPLETED SUCCESSFULLY")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ run() failed: {e}")
        raise
    
    finally:
        # Close connection
        db.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='ETL to populate fx_rate with UVA and USD data')
    parser.add_argument('--local', action='store_true', 
                        help='Local mode: skip dolt pull/add/commit/push operations')
    parser.add_argument('--start-date', type=str, default=None,
                        help='Start date (YYYY-MM-DD), default: 2025-10-01')
    parser.add_argument('--end-date', type=str, default=None,
                        help='End date (YYYY-MM-DD), default: today')
    
    args = parser.parse_args()
    
    # Parse dates
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = datetime(2025, 10, 1)
        # start_date = datetime(2024, 9, 1)  # From convertibilidad exit
    
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # Configure environment variables if not set
    if not os.getenv('DOLT_DB'):
        # Default configuration for local server
        os.environ['DOLT_DB'] = 'mysql://user:@localhost:3306/macroeconomia'
        print(f"ℹ️  Using default DOLT_DB: {os.environ['DOLT_DB']}\n")
    
    if args.local:
        print("ℹ️  Running in LOCAL MODE (skipping dolt operations)\n")
    
    run(start_date, end_date, local_mode=args.local)
