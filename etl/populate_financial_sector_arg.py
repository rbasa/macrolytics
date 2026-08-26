#!/usr/bin/env python3
"""Load Argentina's main financial-sector indicators into Dolt.

The source is the BCRA Monetary Statistics API v4. The series are selected by
their fixed official identifiers: international reserves (1), reserve changes
from currency purchases (78), M2 (109), private-bank BADLAR TNA (7), and
private-bank TAMAR TNA (44).

Monthly BCRA balance data comes from the official din1_ser.txt dataset. Its
source values are thousands of ARS and are converted here to millions of ARS.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
import re
from urllib.parse import urljoin

import pdfplumber
import requests
from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)

API_URL = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias"
MONTHLY_BALANCE_URL = (
    "https://www.bcra.gob.ar/archivos/Pdfs/"
    "PublicacionesEstadisticas/din1_ser.txt"
)
BCRA_SITE = "https://www.bcra.gob.ar"
RESERVE_LIQUIDITY_INDEX_URL = (
    f"{BCRA_SITE}/wp-json/bcra/v1/planillas-fmi?lang=es"
)
BANK_REPORT_INDEX_URL = (
    f"{BCRA_SITE}/wp-json/bcra/v1/publicaciones"
    "?category=informe-sobre-bancos&lang=es&total=true"
)
TABLE_NAME = "financial_sector_argentina"
BALANCE_TABLE_NAME = "bcra_balance_argentina"
DEFAULT_DAYS_BACK = 30
DEFAULT_START_DATE = date(2017, 1, 1)
PAGE_SIZE = 3000

FINANCIAL_SERIES = {
    "reservas_internacionales_millones_usd": 1,
    "activos_reserva_millones_usd": 75,
    "compras_divisas_millones_usd": 78,
    "repo_externo_millones_usd": 76,
    "asignaciones_deg_2009_millones_usd": 83,
    "m2_millones_ars": 109,
    "base_monetaria_millones_ars": 15,
    "cuentas_corrientes_entidades_bcra_millones_ars": 19,
    "pases_pasivos_bcra_millones_ars": 152,
    "leliq_notalq_millones_ars": 155,
    "tenencias_lefi_entidades_millones_ars": 196,
    "creditos_sector_privado_millones_ars": 26,
    "creditos_sector_privado_millones_usd": 1355,
    "depositos_sector_privado_millones_usd": 1564,
    "badlar_bancos_privados_tna": 7,
    "tamar_bancos_privados_tna": 44,
}

SUPPLEMENTAL_COLUMNS = {
    "reservas_netas_liquidez_millones_usd": "DECIMAL(20,4)",
    "drenajes_netos_corto_plazo_millones_usd": "DECIMAL(20,4)",
    "morosidad_sector_privado_porcentaje": "DECIMAL(12,6)",
    "morosidad_empresas_porcentaje": "DECIMAL(12,6)",
    "morosidad_familias_porcentaje": "DECIMAL(12,6)",
}
BACKFILL_COLUMNS = (
    "creditos_sector_privado_millones_ars",
    "creditos_sector_privado_millones_usd",
    "depositos_sector_privado_millones_usd",
)

MONTHLY_BALANCE_SERIES = {
    "activos_externos_netos_millones_ars": 86,
    "oro_divisas_netos_millones_ars": 87,
    "aportes_organismos_internacionales_millones_ars": 89,
    "obligaciones_organismos_internacionales_millones_ars": 90,
    "activos_sector_oficial_millones_ars": 91,
    "activos_gobierno_nacional_millones_ars": 93,
    "adelantos_transitorios_millones_ars": 94,
    "titulos_publicos_millones_ars": 95,
    "creditos_entidades_financieras_millones_ars": 102,
    "fuentes_absorcion_millones_ars": 103,
    "depositos_totales_bcra_millones_ars": 104,
    "depositos_oficiales_bcra_millones_ars": 105,
    "depositos_gobierno_nacional_millones_ars": 106,
    "depositos_oficiales_moneda_extranjera_millones_ars": 107,
    "otras_obligaciones_millones_ars": 110,
    "depositos_entidades_moneda_extranjera_millones_ars": 111,
    "titulos_emitidos_bcra_millones_ars": 112,
    "cuentas_varias_netas_millones_ars": 113,
    "base_monetaria_millones_ars": 114,
}

TABLE_SCHEMAS = {
    TABLE_NAME: f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
          periodo DATE PRIMARY KEY,
          reservas_internacionales_millones_usd DECIMAL(20,4),
          activos_reserva_millones_usd DECIMAL(20,4),
          compras_divisas_millones_usd DECIMAL(20,4),
          repo_externo_millones_usd DECIMAL(20,4),
          asignaciones_deg_2009_millones_usd DECIMAL(20,4),
          m2_millones_ars DECIMAL(20,4),
          base_monetaria_millones_ars DECIMAL(20,4),
          cuentas_corrientes_entidades_bcra_millones_ars DECIMAL(20,4),
          pases_pasivos_bcra_millones_ars DECIMAL(20,4),
          leliq_notalq_millones_ars DECIMAL(20,4),
          tenencias_lefi_entidades_millones_ars DECIMAL(20,4),
          creditos_sector_privado_millones_ars DECIMAL(20,4),
          creditos_sector_privado_millones_usd DECIMAL(20,4),
          depositos_sector_privado_millones_usd DECIMAL(20,4),
          badlar_bancos_privados_tna DECIMAL(12,6),
          tamar_bancos_privados_tna DECIMAL(12,6),
          reservas_netas_liquidez_millones_usd DECIMAL(20,4),
          drenajes_netos_corto_plazo_millones_usd DECIMAL(20,4),
          morosidad_sector_privado_porcentaje DECIMAL(12,6),
          morosidad_empresas_porcentaje DECIMAL(12,6),
          morosidad_familias_porcentaje DECIMAL(12,6)
        )
    """,
    BALANCE_TABLE_NAME: f"""
        CREATE TABLE IF NOT EXISTS {BALANCE_TABLE_NAME} (
          periodo DATE PRIMARY KEY,
          activos_externos_netos_millones_ars DECIMAL(20,4),
          oro_divisas_netos_millones_ars DECIMAL(20,4),
          aportes_organismos_internacionales_millones_ars DECIMAL(20,4),
          obligaciones_organismos_internacionales_millones_ars DECIMAL(20,4),
          activos_sector_oficial_millones_ars DECIMAL(20,4),
          activos_gobierno_nacional_millones_ars DECIMAL(20,4),
          adelantos_transitorios_millones_ars DECIMAL(20,4),
          titulos_publicos_millones_ars DECIMAL(20,4),
          creditos_entidades_financieras_millones_ars DECIMAL(20,4),
          fuentes_absorcion_millones_ars DECIMAL(20,4),
          depositos_totales_bcra_millones_ars DECIMAL(20,4),
          depositos_oficiales_bcra_millones_ars DECIMAL(20,4),
          depositos_gobierno_nacional_millones_ars DECIMAL(20,4),
          depositos_oficiales_moneda_extranjera_millones_ars DECIMAL(20,4),
          otras_obligaciones_millones_ars DECIMAL(20,4),
          depositos_entidades_moneda_extranjera_millones_ars DECIMAL(20,4),
          titulos_emitidos_bcra_millones_ars DECIMAL(20,4),
          cuentas_varias_netas_millones_ars DECIMAL(20,4),
          base_monetaria_millones_ars DECIMAL(20,4)
        )
    """,
}


