#!/usr/bin/env python3
"""
Debug ETL Script WITH Database Connection
Fetches data, shows what would be inserted, and optionally inserts it

Usage:
    # Debug mode (dry-run, no inserts):
    python etl/debug_etl_with_db.py --dry-run
    
    # Debug mode with actual inserts (verbose logging):
    python etl/debug_etl_with_db.py
    
    # Specify days to check:
    DEBUG_DAYS=60 python etl/debug_etl_with_db.py --dry-run
"""

import os
import sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))

from utils.fetch_usd_data import fetch_ambito_dolar
from utils.fetch_uva import fetch_uva_data
from utils.db_manager import DoltDBManager


def debug_etl_with_db(days_back=30, dry_run=False):
    """
    Debug ETL function WITH database connection
    Shows detailed information and optionally inserts data
    
    Args:
        days_back: Number of days to check (default: 30)
        dry_run: If True, only shows what would be inserted (default: False)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    mode_str = "🔍 DRY-RUN MODE (no inserts)" if dry_run else "💾 INSERT MODE (will insert to DB)"
    
    print("\n" + "="*70)
    print("   DEBUG ETL - WITH DATABASE CONNECTION")
    print("="*70)
    print(f"\n{mode_str}")
    print(f"📅 Checking period: {start_str} to {end_str}")
    print(f"⏰ Debug run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Connect to database
    if not dry_run:
        print("🔌 Connecting to database...")
        db = DoltDBManager()
        try:
            db.connect()
            print("✅ Database connected\n")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            print("\n💡 Make sure:")
            print("   1. Dolt SQL server is running: cd macroeconomia && dolt sql-server")
            print("   2. DOLT_DB environment variable is set correctly")
            return 1
    else:
        db = None
    
    try:
        all_records_to_insert = []
        
        # 1. Debug UVA data
        print("\n" + "="*70)
        print("🔵 UVA DATA")
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
                
                # Add to records to insert
                for item in recent_uva:
                    all_records_to_insert.append({
                        'date': item['date'],
                        'kind': item['kind'],
                        'pair': 'UVA_ARS',
                        'rate': item['rate']
                    })
        else:
            print("⚠️  No UVA data fetched")
        
        # 2. Debug USD data (all types)
        print("\n" + "="*70)
        print("🔵 USD DATA - ALL TYPES")
        print("="*70)
        
        usd_types = [
            ('formal', 'USD_ARS', 'Official Dollar'),
            ('mep', 'USDM_ARS', 'MEP Dollar'),
            ('informal', 'USDB_ARS', 'Blue Dollar'),
            ('cripto', 'USDC_ARS', 'Crypto Dollar')
        ]
        
        for kind, pair, label in usd_types:
            print(f"\n{'─'*70}")
            print(f"🔍 Fetching {label} ({pair})")
            print(f"{'─'*70}")
            print(f"   Request: {kind} from {start_str} to {end_str}")
            
            usd_data = fetch_ambito_dolar(kind, start_str, end_str)
            
            if usd_data:
                print(f"\n📊 {label} Summary:")
                print(f"   Total records fetched: {len(usd_data)}")
                print(f"   Expected: ~{len(usd_data) // 2} dates × 2 (bid/ask)")
                
                # Group by date to show structure
                from collections import defaultdict
                dates_dict = defaultdict(list)
                for item in usd_data:
                    dates_dict[item['date']].append(item)
                
                print(f"   Unique dates: {len(dates_dict)}")
                
                # Show sample
                print(f"\n📋 Sample {label} data (first 10 records):")
                print("-"*70)
                print(f"{'Date':<12} | {'Kind':<10} | {'Rate':>15}")
                print("-"*70)
                for item in usd_data[:10]:
                    print(f"{item['date']:<12} | {item['kind']:<10} | {item['rate']:>15.2f}")
                if len(usd_data) > 10:
                    print(f"... ({len(usd_data) - 10} more records)")
                print("-"*70)
                
                # Show date range
                dates = [item['date'] for item in usd_data]
                if dates:
                    print(f"\n📅 {label} Date range: {min(dates)} to {max(dates)}")
                
                # Add to records to insert
                for item in usd_data:
                    all_records_to_insert.append({
                        'date': item['date'],
                        'kind': item['kind'],
                        'pair': pair,
                        'rate': item['rate']
                    })
            else:
                print(f"   ⚠️  No {label} data fetched")
        
        # 3. Summary of all records to insert
        print("\n" + "="*70)
        print("📊 SUMMARY - ALL RECORDS TO INSERT")
        print("="*70)
        print(f"\nTotal records fetched: {len(all_records_to_insert)}")
        
        # Group by pair
        from collections import defaultdict
        by_pair = defaultdict(list)
        for record in all_records_to_insert:
            by_pair[record['pair']].append(record)
        
        print(f"\n📋 Records by currency pair:")
        for pair, records in sorted(by_pair.items()):
            dates = sorted(set([r['date'] for r in records]))
            print(f"   {pair:15} : {len(records):4} records ({len(dates)} unique dates)")
            print(f"                  Date range: {min(dates)} to {max(dates)}")
        
        # 4. Insert to database (if not dry-run)
        if not dry_run and db:
            print("\n" + "="*70)
            print("💾 INSERTING TO DATABASE")
            print("="*70)
            
            inserted_count = 0
            ignored_count = 0
            errors = []
            
            for i, record in enumerate(all_records_to_insert):
                try:
                    result = db.insert_fx_rate(
                        date=record['date'],
                        kind=record['kind'],
                        pair=record['pair'],
                        rate=record['rate']
                    )
                    
                    if result.get('inserted', False):
                        inserted_count += 1
                        if (i + 1) % 50 == 0 or i == 0:
                            print(f"   ✅ [{i+1}/{len(all_records_to_insert)}] INSERTED: {record['date']} | {record['pair']} | {record['kind']} | {record['rate']:.2f}")
                    else:
                        ignored_count += 1
                        if (i + 1) % 100 == 0:
                            print(f"   ℹ️  [{i+1}/{len(all_records_to_insert)}] IGNORED (already exists): {record['date']} | {record['pair']} | {record['kind']}")
                except Exception as e:
                    errors.append((record, str(e)))
                    print(f"   ❌ ERROR inserting {record}: {e}")
            
            print(f"\n📊 Insert Summary:")
            print(f"   ✅ Inserted: {inserted_count} new records")
            print(f"   ℹ️  Ignored: {ignored_count} existing records")
            if errors:
                print(f"   ❌ Errors: {len(errors)} failed inserts")
                print(f"\n⚠️  First 5 errors:")
                for record, error in errors[:5]:
                    print(f"      {record}: {error}")
        else:
            print("\n" + "="*70)
            print("🔍 DRY-RUN MODE - NO INSERTS PERFORMED")
            print("="*70)
            print(f"\n💡 To actually insert these records, run without --dry-run flag:")
            print(f"   python etl/debug_etl_with_db.py")
            print(f"\n📋 Would insert {len(all_records_to_insert)} records")
        
        print("\n" + "="*70)
        print("✅ DEBUG COMPLETED")
        print("="*70 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        if db:
            db.disconnect()
            print("🔌 Database disconnected")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug ETL with database connection')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Dry-run mode: show what would be inserted without actually inserting')
    parser.add_argument('--days', type=int, default=None,
                        help='Number of days to check (default: from DEBUG_DAYS env var or 30)')
    
    args = parser.parse_args()
    
    # Get days from args or env var or default
    days = args.days if args.days else int(os.getenv('DEBUG_DAYS', '30'))
    
    exit_code = debug_etl_with_db(days_back=days, dry_run=args.dry_run)
    sys.exit(exit_code)

