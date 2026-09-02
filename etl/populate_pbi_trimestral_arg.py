#!/usr/bin/env python3
"""Load Argentina's official quarterly national accounts from INDEC."""

from __future__ import annotations

import logging
import os
import re
import sys
import unicodedata
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)
SOURCE_ROOT = "https://www.indec.gob.ar/ftp/cuadros/economia"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Macrolytics/1.0)"}
TABLE_TOTAL = "pbi_trimestral_argentina"
TABLE_SECTOR = "pbi_sector_argentina"

AGGREGATE_COLUMNS = {
  "PIB": "pib",
  "Importaciones": "importaciones",
  "Consumo privado": "consumo_privado",
  "Consumo público": "consumo_publico",
  "FBCF": "formacion_bruta_capital_fijo",
  "Exportaciones": "exportaciones",
}

SECTOR_MEASURES = {
  "Cuadro 3": "vab_precios_2004",
  "Cuadro 4": "vab_precios_corrientes",
  "Cuadro 5": "indice_volumen_fisico",
  "Cuadro 6": "indice_precios_implicitos",
}


def normalize(value):
  text = unicodedata.normalize("NFKD", str(value))
  return " ".join(
    text.encode("ascii", "ignore").decode().lower().split()
  )


def release_suffixes(today=None):
  """Return plausible INDEC quarterly release suffixes, newest first."""
  today = today or date.today()
  suffixes = []
  for year in range(today.year, today.year - 3, -1):
    for month in (12, 9, 6, 3):
      candidate = date(year, month, 1)
      # INDEC publishes each quarterly release around the middle of the month.
      if candidate < today.replace(day=1) or (
        candidate == today.replace(day=1) and today.day >= 15
      ):
        suffixes.append(candidate.strftime("%m_%y"))
  return suffixes


def discover_source_urls(session=None, today=None):
  """Find the newest release for which all three official workbooks exist."""
  session = session or requests.Session()
  session.headers.update(REQUEST_HEADERS)
  templates = {
    "original": "sh_oferta_demanda_{suffix}.xls",
    "desestacionalizado": "sh_oferta_demanda_desest_{suffix}.xls",
    "sectores": "sh_VBP_VAB_{suffix}.xls",
  }

  for suffix in release_suffixes(today):
    urls = {
      key: f"{SOURCE_ROOT}/{template.format(suffix=suffix)}"
      for key, template in templates.items()
    }
    responses = [session.head(url, timeout=30) for url in urls.values()]
    if all(response.status_code == 200 for response in responses):
      LOGGER.info("Using INDEC quarterly national accounts release %s", suffix)
      return urls

  raise RuntimeError("No complete recent INDEC quarterly GDP release was found")


def download_workbook(url, session=None):
  session = session or requests.Session()
  session.headers.update(REQUEST_HEADERS)
  response = session.get(url, timeout=90)
  response.raise_for_status()
  if not response.content:
    raise RuntimeError(f"INDEC returned an empty workbook: {url}")
  return response.content


def quarter_period(year, quarter):
  quarter_number = {"i": 1, "ii": 2, "iii": 3, "iv": 4}[normalize(quarter)]
  return date(int(year), (quarter_number - 1) * 3 + 1, 1)


def parse_desest_sheet(workbook, sheet_name):
  frame = pd.read_excel(BytesIO(workbook), sheet_name=sheet_name, header=None)
  header_row = next(
    index for index, row in frame.iterrows()
    if normalize(row.iloc[0]) == "ano" and normalize(row.iloc[1]) == "trimestre"
  )
  columns = [str(value).strip() for value in frame.iloc[header_row]]
  data = frame.iloc[header_row + 1:].copy()
  data.columns = columns
  data["Año"] = pd.to_numeric(data["Año"], errors="coerce").ffill()
  data = data[data["Trimestre"].map(normalize).isin({"i", "ii", "iii", "iv"})]
  records = []
  for row in data.to_dict("records"):
    record = {"periodo": quarter_period(row["Año"], row["Trimestre"])}
    for source, target in AGGREGATE_COLUMNS.items():
      record[target] = pd.to_numeric(row.get(source), errors="coerce")
    records.append(record)
  return pd.DataFrame(records)


def parse_original_pib(workbook):
  """Read the raw, non-seasonally-adjusted GDP level from INDEC cuadro 1."""
  frame = pd.read_excel(BytesIO(workbook), sheet_name="cuadro 1", header=None)
  year_row = next(
    index for index, row in frame.iterrows()
    if sum(bool(re.match(r"^20\d{2}", str(value))) for value in row) >= 3
  )
  quarter_row = year_row + 1
  label_column = next(
    column for column in range(frame.shape[1])
    if any(normalize(value) == "producto interno bruto" for value in frame.iloc[:, column])
  )
  pib_row = next(
    index for index, value in frame.iloc[:, label_column].items()
    if normalize(value) == "producto interno bruto"
  )

  current_year = None
  records = []
  for column in range(label_column + 1, frame.shape[1]):
    year_match = re.match(r"^(20\d{2})", str(frame.iat[year_row, column]))
    if year_match:
      current_year = int(year_match.group(1))
    quarter = normalize(frame.iat[quarter_row, column])
    if current_year and quarter in {"1o trimestre", "2o trimestre", "3o trimestre", "4o trimestre"}:
      number = int(quarter[0])
      value = pd.to_numeric(frame.iat[pib_row, column], errors="coerce")
      records.append({
        "periodo": date(current_year, (number - 1) * 3 + 1, 1),
        "pib_original": value,
      })
  return pd.DataFrame(records)


