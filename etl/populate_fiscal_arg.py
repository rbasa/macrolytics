#!/usr/bin/env python3
"""
Populate Argentina fiscal accounts from Datos Argentina.

Sources:
  - Sector Público Nacional - Base Caja:
    accounting aggregates and fiscal balances.
  - IMIG:
    detailed tax revenue components.

All values are millions of current Argentine pesos.

Initial historical load:
  LAST_PERIODS = 1000

Normal daily update:
  LAST_PERIODS = 6

Usage:
  python etl/populate_fiscal_arg.py
"""

import logging
import os
import sys
from datetime import datetime

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)

SEARCH_URL = (
  "https://apis.datos.gob.ar/series/api/search/"
)

SERIES_URL = (
  "https://apis.datos.gob.ar/series/api/series"
)

TABLE_NAME = "fiscal_argentina"

# First run: 1000
# Normal runs: 6
LAST_PERIODS = 6

MAX_SERIES_PER_REQUEST = 30


AIF_DATASET = (
  "Esquema Ahorro - Inversión - Financiamiento. "
  "Sector Público Nacional. Base Caja."
)

IMIG_DATASET = (
  "Informe Mensual de Ingresos y Gastos del "
  "Sector Público Nacional No Financiero (IMIG)"
)


# ------------------------------------------------------------------
# Canonical database column -> official series description search
# ------------------------------------------------------------------

AIF_SERIES = {
  # Ingresos corrientes
  "ingresos_corrientes_total":
    "Total ingresos corrientes Metodología 2017",

  "ingresos_tributarios_total":
    "Ingresos corrientes ingresos tributarios Metodología 2017",

  "ingresos_aportes_contribuciones_seguridad_social":
    "Ingresos corrientes aportes y contrib. a la seg. social Metodología 2017",

  "ingresos_no_tributarios":
    "Ingresos corrientes ingresos no tributarios Metodología 2017",

  "ingresos_ventas_bienes_servicios_adm_publica":
    "Ingresos corrientes ventas de bs. y serv. de las adm. pub. Metodología 2017",

  "ingresos_operacion":
    "Ingresos corrientes ingresos de operacion Metodología 2017",

  "ingresos_rentas_propiedad_netas":
    "Ingresos corrientes rentas de la propiedad netas Metodología 2017",

  "ingresos_transferencias_corrientes":
    "Ingresos corrientes transferencias corrientes Metodología 2017",

  "ingresos_otros":
    "Ingresos corrientes otros ingresos Metodología 2017",

  "ingresos_superavit_operativo_empresas_publicas":
    "Ingresos corrientes superavit operativo empresas pub. Metodología 2017",

  # Gastos corrientes
  "gastos_corrientes_total":
    "Total gastos corrientes Metodología 2017",

  "gastos_consumo_operacion_total":
    "Gastos corrientes gastos de consumo y operacion total Metodología 2017",

  "gastos_consumo_operacion_remuneraciones":
    "Gastos corrientes gastos de consumo y operacion remuneraciones Metodología 2017",

  "gastos_consumo_operacion_bienes_servicios":
    "Gastos corrientes gastos de consumo y operacion bienes y servicios Metodología 2017",

  "gastos_consumo_operacion_otros":
    "Gastos corrientes gastos de consumo y operacion otros gastos Metodología 2017",

  "gastos_intereses_otras_rentas_total":
    "Gastos corrientes intereses y otras rentas de la prop. total Metodología 2017",

  "gastos_intereses_netos":
    "Gastos corrientes intereses y otras rentas de la prop. intereses netos Metodología 2017",

  "gastos_otras_rentas":
    "Gastos corrientes intereses y otras rentas de la prop. otras rentas Metodología 2017",

  "gastos_prestaciones_seguridad_social":
    "Gastos corrientes prestaciones de la seguridad social Metodología 2017",

  "gastos_otros_corrientes":
    "Gastos corrientes otros gastos corrientes Metodología 2017",

  "gastos_transferencias_corrientes_total":
    "Gastos corrientes transferencias corrientes total Metodología 2017",

  "gastos_transferencias_sector_privado":
    "Gastos corrientes transferencias corrientes al sector privado total sector privado Metodología 2017",

  "gastos_transferencias_sector_publico_total":
    "Gastos corrientes transferencias corrientes al sector público total Metodología 2017",

  "gastos_transferencias_provincias_caba":
    "Gastos corrientes transferencias corrientes al sector público provincias y caba total Metodología 2017",

  "gastos_transferencias_universidades":
    "Gastos corrientes transferencias corrientes al sector público universidades Metodología 2017",

  "gastos_transferencias_sector_publico_otras":
    "Gastos corrientes transferencias corrientes al sector público otras Metodología 2017",

  "gastos_transferencias_sector_externo":
    "Gastos corrientes transferencias corrientes al sector externo Metodología 2017",

  "gastos_otros":
    "Gastos corrientes otros gastos Metodología 2017",

  "gastos_deficit_operativo_empresas_publicas":
    "Gastos corrientes deficit operativo empresas pub. Metodología 2017",

  # Resultado económico
  "resultado_economico":
    "Resultado economico ahorro desahorro Metodología 2017",

  # Capital
  "recursos_capital":
    "Recursos de capital total recursos de capital Metodología 2017",

  "gastos_capital_total":
    "Total gastos de capital Metodología 2017",

  "gastos_capital_inversion_real_directa":
    "Gastos de capital inversion real directa Metodología 2017",

  "gastos_capital_transferencias_total":
    "Gastos de capital transferencias de capital total Metodología 2017",

  "gastos_capital_transferencias_provincias_caba":
    "Gastos de capital transferencias de capital a provincias y caba total Metodología 2017",

  "gastos_capital_transferencias_otras":
    "Gastos de capital transferencias de capital otras Metodología 2017",

  "gastos_capital_inversion_financiera_total":
    "Gastos de capital inversion financiera total Metodología 2017",

  "gastos_capital_inversion_financiera_provincias_caba":
    "Gastos de capital inversion financiera a provincias y caba Metodología 2017",

  "gastos_capital_inversion_financiera_resto":
    "Gastos de capital inversion financiera resto Metodología 2017",

  # Antes de figurativos
  "ingresos_antes_figurativos":
    "Ingresos antes de figurativos Metodología 2017",

  "gastos_antes_figurativos":
    "Gastos antes de figurativos Metodología 2017",

  "resultado_financiero_antes_figurativos":
    "Resultado financiero antes de figurativos Metodología 2017",

  # Figurativos
  "contribuciones_figurativas_total":
    "Contribuciones figurativas total Metodología 2017",

  "contribuciones_figurativas_tesoro_nacional":
    "Contribuciones figurativas del Tesoro Nacional Metodología 2017",

  "contribuciones_figurativas_recursos_afectados":
    "Contribuciones figurativas de Recursos Afectados Metodología 2017",

  "contribuciones_figurativas_organismos_descentralizados":
    "Contribuciones figurativas de Organismos Descentralizados Metodología 2017",

  "contribuciones_figurativas_seguridad_social":
    "Contribuciones figurativas de Instituciones de Seguridad Social Metodología 2017",

  "contribuciones_figurativas_pami_fondos_otros":
    "Contribuciones figurativas PAMI Fondos Fiduciarios y Otros Metodología 2017",

  "gastos_figurativos":
    "Gastos figurativos Metodología 2017",

  # Después de figurativos
  "ingresos_despues_figurativos":
    "Ingresos despues de figurativos Metodología 2017",

  "gastos_primarios_despues_figurativos":
    "Gastos primarios despues de figurativos Metodología 2017",

  "gastos_despues_figurativos":
    "Gastos despues de figurativos Metodología 2017",

  "resultado_primario":
    "Resultado primario Metodología 2017",

  "resultado_financiero":
    "Resultado financiero Metodología 2017",

  # Memo items
  "rentas_percibidas_bcra":
    "Rentas percibidas del BCRA Metodología 2017",

  "rentas_publicas_fgs_otros":
    "Rentas públicas percibidas por el FGS y otros Metodología 2017",

  "intereses_pagados_intrasector_publico":
    "Intereses pagados intra-sector público Metodología 2017",
}


