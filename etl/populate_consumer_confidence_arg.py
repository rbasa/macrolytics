#!/usr/bin/env python3

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
TABLE_NAME = "consumer_confidence_argentina"

LAST_PERIODS = 1000


SERIES = {
  "icc_nacional":
    "380.3_ICC_NACIONNAL_0_T_12",

  "icc_capital":
    "380.3_DESAGREGACTAL_0_T_30",

  "icc_interior":
    "380.3_DESAGREGACIOR_0_T_31",

  "icc_gba":
    "380.3_DESAGREGACGBA_0_T_26",

  "icc_situacion_personal":
    "380.3_DESAGREGACNAL_0_T_43",

  "icc_situacion_macro":
    "380.3_DESAGREGACCRO_0_T_40",

  "icc_bienes_durables_inmuebles":
    "380.3_DESAGREGACLES_0_T_50",
}


def fetch_data():
  columns = list(SERIES)
  ids = list(SERIES.values())

  response = requests.get(
    API_URL,
    params={
      "ids": ",".join(ids),
      "last": LAST_PERIODS,
      "metadata": "none",
    },
    timeout=60,
  )

  if not response.ok:
    raise RuntimeError(
      f"Datos Argentina error {response.status_code}: "
      f"{response.text}"
    )

  data = response.json().get("data", [])

  if not data:
    raise RuntimeError(
      "No consumer confidence data returned"
    )

  df = pd.DataFrame(
    data,
    columns=[
      "period",
      *columns,
    ],
  )

  df["period"] = pd.to_datetime(
    df["period"],
  ).dt.date

  return df


def upsert(db, data):
  columns = list(SERIES)
  all_columns = [
    "period",
    *columns,
  ]

  placeholders = ", ".join(
    ["%s"] * len(all_columns)
  )

  updates = ", ".join(
    f"{column}=VALUES({column})"
    for column in columns
  )

  sql = (
    f"INSERT INTO {TABLE_NAME} "
    f"({', '.join(all_columns)}) "
    f"VALUES ({placeholders}) "
    f"ON DUPLICATE KEY UPDATE {updates}"
  )

  for row in data.itertuples(
    index=False,
    name=None,
  ):
    clean_row = tuple(
      None if pd.isna(value) else value
      for value in row
    )

    db.query(sql, clean_row)


def main():
  db = DoltDBManager()

  try:
    db.connect()

    data = fetch_data()

    LOGGER.info(
      "Fetched %s ICC periods",
      len(data),
    )

    upsert(
      db,
      data,
    )

    db.dolt_add(
      TABLE_NAME,
    )

    result = db.dolt_commit(
      "Update consumer confidence Argentina - "
      f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    )

    LOGGER.info(
      "Dolt commit result: %s",
      result,
    )

  finally:
    db.disconnect()


if __name__ == "__main__":
  logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
  )

  main()