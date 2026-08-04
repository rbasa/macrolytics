#!/usr/bin/env python3
"""
Fetch Argentina's monthly foreign-trade values and store them in Dolt.

The source is the Datos Argentina Time Series API. The underlying data comes
from INDEC's Intercambio Comercial Argentino (ICA) and is expressed in
millions of US dollars.

Only nominal trade values are loaded here. Price, quantity, value indices and
terms of trade can be added from a separate official source.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)

API_URL = "https://apis.datos.gob.ar/series/api/series"
DEFAULT_LAST_PERIODS = 5
TABLE_NAME = "trade_argentina"

TRADE_SERIES = {
  "exportaciones_usd": "74.3_IET_0_M_16",
  "importaciones_usd": "74.3_IIT_0_M_25",
  "balanza_comercial_usd": "74.3_ISC_0_M_19",
  "exportaciones_pp_valor": "74.3_IEPP_0_M_35",
  "exportaciones_moa_valor": "74.3_IEMOA_0_M_48",
  "exportaciones_moi_valor": "74.3_IEMOI_0_M_46",
  "exportaciones_cye_valor": "74.3_IECE_0_M_35",
  "importaciones_bienes_capital_valor": "74.3_IIBCA_0_M_32",
  "importaciones_bienes_intermedios_valor": "74.3_IIBI_0_M_36",
  "importaciones_combustibles_lubricantes_valor": "74.3_IICL_0_M_42",
  "importaciones_piezas_accesorios_capital_valor": "74.3_IIPABC_0_M_50",
  "importaciones_bienes_consumo_valor": "74.3_IIBCO_0_M_32",
  "importaciones_vehiculos_pasajeros_valor": "74.3_IIVAP_0_M_49",
  "importaciones_resto_valor": "74.3_IIR_0_M_23",
}


def fetch_trade(last_periods: int = DEFAULT_LAST_PERIODS) -> pd.DataFrame:
    """
    Fetch the latest monthly foreign-trade observations.

    Args:
        last_periods:
            Number of most recent monthly observations to request.
            Use a large value, such as 1000, for the initial historical load.

    Returns:
        A DataFrame whose columns match the nominal fields in trade_argentina.
    """
    if last_periods <= 0:
        raise ValueError("last_periods must be greater than zero")

    response = requests.get(
        API_URL,
        params={
            "ids": ",".join(TRADE_SERIES.values()),
            "last": last_periods,
            "metadata": "none",
        },
        timeout=45,
    )
    response.raise_for_status()

    data = response.json().get("data", [])
    if not data:
        raise RuntimeError("Datos Argentina returned no trade observations")

    trade = pd.DataFrame(data, columns=["period", *TRADE_SERIES])
    trade["period"] = pd.to_datetime(
        trade["period"],
        errors="raise",
    ).dt.date

    trade = trade.sort_values("period").reset_index(drop=True)

    LOGGER.info(
        "Fetched %s trade periods from %s through %s",
        len(trade),
        trade["period"].min(),
        trade["period"].max(),
    )

    return trade


def upsert_trade(db: DoltDBManager, trade: pd.DataFrame) -> None:
    """
    Insert new trade observations and update revised published values.
    """
    if trade.empty:
        LOGGER.info("No trade observations to store")
        return

    value_columns = list(TRADE_SERIES)
    columns = ["period", *value_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column}=VALUES({column})"
        for column in value_columns
    )

    sql = (
        f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    affected_rows = 0

    for row in trade.itertuples(index=False, name=None):
        result = db.query(sql, row)
        affected_rows += result[0]["affected_rows"]

    LOGGER.info(
        "Stored %s trade periods; Dolt reported %s affected rows",
        len(trade),
        affected_rows,
    )


def main() -> None:
    """
    Fetch trade data, persist it and create a Dolt commit.
    """
    last_periods = int(
        os.getenv("TRADE_LAST_PERIODS", DEFAULT_LAST_PERIODS)
    )

    db = DoltDBManager()

    try:
        db.connect()

        trade = fetch_trade(last_periods=last_periods)
        upsert_trade(db, trade)

        db.dolt_add(TABLE_NAME)
        result = db.dolt_commit(
            "Update Argentina foreign trade data - "
            f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        )

        LOGGER.info("Dolt commit result: %s", result)

    finally:
        db.disconnect()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    main()