IMIG_SERIES = {
  "ingresos_tributarios_iva":
    "IMIG Ingresos totales Ingresos tributarios IVA neto de reintegros",

  "ingresos_tributarios_ganancias":
    "IMIG Ingresos totales Ingresos tributarios Ganancias",

  "ingresos_tributarios_debitos_creditos":
    "IMIG Ingresos totales Ingresos tributarios Débitos y créditos",

  "ingresos_tributarios_bienes_personales":
    "IMIG Ingresos totales Ingresos tributarios Bienes personales",

  "ingresos_tributarios_combustibles":
    "IMIG Ingresos totales Ingresos tributarios Combustibles",

  "ingresos_tributarios_derechos_exportacion":
    "IMIG Ingresos totales Ingresos tributarios Derechos de exportación",

  "ingresos_tributarios_derechos_importacion":
    "IMIG Ingresos totales Ingresos tributarios Derechos de importación",

  "ingresos_tributarios_impuestos_internos":
    "IMIG Ingresos totales Ingresos tributarios Impuestos internos",

  "ingresos_tributarios_resto":
    "IMIG Ingresos totales Ingresos tributarios Resto de ingresos tributarios",
}


def normalize_text(value):
  """Normalize text for metadata matching."""
  return (
    str(value)
    .lower()
    .replace(".", " ")
    .replace(",", " ")
    .replace("-", " ")
  )


