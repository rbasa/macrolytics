#!/usr/bin/env python3
"""
Update recent UVA and USD exchange-rate data.

The script:
1. Fetches recent observations.
2. Inserts new rows into Dolt.
3. Creates a Dolt commit when data changed.

The GitHub Actions workflow is responsible for pushing to DoltHub.

Environment variables:
    DOLT_DB: Dolt SQL connection string.
    UPDATE_DAYS: Number of recent days to update. Defaults to 7.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager
from utils.fetch_usd_data import fetch_ambito_dolar
from utils.fetch_uva import fetch_uva_data


USD_SERIES = {
    "formal": "USD_ARS",
    "mep": "USDM_ARS",
    "informal": "USDB_ARS",
    "cripto": "USDC_ARS",
}


def insert_rates(db, data, pair):
    """Insert observations and return the number of new rows."""
    inserted = 0

    for item in data:
        result = db.insert_fx_rate(
            date=item["date"],
            kind=item["kind"],
            pair=pair,
            rate=item["rate"],
        )

        if result.get("inserted", False):
            inserted += 1

    return inserted


def update_recent_data(days_back=70):
    """Update UVA and USD observations from the last N days."""
    end_date = datetime.now()
    # start_date = end_date - timedelta(days=days_back)
    start_str = "2026-05-17"
    # start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"Updating data from {start_str} through {end_str}")

    db = DoltDBManager()
    updated_pairs = []

    try:
        db.connect()

        uva_data = fetch_uva_data() or []
        recent_uva = [
            item for item in uva_data
            if item["date"] >= start_str
        ]

        inserted = insert_rates(db, recent_uva, "UVA_ARS")

        if inserted:
            updated_pairs.append("UVA_ARS")
            print(f"UVA_ARS: inserted {inserted} rows")
        else:
            print("UVA_ARS: no new rows")

        for kind, pair in USD_SERIES.items():
            data = fetch_ambito_dolar(
                kind,
                start_str,
                end_str,
            ) or []

            inserted = insert_rates(db, data, pair)

            if inserted:
                updated_pairs.append(pair)
                print(f"{pair}: inserted {inserted} rows")
            else:
                print(f"{pair}: no new rows")

        if not updated_pairs:
            print("Database already up to date")
            return 0

        db.dolt_add("fx_rate")
        db.dolt_commit(
            "Update UVA and USD rates - "
            f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        )

        print(
            "Committed updates for: "
            + ", ".join(updated_pairs)
        )

        return 0

    except Exception as error:
        print(f"Daily update failed: {error}")
        return 1

    finally:
        db.disconnect()


if __name__ == "__main__":
    days = int(os.getenv("UPDATE_DAYS", "7"))
    sys.exit(update_recent_data(days_back=days))