def ensure_tables(db: DoltDBManager) -> None:
    """Create the ETL-owned tables before querying or storing data."""
    for schema in TABLE_SCHEMAS.values():
        db.query(schema)


def ensure_financial_columns(db: DoltDBManager) -> None:
    """Add columns introduced after the table was first created."""
    existing = {
        row["Field"]
        for row in db.query(f"SHOW COLUMNS FROM {TABLE_NAME}")
    }
    column_types = {
        **{
            column: (
                "DECIMAL(12,6)"
                if column.endswith("_tna")
                else "DECIMAL(20,4)"
            )
            for column in FINANCIAL_SERIES
        },
        **SUPPLEMENTAL_COLUMNS,
    }
    for column, sql_type in column_types.items():
        if column not in existing:
            db.query(
                f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column} {sql_type}"
            )


def parse_localized_decimal(value: object) -> Decimal:
    """Parse Spanish or English thousands/decimal separators."""
    text = str(value).strip().replace(" ", "")
    if not text:
        return Decimal("0")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    return Decimal(text)


def fetch_series(
    series_id: int,
    start_date: date,
    end_date: date,
    *,
    session=requests,
) -> dict[date, Decimal]:
    """Fetch every observation for one BCRA series in a date range."""
    observations: dict[date, Decimal] = {}
    offset = 0

    while True:
        response = session.get(
            f"{API_URL}/{series_id}",
            params={
                "desde": start_date.isoformat(),
                "hasta": end_date.isoformat(),
                "offset": offset,
                "limit": PAGE_SIZE,
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != 200:
            raise RuntimeError(
                f"BCRA returned status {payload.get('status')} "
                f"for series {series_id}"
            )

        results = payload.get("results") or []
        detail = results[0].get("detalle", []) if results else []

        for item in detail:
            if item.get("valor") is None:
                continue
            period = datetime.strptime(item["fecha"], "%Y-%m-%d").date()
            observations[period] = Decimal(str(item["valor"]))

        count = (
            payload.get("metadata", {})
            .get("resultset", {})
            .get("count", len(detail))
        )
        offset += len(detail)

        if not detail or offset >= count or len(detail) < PAGE_SIZE:
            break

    return observations


def fetch_financial_sector(
    start_date: date,
    end_date: date,
    *,
    session=requests,
) -> list[dict]:
    """Fetch and outer-join the official series by observation date."""
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    values_by_column = {
        column: fetch_series(
            series_id,
            start_date,
            end_date,
            session=session,
        )
        for column, series_id in FINANCIAL_SERIES.items()
    }

    periods = sorted({
        period
        for values in values_by_column.values()
        for period in values
    })

    rows = [
        {
            "periodo": period,
            **{
                column: values.get(period)
                for column, values in values_by_column.items()
            },
        }
        for period in periods
    ]

    LOGGER.info(
        "Fetched %s financial-sector dates from %s through %s",
        len(rows),
        start_date,
        end_date,
    )
    return rows


def fetch_monthly_balance(
    start_date: date,
    *,
    session=requests,
) -> list[dict]:
    """Fetch selected monthly analytical-balance series from BCRA TXT."""
    response = session.get(MONTHLY_BALANCE_URL, timeout=60)
    response.raise_for_status()

    columns_by_id = {
        series_id: column
        for column, series_id in MONTHLY_BALANCE_SERIES.items()
    }
    rows_by_period: dict[date, dict] = {}

    for line in response.text.splitlines():
        parts = line.strip().split(";")
        if len(parts) != 3:
            continue

        try:
            series_id = int(parts[0])
        except ValueError:
            continue

        column = columns_by_id.get(series_id)
        if column is None or not parts[2]:
            continue

        period = datetime.strptime(parts[1], "%d/%m/%Y").date()
        if period < start_date:
            continue

        row = rows_by_period.setdefault(period, {"periodo": period})
        row[column] = Decimal(parts[2].replace(",", ".")) / Decimal("1000")

    rows = []
    for period in sorted(rows_by_period):
        source = rows_by_period[period]
        rows.append({
            "periodo": period,
            **{
                column: source.get(column)
                for column in MONTHLY_BALANCE_SERIES
            },
        })

    LOGGER.info("Fetched %s monthly BCRA balance periods", len(rows))
    return rows


def _first_numeric_cell(row: list[object]) -> Decimal:
    for value in row[1:]:
        if value not in (None, ""):
            try:
                return parse_localized_decimal(value)
            except Exception:
                continue
    raise ValueError(f"No numeric value found in NEDD row: {row!r}")


def parse_reserve_liquidity_pdf(content: bytes) -> dict:
    """Parse the BCRA/FMI reserve-liquidity template.

    The liquidity RIN subtracts the monetary authority's loans, deposits,
    repos and other predetermined foreign-currency drains with residual
    maturity of up to one year. It excludes non-deliverable derivatives that
    settle in local currency, the separate central-government column and IMF
    programme-target valuation adjustments.
    """
    with pdfplumber.open(BytesIO(content)) as pdf:
        if len(pdf.pages) < 2:
            raise ValueError("Reserve-liquidity PDF has fewer than two pages")

        first_page_text = pdf.pages[0].extract_text() or ""
        match = re.search(r"(\d{2}/\d{2}/\d{2,4})", first_page_text)
        if not match:
            raise ValueError("Reserve-liquidity PDF has no reporting date")
        date_format = "%d/%m/%Y" if len(match.group(1)) == 10 else "%d/%m/%y"
        period = datetime.strptime(match.group(1), date_format).date()

        assets_table = max(pdf.pages[0].extract_tables(), key=len)
        flows_table = max(pdf.pages[1].extract_tables(), key=len)
        assets_row = next(
            row for row in assets_table
            if (row[0] or "").startswith("A. Activos de reserva oficiales")
        )
        gross_reserves = _first_numeric_cell(assets_row)

        flow_prefixes = (
            "1. Préstamos en moneda extranjera",
            "3. Otros",
        )
        flows = []
        for prefix in flow_prefixes:
            row = next(
                row for row in flows_table
                if (row[0] or "").startswith(prefix)
            )
            flows.append(_first_numeric_cell(row))

    net_flows = sum(flows, Decimal("0"))
    return {
        "periodo": period,
        "reservas_netas_liquidez_millones_usd": gross_reserves + net_flows,
        "drenajes_netos_corto_plazo_millones_usd": -net_flows,
    }


def fetch_reserve_liquidity(
    start_date: date,
    *,
    session=requests,
) -> list[dict]:
    """Fetch monthly BCRA/FMI reserve-liquidity templates."""
    response = session.get(RESERVE_LIQUIDITY_INDEX_URL, timeout=45)
    response.raise_for_status()
    items = response.json().get("data", {}).get("items", [])
    rows = []

    for item in reversed(items):
        url = urljoin(BCRA_SITE, item.get("url", ""))
        filename_match = re.search(r"temp(\d{2})(\d{2})\.pdf", url, re.I)
        if not filename_match:
            continue
        month, short_year = map(int, filename_match.groups())
        current_short_year = date.today().year % 100
        year = (
            2000 + short_year
            if short_year <= current_short_year
            else 1900 + short_year
        )
        approximate_period = date(year, month, 1)
        if approximate_period < start_date.replace(day=1):
            continue

        pdf_response = session.get(url, timeout=60)
        pdf_response.raise_for_status()
        row = parse_reserve_liquidity_pdf(pdf_response.content)
        if row["periodo"] >= start_date:
            rows.append(row)

    LOGGER.info("Fetched %s monthly reserve-liquidity periods", len(rows))
    return rows


def _latest_bank_report_workbook(*, session=requests) -> bytes:
    response = session.get(BANK_REPORT_INDEX_URL, timeout=45)
    response.raise_for_status()
    publications = (
        response.json().get("data", {}).get("publicaciones", [])
    )
    if not publications:
        raise ValueError("BCRA bank-report index returned no publications")

    report_url = publications[0].get("url")
    report = session.get(report_url, timeout=45)
    report.raise_for_status()
    workbook_match = re.search(
        r'href=["\']([^"\']*informe-bancos-serie[^"\']*\.xlsx)["\']',
        report.text,
        re.I,
    )
    if not workbook_match:
        raise ValueError("Latest BCRA bank report has no data-series workbook")

    workbook = session.get(
        urljoin(report_url, workbook_match.group(1)),
        timeout=60,
    )
    workbook.raise_for_status()
    return workbook.content


def fetch_credit_quality(
    start_date: date,
    *,
    session=requests,
) -> list[dict]:
    """Fetch monthly private-credit delinquency ratios from BCRA."""
    workbook = load_workbook(
        BytesIO(_latest_bank_report_workbook(session=session)),
        read_only=True,
        data_only=True,
    )
    sheet = workbook["8"]
    rows = []

    for values in sheet.iter_rows(values_only=True):
        raw_period = values[0]
        if isinstance(raw_period, datetime):
            period = raw_period.date()
        elif isinstance(raw_period, date):
            period = raw_period
        else:
            continue
        if period < start_date or values[1] is None:
            continue
        rows.append({
            "periodo": period,
            "morosidad_sector_privado_porcentaje": Decimal(str(values[1])),
            "morosidad_empresas_porcentaje": (
                Decimal(str(values[6])) if values[6] is not None else None
            ),
            "morosidad_familias_porcentaje": (
                Decimal(str(values[7])) if values[7] is not None else None
            ),
        })

    workbook.close()
    LOGGER.info("Fetched %s monthly credit-quality periods", len(rows))
    return rows


def get_start_date(db: DoltDBManager, days_back: int) -> date:
    if days_back <= 0:
        raise ValueError("days_back must be greater than zero")

    result = db.query(
        f"SELECT MAX(periodo) AS latest_period FROM {TABLE_NAME}"
    )
    latest = result[0]["latest_period"] if result else None

    if latest is None:
        configured = os.getenv("FINANCIAL_START_DATE")
        return (
            date.fromisoformat(configured)
            if configured
            else DEFAULT_START_DATE
        )

    if isinstance(latest, datetime):
        latest = latest.date()
    elif isinstance(latest, str):
        latest = date.fromisoformat(latest)

    return min(latest, date.today() - timedelta(days=days_back))


def needs_daily_backfill(db: DoltDBManager) -> bool:
    expressions = ", ".join(
        f"MIN(CASE WHEN {column} IS NOT NULL THEN periodo END) AS c{index}"
        for index, column in enumerate(BACKFILL_COLUMNS)
    )
    result = db.query(f"SELECT {expressions} FROM {TABLE_NAME}")
    if not result:
        return True
    latest_acceptable_start = DEFAULT_START_DATE + timedelta(days=7)
    for value in result[0].values():
        if value is None:
            return True
        if isinstance(value, datetime):
            value = value.date()
        elif isinstance(value, str):
            value = date.fromisoformat(value)
        if value > latest_acceptable_start:
            return True
    return False


def get_supplemental_start_date(
    db: DoltDBManager,
    column: str,
    days_back: int = 62,
) -> date:
    result = db.query(
        f"SELECT MAX(periodo) AS latest_period FROM {TABLE_NAME} "
        f"WHERE {column} IS NOT NULL"
    )
    latest = result[0]["latest_period"] if result else None
    if latest is None:
        return DEFAULT_START_DATE
    if isinstance(latest, datetime):
        latest = latest.date()
    elif isinstance(latest, str):
        latest = date.fromisoformat(latest)
    return latest - timedelta(days=days_back)


def upsert_financial_sector(db: DoltDBManager, rows: list[dict]) -> None:
    if not rows:
        LOGGER.info("No financial-sector observations to store")
        return

    value_columns = list(FINANCIAL_SERIES)
    columns = ["periodo", *value_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column}=VALUES({column})" for column in value_columns
    )
    sql = (
        f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    for row in rows:
        db.query(sql, tuple(row[column] for column in columns))

    LOGGER.info("Stored %s financial-sector dates", len(rows))


def upsert_monthly_balance(db: DoltDBManager, rows: list[dict]) -> None:
    if not rows:
        LOGGER.info("No BCRA balance observations to store")
        return

    value_columns = list(MONTHLY_BALANCE_SERIES)
    columns = ["periodo", *value_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column}=VALUES({column})" for column in value_columns
    )
    sql = (
        f"INSERT INTO {BALANCE_TABLE_NAME} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    for row in rows:
        db.query(sql, tuple(row[column] for column in columns))

    LOGGER.info("Stored %s monthly BCRA balance periods", len(rows))


def upsert_supplemental_rows(
    db: DoltDBManager,
    rows: list[dict],
    value_columns: tuple[str, ...],
    label: str,
) -> None:
    """Upsert sparse monthly fields without clearing daily observations."""
    if not rows:
        LOGGER.info("No %s observations to store", label)
        return

    columns = ["periodo", *value_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column}=VALUES({column})" for column in value_columns
    )
    sql = (
        f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    for row in rows:
        db.query(sql, tuple(row.get(column) for column in columns))

    LOGGER.info("Stored %s %s periods", len(rows), label)


def main() -> None:
    days_back = int(os.getenv("FINANCIAL_DAYS_BACK", DEFAULT_DAYS_BACK))
    db = DoltDBManager()

    try:
        db.connect()
        ensure_tables(db)
        ensure_financial_columns(db)
        start_date = (
            DEFAULT_START_DATE
            if needs_daily_backfill(db)
            else get_start_date(db, days_back)
        )
        rows = fetch_financial_sector(start_date, date.today())
        upsert_financial_sector(db, rows)

        liquidity_start = get_supplemental_start_date(
            db,
            "reservas_netas_liquidez_millones_usd",
        )
        liquidity_rows = fetch_reserve_liquidity(liquidity_start)
        upsert_supplemental_rows(
            db,
            liquidity_rows,
            (
                "reservas_netas_liquidez_millones_usd",
                "drenajes_netos_corto_plazo_millones_usd",
            ),
            "reserve-liquidity",
        )

        credit_quality_rows = fetch_credit_quality(DEFAULT_START_DATE)
        upsert_supplemental_rows(
            db,
            credit_quality_rows,
            (
                "morosidad_sector_privado_porcentaje",
                "morosidad_empresas_porcentaje",
                "morosidad_familias_porcentaje",
            ),
            "credit-quality",
        )
        balance_rows = fetch_monthly_balance(DEFAULT_START_DATE)
        upsert_monthly_balance(db, balance_rows)
        for table_name in TABLE_SCHEMAS:
            db.dolt_add(table_name)
        result = db.dolt_commit(
            "Update Argentina financial-sector data - "
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