def search_series(query):
  """Search Datos Argentina metadata."""
  response = requests.get(
    SEARCH_URL,
    params={
      "q": query,
      "limit": 100,
    },
    timeout=60,
  )
  response.raise_for_status()

  return response.json().get("data", [])


def resolve_series_id(
  query,
  dataset_title,
):
  """
  Resolve one monthly official series from metadata.

  Fails instead of guessing if no valid series can be found.
  """
  results = search_series(query)

  candidates = []

  for result in results:
    field = result.get("field", {})
    dataset = result.get("dataset", {})

    if (
      dataset.get("title") != dataset_title
      or field.get("frequency") != "R/P1M"
    ):
      continue

    description = normalize_text(
      field.get("description", "")
    )

    # AIF current methodology
    if dataset_title == AIF_DATASET:
      if "2017" not in description:
        continue

    candidates.append(field)

  if not candidates:
    raise RuntimeError(
      f"No monthly series found for: {query}"
    )

  # Prefer the series with the most recent endpoint.
  candidates.sort(
    key=lambda item:
      item.get("time_index_end") or "",
    reverse=True,
  )

  selected = candidates[0]

  LOGGER.info(
    "%s -> %s | %s",
    query,
    selected["id"],
    selected.get("description"),
  )

  return selected["id"]


def resolve_all_series():
  """Resolve canonical columns to Datos Argentina IDs."""
  resolved = {}

  for column, query in AIF_SERIES.items():
    resolved[column] = resolve_series_id(
      query,
      AIF_DATASET,
    )

  for column, query in IMIG_SERIES.items():
    resolved[column] = resolve_series_id(
      query,
      IMIG_DATASET,
    )

  return resolved


def chunks(items, size):
  for index in range(
    0,
    len(items),
    size,
  ):
    yield items[index:index + size]


def fetch_batch(series_items):
  """Fetch one group of time series."""
  columns = [
    column
    for column, _ in series_items
  ]

  ids = [
    series_id
    for _, series_id in series_items
  ]

  response = requests.get(
    SERIES_URL,
    params={
      "ids": ",".join(ids),
      "last": LAST_PERIODS,
      "metadata": "none",
    },
    timeout=60,
  )
  response.raise_for_status()

  data = response.json().get(
    "data",
    [],
  )

  if not data:
    raise RuntimeError(
      "Datos Argentina returned no observations"
    )

  return pd.DataFrame(
    data,
    columns=[
      "period",
      *columns,
    ],
  )


def fetch_fiscal_data(series):
  """Fetch all resolved fiscal series."""
  frames = []

  series_items = list(
    series.items()
  )

  for batch in chunks(
    series_items,
    MAX_SERIES_PER_REQUEST,
  ):
    frames.append(
      fetch_batch(batch)
    )

  fiscal = frames[0]

  for frame in frames[1:]:
    fiscal = fiscal.merge(
      frame,
      on="period",
      how="outer",
    )

  fiscal["period"] = pd.to_datetime(
    fiscal["period"],
  ).dt.date

  fiscal = (
    fiscal
    .sort_values("period")
    .reset_index(drop=True)
  )

  LOGGER.info(
    "Fetched %s fiscal periods from %s through %s",
    len(fiscal),
    fiscal["period"].min(),
    fiscal["period"].max(),
  )

  return fiscal


def clean_value(value):
  """Convert pandas NaN to SQL NULL."""
  if pd.isna(value):
    return None

  return float(value)


def upsert_fiscal(
  db,
  fiscal,
  series,
):
  """Insert new rows and update revised observations."""
  value_columns = list(
    series.keys()
  )

  columns = [
    "period",
    *value_columns,
  ]

  placeholders = ", ".join(
    ["%s"] * len(columns)
  )

  updates = ", ".join(
    f"{column}=VALUES({column})"
    for column in value_columns
  )

  sql = f"""
    INSERT INTO {TABLE_NAME}
      ({", ".join(columns)})
    VALUES
      ({placeholders})
    ON DUPLICATE KEY UPDATE
      {updates}
  """

  for _, row in fiscal.iterrows():
    values = [
      row["period"],
      *[
        clean_value(row[column])
        for column in value_columns
      ],
    ]

    db.query(
      sql,
      tuple(values),
    )

  LOGGER.info(
    "Stored %s fiscal periods",
    len(fiscal),
  )


def main():
  db = DoltDBManager()

  try:
    LOGGER.info(
      "Resolving official fiscal series"
    )

    series = resolve_all_series()

    LOGGER.info(
      "Resolved %s series",
      len(series),
    )

    fiscal = fetch_fiscal_data(
      series,
    )

    db.connect()

    upsert_fiscal(
      db,
      fiscal,
      series,
    )

    db.dolt_add(
      TABLE_NAME,
    )

    result = db.dolt_commit(
      "Update Argentina fiscal data - "
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
    format=(
      "%(levelname)s:"
      "%(name)s:"
      "%(message)s"
    ),
  )

  main()