def parse_aggregates(original_workbook, adjusted_workbook):
  adjusted = parse_desest_sheet(adjusted_workbook, "desestacionalizado n")
  adjusted = adjusted.rename(columns={
    column: f"{column}_desestacionalizado"
    for column in AGGREGATE_COLUMNS.values()
  })
  original = parse_original_pib(original_workbook)
  result = original.merge(adjusted, on="periodo", how="outer", validate="one_to_one")
  if result.empty or result["periodo"].duplicated().any():
    raise RuntimeError("INDEC aggregate workbooks produced invalid quarterly periods")
  return result.sort_values("periodo").reset_index(drop=True)


def parse_quarterly_matrix(workbook, sheet_name, measure):
  frame = pd.read_excel(BytesIO(workbook), sheet_name=sheet_name, header=None)
  year_row = next(
    index for index, row in frame.iterrows()
    if sum(bool(re.match(r"^20\d{2}", str(value))) for value in row) >= 3
  )
  quarter_row = year_row + 1
  records = []
  current_year = None

  for column in range(1, frame.shape[1]):
    year_match = re.match(r"^(20\d{2})", str(frame.iat[year_row, column]))
    if year_match:
      current_year = int(year_match.group(1))
    quarter = normalize(frame.iat[quarter_row, column])
    if not current_year or quarter not in {
      "1o trimestre", "2o trimestre", "3o trimestre", "4o trimestre"
    }:
      continue
    period = date(current_year, (int(quarter[0]) - 1) * 3 + 1, 1)
    for row in range(quarter_row + 1, frame.shape[0]):
      activity = frame.iat[row, 0]
      value = pd.to_numeric(frame.iat[row, column], errors="coerce")
      if pd.isna(activity) or pd.isna(value):
        continue
      records.append({
        "periodo": period,
        "actividad": " ".join(str(activity).split()),
        "medida": measure,
        "valor": float(value),
        "orden_fuente": row,
      })
  return records


def parse_sectors(workbook):
  records = []
  for sheet_name, measure in SECTOR_MEASURES.items():
    records.extend(parse_quarterly_matrix(workbook, sheet_name, measure))
  result = pd.DataFrame(records)
  if result.empty or result.duplicated(["periodo", "actividad", "medida"]).any():
    raise RuntimeError("INDEC sector workbook produced invalid or duplicate observations")
  return result.sort_values(["periodo", "orden_fuente", "medida"]).reset_index(drop=True)


def create_tables(db):
  db.query(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_TOTAL} (
      periodo DATE NOT NULL,
      pib_original DECIMAL(24,6),
      pib_desestacionalizado DECIMAL(24,6),
      importaciones_desestacionalizado DECIMAL(24,6),
      consumo_privado_desestacionalizado DECIMAL(24,6),
      consumo_publico_desestacionalizado DECIMAL(24,6),
      formacion_bruta_capital_fijo_desestacionalizado DECIMAL(24,6),
      exportaciones_desestacionalizado DECIMAL(24,6),
      PRIMARY KEY (periodo)
    )
  """)
  db.query(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_SECTOR} (
      periodo DATE NOT NULL,
      actividad VARCHAR(255) NOT NULL,
      medida VARCHAR(40) NOT NULL,
      valor DECIMAL(24,6),
      orden_fuente SMALLINT UNSIGNED NOT NULL,
      PRIMARY KEY (periodo, actividad, medida),
      INDEX idx_pbi_sector_medida_periodo (medida, periodo)
    )
  """)


def clean(value):
  return None if pd.isna(value) else float(value)


def upsert_aggregates(db, data):
  columns = ["periodo", "pib_original", *(
    f"{column}_desestacionalizado" for column in AGGREGATE_COLUMNS.values()
  )]
  placeholders = ", ".join(["%s"] * len(columns))
  updates = ", ".join(f"{column}=VALUES({column})" for column in columns[1:])
  sql = (
    f"INSERT INTO {TABLE_TOTAL} ({', '.join(columns)}) VALUES ({placeholders}) "
    f"ON DUPLICATE KEY UPDATE {updates}"
  )
  for row in data.to_dict("records"):
    db.query(sql, tuple(row["periodo"] if column == "periodo" else clean(row.get(column)) for column in columns))


def upsert_sectors(db, data):
  sql = f"""
    INSERT INTO {TABLE_SECTOR} (periodo, actividad, medida, valor, orden_fuente)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      valor=VALUES(valor), orden_fuente=VALUES(orden_fuente)
  """
  for row in data.to_dict("records"):
    db.query(sql, (
      row["periodo"], row["actividad"], row["medida"],
      clean(row["valor"]), int(row["orden_fuente"]),
    ))


def fetch_pbi_data():
  urls = discover_source_urls()
  session = requests.Session()
  session.headers.update(REQUEST_HEADERS)
  original = download_workbook(urls["original"], session)
  adjusted = download_workbook(urls["desestacionalizado"], session)
  sectors = download_workbook(urls["sectores"], session)
  return parse_aggregates(original, adjusted), parse_sectors(sectors)


def main():
  aggregates, sectors = fetch_pbi_data()
  db = DoltDBManager()
  try:
    db.connect()
    create_tables(db)
    upsert_aggregates(db, aggregates)
    upsert_sectors(db, sectors)
    db.dolt_add(TABLE_TOTAL)
    db.dolt_add(TABLE_SECTOR)
    result = db.dolt_commit(
      f"Update Argentina quarterly GDP - {datetime.now():%Y-%m-%d %H:%M:%S}"
    )
    LOGGER.info(
      "Stored %s aggregate quarters and %s sector observations: %s",
      len(aggregates), len(sectors), result,
    )
  finally:
    db.disconnect()


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
  main()
