#!/usr/bin/env python3
"""
Debug ETL Script - NO DATABASE CONNECTION
Only fetches and displays data to verify what's being processed

Usage:
    python etl/debug_etl.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
etl_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(etl_dir)
sys.path.insert(0, parent_dir)

# Import directly using importlib to avoid __init__.py which imports db_manager
import importlib.util

# Load utils.py directly (doesn't require db_manager)
utils_path = os.path.join(etl_dir, 'utils', 'utils.py')
spec = importlib.util.spec_from_file_location("etl_utils", utils_path)
etl_utils = importlib.util.module_from_spec(spec)
sys.modules['etl_utils'] = etl_utils
spec.loader.exec_module(etl_utils)
try_fetch = etl_utils.try_fetch
BROWSER_HEADERS = etl_utils.BROWSER_HEADERS
parse_ambito_response = etl_utils.parse_ambito_response
parse_number = etl_utils.parse_number

# Load fetch_usd_data.py (it imports from utils, so we need to patch sys.modules)
sys.modules['etl.utils.utils'] = etl_utils
fetch_usd_path = os.path.join(etl_dir, 'utils', 'fetch_usd_data.py')
spec = importlib.util.spec_from_file_location("etl.utils.fetch_usd_data", fetch_usd_path)
fetch_usd = importlib.util.module_from_spec(spec)
sys.modules['etl.utils.fetch_usd_data'] = fetch_usd
spec.loader.exec_module(fetch_usd)
fetch_ambito_dolar = fetch_usd.fetch_ambito_dolar

# Load fetch_uva.py
fetch_uva_path = os.path.join(etl_dir, 'utils', 'fetch_uva.py')
spec = importlib.util.spec_from_file_location("etl.utils.fetch_uva", fetch_uva_path)
fetch_uva = importlib.util.module_from_spec(spec)
sys.modules['etl.utils.fetch_uva'] = fetch_uva
spec.loader.exec_module(fetch_uva)
fetch_uva_data = fetch_uva.fetch_uva_data
import pandas as pd
import json
# from utils.db_manager import DoltDBManager  # COMMENTED OUT FOR DEBUG


def debug_recent_data(days_back=30):
    """
    Debug function - fetches data WITHOUT inserting to database
    Shows detailed information about what data is being fetched
    
    Args:
        days_back: Number of days to check (default: 30)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    print("\n" + "🔍" * 35)
    print("   DEBUG ETL - NO DATABASE CONNECTION")
    print("🔍" * 35)
    print(f"\n📅 Checking period: {start_str} to {end_str}")
    print(f"⏰ Debug run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # ===================================================================
    # DATABASE CONNECTION COMMENTED OUT FOR DEBUG
    # ===================================================================
    # db = DoltDBManager()
    # db.connect()
    # ===================================================================
    
    try:
        # 1. Debug UVA data
        print("\n" + "="*70)
        print("🔵 UVA DATA DEBUG")
        print("="*70)
        uva_data = fetch_uva_data()
        
        if uva_data:
            # Filter to recent dates
            recent_uva = [d for d in uva_data if d['date'] >= start_str]
            print(f"\n📊 UVA Summary:")
            print(f"   Total UVA records fetched: {len(uva_data)}")
            print(f"   Records in period ({start_str} to {end_str}): {len(recent_uva)}")
            
            if recent_uva:
                print(f"\n📋 Sample UVA data (first 10 records):")
                print("-"*70)
                print(f"{'Date':<12} | {'Kind':<10} | {'Rate':>15}")
                print("-"*70)
                for item in recent_uva[:10]:
                    print(f"{item['date']:<12} | {item['kind']:<10} | {item['rate']:>15.6f}")
                if len(recent_uva) > 10:
                    print(f"... ({len(recent_uva) - 10} more records)")
                print("-"*70)
                
                # Show date range
                dates = [item['date'] for item in recent_uva]
                print(f"\n📅 UVA Date range in period: {min(dates)} to {max(dates)}")
        else:
            print("⚠️  No UVA data fetched")
        
        # 2. Debug USD data (focus on informal/blue dollar)
        print("\n" + "="*70)
        print("🔵 USD DATA DEBUG - INFORMAL (BLUE DOLLAR)")
        print("="*70)
        
        usd_types = [
            ('informal', 'USDB_ARS', 'Blue Dollar'),    # Focus on this one
        ]
        
        # Also check other types for comparison
        # usd_types = [
        #     ('formal', 'USD_ARS', 'Official Dollar'),
        #     ('mep', 'USDM_ARS', 'MEP Dollar'),
        #     ('informal', 'USDB_ARS', 'Blue Dollar'),
        #     ('cripto', 'USDC_ARS', 'Crypto Dollar')
        # ]
        
        for kind, pair, label in usd_types:
            print(f"\n{'='*70}")
            print(f"🔍 Fetching {label} ({pair})")
            print(f"{'='*70}")
            print(f"   Request parameters:")
            print(f"   - kind: {kind}")
            print(f"   - start_date: {start_str}")
            print(f"   - end_date: {end_str}")
            print(f"   - Expected URL: https://mercados.ambito.com/dolar/{kind}/historico-general/{start_str}/{end_str}")
            
            # Fetch data (will be called by fetch_ambito_dolar, but we'll inspect it here too)
            # For now, just call the normal function - we'll add raw inspection if needed
            usd_data = fetch_ambito_dolar(kind, start_str, end_str)
            
            if usd_data:
                print(f"\n📊 {label} Summary:")
                print(f"   Total records fetched: {len(usd_data)}")
                print(f"   Expected: ~{len(usd_data) // 2} dates × 2 (bid/ask) = {len(usd_data)} records")
                
                # Group by date to see duplicates
                from collections import defaultdict
                dates_dict = defaultdict(list)
                for item in usd_data:
                    dates_dict[item['date']].append(item)
                
                print(f"\n📅 Unique dates: {len(dates_dict)}")
                
                # Show records with issues (duplicates, missing bid/ask, etc.)
                print(f"\n🔍 Checking data quality...")
                issues = []
                for date, items in dates_dict.items():
                    kinds = [item['kind'] for item in items]
                    if 'bid' not in kinds:
                        issues.append(f"   ❌ {date}: Missing 'bid' (only has: {kinds})")
                    if 'ask' not in kinds:
                        issues.append(f"   ❌ {date}: Missing 'ask' (only has: {kinds})")
                    if len(items) > 2:
                        issues.append(f"   ⚠️  {date}: {len(items)} records (expected 2: bid+ask)")
                    if len(items) < 2:
                        issues.append(f"   ⚠️  {date}: {len(items)} records (expected 2: bid+ask)")
                
                if issues:
                    print(f"   Found {len(issues)} potential issues:")
                    for issue in issues[:20]:  # Show first 20
                        print(issue)
                    if len(issues) > 20:
                        print(f"   ... ({len(issues) - 20} more issues)")
                else:
                    print("   ✅ All dates have exactly bid + ask records")
                
                # Show sample data
                print(f"\n📋 Sample {label} data (first 20 records):")
                print("-"*70)
                print(f"{'Date':<12} | {'Kind':<10} | {'Rate':>15}")
                print("-"*70)
                for item in usd_data[:20]:
                    print(f"{item['date']:<12} | {item['kind']:<10} | {item['rate']:>15.2f}")
                if len(usd_data) > 20:
                    print(f"... ({len(usd_data) - 20} more records)")
                print("-"*70)
                
                # Show date range
                dates = [item['date'] for item in usd_data]
                if dates:
                    print(f"\n📅 {label} Date range: {min(dates)} to {max(dates)}")
                    
                    # Check for dates outside requested range
                    dates_before = [d for d in dates if d < start_str]
                    dates_after = [d for d in dates if d > end_str]
                    if dates_before:
                        print(f"   ⚠️  Found {len(dates_before)} dates BEFORE requested start: {min(dates_before)} to {max(dates_before)}")
                    if dates_after:
                        print(f"   ⚠️  Found {len(dates_after)} dates AFTER requested end: {min(dates_after)} to {max(dates_after)}")
                
                # Show rate statistics
                rates = [item['rate'] for item in usd_data]
                if rates:
                    print(f"\n💰 Rate statistics:")
                    print(f"   Min: ${min(rates):.2f}")
                    print(f"   Max: ${max(rates):.2f}")
                    print(f"   Avg: ${sum(rates)/len(rates):.2f}")
                    
                    # Check for suspicious values (negative, zero, extremely high)
                    suspicious = [r for r in rates if r <= 0 or r > 10000]
                    if suspicious:
                        print(f"   ⚠️  Found {len(suspicious)} suspicious rates: {suspicious[:10]}")
            else:
                print(f"   ⚠️  No {label} data fetched")
        
        print("\n" + "="*70)
        print("✅ DEBUG COMPLETED")
        print("="*70)
        print("\n💡 Next steps:")
        print("   1. Review the data above to identify issues")
        print("   2. Check if dates are correct (not in future)")
        print("   3. Verify rates are reasonable")
        print("   4. Check for duplicates or missing bid/ask pairs")
        print("="*70 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    # finally:
    #     # DATABASE DISCONNECT COMMENTED OUT
    #     # db.disconnect()
    #     pass


if __name__ == "__main__":
    # Get days to check from env var or use default (30)
    days = int(os.getenv('DEBUG_DAYS', '30'))
    
    exit_code = debug_recent_data(days_back=days)
    sys.exit(exit_code)

