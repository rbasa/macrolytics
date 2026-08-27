#!/usr/bin/env python3
"""Load Argentina's official monthly AIF statement and fixed IMIG tax series."""

import logging
import os
import re
import sys
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)
TABLE_NAME = "fiscal_argentina"
AIF_START_YEAR = 2017
LAST_PERIODS = int(os.getenv("FISCAL_LAST_PERIODS", "6"))

# `www.economia.gob.ar` currently presents an expired leaf certificate and
# redirects to this official Ministry of Economy host. Using the canonical
# target avoids weakening TLS while keeping the same ONP-published workbooks.
ONP_PAGE_URL = "https://www.mecon.gob.ar/onp/ejecucion/{year}"
SERIES_URL = "https://apis.datos.gob.ar/series/api/series"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Macrolytics/1.0)"}
MAX_SOURCE_LAG_MONTHS = 2


class ONPStructureError(RuntimeError):
    """The official ONP page responded but no longer has the expected shape."""


def make_session():
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session


ONP_SESSION = make_session()


def get_onp_response(url, timeout=60):
    """Fetch one ONP resource with normal CA and hostname validation."""
    return ONP_SESSION.get(url, timeout=timeout)


# Fixed official IMIG IDs. Never replace these with fuzzy metadata matching.
TAX_SERIES = {
    "ingresos_tributarios_iva": "452.2_IVA_NETO_RROS_0_T_19_67",
    "ingresos_tributarios_ganancias": "452.2_GANANCIASIAS_0_T_9_51",
    "ingresos_tributarios_debitos_creditos": "452.2_DEBITOS_CRTOS_0_T_16_22",
    "ingresos_tributarios_bienes_personales": "452.2_BIENES_PERLES_0_T_17_26",
    "ingresos_tributarios_combustibles": "452.2_COMBUSTIBLLES_0_T_12_97",
    "ingresos_tributarios_derechos_exportacion": "452.2_DERECHOS_EION_0_T_20_42",
    "ingresos_tributarios_derechos_importacion": "452.2_DERECHOS_IION_0_T_20_60",
    "ingresos_tributarios_impuestos_internos": "452.2_IMPUESTOS_NOS_0_T_18_87",
    "ingresos_tributarios_resto": "452.2_RESTO_TRIBIOS_0_T_17_0",
}

# IMIG expenditure detail used by the official primary-spending summary.
IMIG_EXPENSE_SERIES = {
    "imig_gasto_funcionamiento_salarios": "452.2_SALARIOSIOS_0_T_8_22",
    "imig_gasto_funcionamiento_otros": "452.2_OTROS_GASTNTO_0_T_27_55",
    "imig_gasto_prestaciones_jubilaciones": "452.2_JUBILACIONVAS_0_T_36_18",
    "imig_gasto_prestaciones_pensiones_no_contributivas": "452.2_PENSIONES_VAS_0_T_26_164",
    "imig_gasto_prestaciones_asignaciones": "452.2_ASIGNACIONIJO_0_T_26_67",
    "imig_gasto_prestaciones_otros_programas": "452.2_OTROS_PROGMAS_0_T_15_11",
    "imig_gasto_prestaciones_inssjp": "452.2_PRESTACIONSJP_0_T_19_86",
    "imig_gasto_subsidios_energia": "452.2_ENERGIAGIA_0_T_7_56",
    "imig_gasto_subsidios_transporte": "452.2_TRANSPORTERTE_0_T_10_32",
    "imig_gasto_subsidios_otras_funciones": "452.2_OTRAS_FUNCNES_0_T_15_25",
    "imig_gasto_provincias_desarrollo_social": "452.2_TRANSFERENIAL_0_T_54_58",
    "imig_gasto_provincias_educacion": "452.2_TRANSFERENION_0_T_46_94",
    "imig_gasto_provincias_salud": "452.2_TRANSFERENLUD_0_T_42_88",
    "imig_gasto_provincias_seguridad_social": "452.2_TRANSFERENIAL_0_T_53_66",
    "imig_gasto_provincias_otras": "452.2_TRANSFERENRAS_0_T_42_55",
    "imig_gasto_transferencias_universidades": "452.2_OTROS_CORRDES_0_T_45_79",
    "imig_gasto_otros_deficit_empresas_publicas": "452.2_OTROS_CORRCAS_0_T_52_16",
    "imig_gasto_otros_resto": "452.2_OTROS_CORRSTO_0_T_22_78",
}

IMIG_SERIES = {**TAX_SERIES, **IMIG_EXPENSE_SERIES}

# Rows must remain in official workbook order to disambiguate repeated labels.
# Values always come from the published consolidated TOTAL; no identities are built.
AIF_ROWS = [
    ("ingresos_corrientes_total", ("INGRESOS CORRIENTES",)),
    ("ingresos_tributarios_total", ("INGRESOS IMPOSITIVOS", "INGRESOS TRIBUTARIOS")),
    ("ingresos_aportes_contribuciones_seguridad_social",
     ("APORTES Y CONTRIB. A LA SEG. SOCIAL", "APORTES Y CONTRIB A LA SEG SOCIAL",
      "CONTRIBUCIONES A LA SEG SOCIAL")),
    ("ingresos_no_tributarios", ("INGRESOS NO IMPOSITIVOS", "INGRESOS NO TRIBUTARIOS")),
    ("ingresos_ventas_bienes_servicios_adm_publica",
     ("VENTAS DE BS.Y SERV.DE LAS ADM.PUB.", "VENTAS DE BS Y SERV DE LAS ADM PUB")),
    ("ingresos_operacion", ("INGRESOS DE OPERACION",)),
    ("ingresos_rentas_propiedad_netas",
     ("RENTAS DE LA PROPIEDAD NETAS", "RENTAS DE LA PROPIEDAD")),
    ("ingresos_transferencias_corrientes", ("TRANSFERENCIAS CORRIENTES",)),
    ("ingresos_otros", ("OTROS INGRESOS",)),
    ("ingresos_superavit_operativo_empresas_publicas",
     ("SUPERAVIT OPERATIVO EMPRESAS PUB.", "SUPERAVIT OPERATIVO EMPRESAS PUB")),
    ("gastos_corrientes_total", ("GASTOS CORRIENTES",)),
    ("gastos_consumo_operacion_total", ("GASTOS DE CONSUMO Y OPERACION",)),
    ("gastos_consumo_operacion_remuneraciones", ("REMUNERACIONES",)),
    ("gastos_consumo_operacion_bienes_servicios", ("BIENES Y SERVICIOS",)),
    ("gastos_consumo_operacion_otros", ("OTROS GASTOS",)),
    ("gastos_intereses_otras_rentas_total",
     ("INTERESES Y OTRAS RENTAS DE LA PROP.", "INTERESES Y OTRAS RENTAS DE LA PROP")),
    ("gastos_intereses_netos", ("INTERESES NETOS", "INTERESES")),
    ("gastos_otras_rentas", ("OTRAS RENTAS",)),
    ("gastos_prestaciones_seguridad_social", ("PRESTACIONES DE LA SEGURIDAD SOCIAL",)),
    ("gastos_otros_corrientes", ("OTROS GASTOS CORRIENTES",)),
    ("gastos_transferencias_corrientes_total", ("TRANSFERENCIAS CORRIENTES",)),
    ("gastos_transferencias_sector_privado", ("AL SECTOR PRIVADO",)),
    ("gastos_transferencias_sector_publico_total", ("AL SECTOR PUBLICO",)),
    ("gastos_transferencias_provincias_caba", ("PROVINCIAS Y CABA", "PROVINCIAS Y C.A.B.A.")),
    ("gastos_transferencias_universidades", ("UNIVERSIDADES",)),
    ("gastos_transferencias_sector_publico_otras", ("OTRAS",)),
    ("gastos_transferencias_sector_externo", ("AL SECTOR EXTERNO",)),
    ("gastos_otros", ("OTROS GASTOS",)),
    ("gastos_deficit_operativo_empresas_publicas",
     ("DEFICIT OPERATIVO EMPRESAS PUB.", "DEFICIT OPERATIVO EMPRESAS PUB")),
    ("resultado_economico", ("RESULT.ECON.: AHORRO/DESAHORRO", "RESULT ECON AHORRO DESAHORRO")),
    ("recursos_capital", ("RECURSOS DE CAPITAL",)),
    ("gastos_capital_total", ("GASTOS DE CAPITAL",)),
    ("gastos_capital_inversion_real_directa", ("INVERSION REAL DIRECTA",)),
    ("gastos_capital_transferencias_total", ("TRANSFERENCIAS DE CAPITAL",)),
    ("gastos_capital_transferencias_provincias_caba",
     ("A PROVINCIAS Y CABA", "A PROVINCIAS Y C.A.B.A.")),
    ("gastos_capital_transferencias_otras", ("OTRAS",)),
    ("gastos_capital_inversion_financiera_total", ("INVERSION FINANCIERA",)),
    ("gastos_capital_inversion_financiera_provincias_caba",
     ("A PROVINCIAS Y CABA", "A PROVINCIAS Y C.A.B.A.")),
    ("gastos_capital_inversion_financiera_resto", ("RESTO",)),
    ("ingresos_antes_figurativos", ("INGRESOS ANTES DE FIGURAT",)),
    ("gastos_antes_figurativos", ("GASTOS ANTES DE FIGURAT",)),
    ("resultado_financiero_antes_figurativos", ("RESULT.FINANC.ANTES DE FIGURAT",)),
    ("contribuciones_figurativas_total", ("CONTRIBUCIONES FIGURATIVAS",)),
    ("contribuciones_figurativas_tesoro_nacional", ("DEL TESORO NACIONAL",)),
    ("contribuciones_figurativas_recursos_afectados", ("DE RECURSOS AFECTADOS",)),
    ("contribuciones_figurativas_organismos_descentralizados", ("DE ORGANISMOS DESCENTRALIZADOS",)),
    ("contribuciones_figurativas_seguridad_social",
     ("DE INSTITUCIONES DE SEGURIDAD SOCIAL", "DE INSTITUCIONES DE LA SEGURIDAD SOCIAL")),
    ("contribuciones_figurativas_pami_fondos_otros",
     ("DE PAMI, FDOS. FIDUCIARIOS Y OTROS", "DE PAMI FDOS FIDUCIARIOS Y OTROS")),
    ("gastos_figurativos", ("GASTOS FIGURATIVOS",)),
    ("ingresos_despues_figurativos", ("INGRESOS DESPUES DE FIGURAT",)),
    ("gastos_primarios_despues_figurativos", ("GASTOS PRIMARIOS DESPUES DE FIGURAT",)),
    ("gastos_despues_figurativos", ("GASTOS DESPUES DE FIGURAT",)),
    ("resultado_primario", ("RESULTADO PRIMARIO", "SUPERAVIT PRIMARIO")),
    ("resultado_financiero", ("RESULTADO FINANCIERO",)),
    ("rentas_percibidas_bcra", ("RENTAS PERCIBIDAS DEL BCRA",)),
    ("rentas_publicas_fgs_otros",
     ("RENTAS PUBL. PERCIBIDAS POR EL FGS Y OTROS", "RENTAS PUBLICAS PERCIBIDAS POR EL FGS Y OTROS")),
    ("intereses_pagados_intrasector_publico",
     ("INTERESES PAGADOS INTRA-SECTOR PUBLICO", "INTERESES PAGADOS INTRA SECTOR PUBLICO")),
]

AIF_COLUMNS = [column for column, _ in AIF_ROWS]
VALUE_COLUMNS = [*AIF_COLUMNS, *IMIG_SERIES]
MONTHS = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}


def normalize_text(value):
    """Normalize a known HTML/Excel label; never used to discover series."""
    if value is None or not str(value).strip():
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip())
    text = "".join(char for char in text if not unicodedata.combining(char)).upper()
    text = re.sub(r"^\s*[IVXLCDM]+\)\s*", "", text)
    text = re.sub(r"\(\s*\d+\s*\)", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", text)).strip()


def row_matches(actual, aliases):
    actual = normalize_text(actual)
    return any(
        actual == expected or actual.startswith(expected + " ")
        for expected in map(normalize_text, aliases)
    )


def parse_amount(value):
    """Parse an Excel number or a number formatted in English/Spanish style."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = re.sub(r"\s+", "", str(value).strip())
    if text in {"", "-", "–", "—"}:
        return 0.0
    if "," in text and "." in text:
        if text.rfind(".") > text.rfind(","):
            text = text.replace(",", "")
        else:
            text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        parts = text.split(",")
        text = text.replace(",", "." if len(parts) == 2 and len(parts[1]) <= 2 else "")
    try:
        return float(text)
    except ValueError as exc:
        raise RuntimeError(f"Could not parse fiscal amount: {value!r}") from exc


class AIFPageParser(HTMLParser):
    """Extract monthly Excel links only from the AIF section of an ONP page."""

    def __init__(self):
        super().__init__()
        self.in_aif = False
        self.finished = False
        self.pending_month = None
        self.pending_excel_href = None
        self.current_href = None
        self.links = {}

    def store_pending_link(self):
        if self.pending_month is None or self.pending_excel_href is None:
            return
        self.links.setdefault(self.pending_month, self.pending_excel_href)
        self.pending_month = self.pending_excel_href = None

    def handle_starttag(self, tag, attrs):
        if not self.finished and tag.lower() == "a":
            self.current_href = dict(attrs).get("href")

    def handle_data(self, data):
        if self.finished:
            return
        text = normalize_text(data)
        if not self.in_aif and "CUENTA AIF SEC PUBLICO NACIONAL" in text:
            self.in_aif = True
        elif self.in_aif and "EJECUCION DIVISAS" in text:
            self.finished = True
        elif self.in_aif and text in MONTHS:
            self.pending_month = MONTHS[text]
            self.store_pending_link()

    def handle_endtag(self, tag):
        if tag.lower() != "a":
            return
        if self.in_aif and not self.finished and self.current_href:
            if urlparse(self.current_href).path.lower().endswith((".xls", ".xlsx")):
                self.pending_excel_href = self.current_href
                self.store_pending_link()
        self.current_href = None


def fetch_aif_links(year):
    page_url = ONP_PAGE_URL.format(year=year)
    LOGGER.info("Fetching ONP AIF index for %s: %s", year, page_url)
    try:
        response = get_onp_response(page_url)
    except requests.exceptions.SSLError as exc:
        LOGGER.error("ONP TLS validation failed for %s: %s", page_url, exc)
        raise

    if response.status_code == 404:
        LOGGER.warning("Skipping unavailable ONP year %s: %s", year, page_url)
        return []
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        LOGGER.error(
            "ONP HTTP error for year %s at %s: %s",
            year,
            page_url,
            exc,
        )
        raise

    if not response.encoding:
        response.encoding = response.apparent_encoding
    if not response.text.strip():
        raise ONPStructureError(
            f"ONP returned an empty execution page for {year}: {page_url}"
        )
    parser = AIFPageParser()
    parser.feed(response.text)
    links = [
        {
            "period": date(year, month, 1),
            "url": urljoin(response.url or page_url, href),
        }
        for month, href in parser.links.items()
    ]
    if not links:
        raise ONPStructureError(
            "ONP execution page structure changed or has no monthly AIF "
            f"workbooks for {year}: {page_url}"
        )
    LOGGER.info("Found %s monthly ONP AIF workbooks for %s", len(links), year)
    return links


def month_distance(later, earlier):
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def collect_aif_links(last_periods):
    """Return the latest workbooks, scanning all years only for backfills."""
    if last_periods <= 0:
        raise ValueError("FISCAL_LAST_PERIODS must be positive")
    current_year = date.today().year
    start_year = (
        AIF_START_YEAR
        if last_periods >= 100
        else max(AIF_START_YEAR, current_year - 1)
    )
    links = []
    omitted_years = []
    for year in range(start_year, current_year + 1):
        year_links = fetch_aif_links(year)
        if not year_links:
            omitted_years.append(year)
        links.extend(year_links)

    if not links:
        raise RuntimeError("No monthly AIF Excel files were found")
    if last_periods >= 100 and omitted_years:
        raise RuntimeError(
            "Cannot safely backfill fiscal history because ONP years are "
            f"unavailable: {', '.join(map(str, omitted_years))}"
        )

    selected = sorted(links, key=lambda item: item["period"])[-last_periods:]
    if last_periods < 100 and len(selected) < last_periods:
        raise RuntimeError(
            f"ONP supplied only {len(selected)} of {last_periods} required "
            "monthly AIF workbooks"
        )

    latest_period = selected[-1]["period"]
    lag = month_distance(date.today(), latest_period)
    if lag > MAX_SOURCE_LAG_MONTHS:
        raise RuntimeError(
            "Latest ONP AIF workbook is stale: "
            f"{latest_period:%Y-%m} ({lag} months behind current month)"
        )
    if omitted_years:
        LOGGER.warning(
            "Omitted ONP years %s; selected range remains complete and fresh",
            ", ".join(map(str, omitted_years)),
        )

    LOGGER.info(
        "Selected %s ONP AIF periods from %s through %s",
        len(selected),
        selected[0]["period"],
        selected[-1]["period"],
    )
    return selected


def find_sheet_layout(frame):
    """Locate CONCEPTO and the rightmost (consolidated SPN) TOTAL column."""
    concept = next(
        (
            (row, column)
            for row in range(min(25, len(frame)))
            for column in range(frame.shape[1])
            if normalize_text(frame.iat[row, column]) == "CONCEPTO"
        ),
        None,
    )
    if concept is None:
        return None
    header_row, concept_column = concept
    total_columns = [
        column
        for row in range(header_row, min(header_row + 4, len(frame)))
        for column in range(frame.shape[1])
        if normalize_text(frame.iat[row, column]).replace(" ", "") == "TOTAL"
    ]
    if not total_columns:
        return None
    return {
        "header_row": header_row,
        "concept_column": concept_column,
        "total_column": max(total_columns),
    }


def read_aif_workbook(content):
    excel = pd.ExcelFile(BytesIO(content))
    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(excel, sheet_name=sheet_name, header=None)
        layout = find_sheet_layout(frame)
        if layout:
            return frame, layout
    raise RuntimeError("Could not locate AIF table in workbook")


def extract_aif_values(frame, layout):
    """Read every required row in order from the published TOTAL column."""
    cursor = layout["header_row"] + 1
    values = {}
    for column, aliases in AIF_ROWS:
        found_row = next(
            (
                row
                for row in range(cursor, len(frame))
                if row_matches(frame.iat[row, layout["concept_column"]], aliases)
            ),
            None,
        )
        if found_row is None:
            raise RuntimeError(
                "Official AIF workbook structure changed. "
                f"Could not find row for {column}: {' / '.join(aliases)}"
            )
        values[column] = parse_amount(frame.iat[found_row, layout["total_column"]])
        cursor = found_row + 1
    return values


def fetch_aif_period(period, url):
    LOGGER.info("Fetching ONP AIF workbook for %s: %s", period, url)
    try:
        response = get_onp_response(url)
        response.raise_for_status()
    except requests.exceptions.SSLError as exc:
        LOGGER.error("ONP TLS validation failed for workbook %s: %s", url, exc)
        raise
    except requests.exceptions.HTTPError as exc:
        LOGGER.error("ONP HTTP error for workbook %s: %s", url, exc)
        raise
    if not response.content:
        raise RuntimeError(f"ONP returned an empty AIF workbook for {period}: {url}")
    frame, layout = read_aif_workbook(response.content)
    return {"period": period, **extract_aif_values(frame, layout)}


def fetch_aif_data():
    rows = [fetch_aif_period(**item) for item in collect_aif_links(LAST_PERIODS)]
    frame = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
    LOGGER.info(
        "Fetched %s AIF periods from %s through %s",
        len(frame), frame["period"].min(), frame["period"].max(),
    )
    return frame


def fetch_imig_data():
    response = requests.get(
        SERIES_URL,
        params={
            "ids": ",".join(IMIG_SERIES.values()),
            "last": LAST_PERIODS,
            "metadata": "none",
        },
        headers=REQUEST_HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json().get("data", [])
    if not data:
        raise RuntimeError("Datos Argentina returned no IMIG tax observations")
    frame = pd.DataFrame(data, columns=["period", *IMIG_SERIES])
    frame["period"] = pd.to_datetime(frame["period"], errors="raise").dt.date
    frame = frame.sort_values("period").reset_index(drop=True)
    LOGGER.info(
        "Fetched %s IMIG periods from %s through %s",
        len(frame), frame["period"].min(), frame["period"].max(),
    )
    return frame


def fetch_fiscal_data():
    """Use AIF as calendar; unavailable tax observations remain NULL."""
    fiscal = (
        fetch_aif_data()
        .merge(
            fetch_imig_data(),
            on="period",
            how="left",
            validate="one_to_one",
        )
        .sort_values("period")
        .reset_index(drop=True)
    )
    if fiscal.empty:
        raise RuntimeError("Fiscal sources returned no valid observations")
    if fiscal["period"].isna().any() or fiscal["period"].duplicated().any():
        raise RuntimeError("Fiscal sources produced invalid or duplicate periods")
    return fiscal


def clean_value(value):
    return None if pd.isna(value) else float(value)


def upsert_fiscal(db, fiscal):
    if fiscal.empty:
        raise ValueError("Cannot upsert an empty fiscal dataset")
    if fiscal["period"].duplicated().any():
        raise ValueError("Cannot upsert duplicate fiscal periods")

    columns = ["period", *VALUE_COLUMNS]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{column}=VALUES({column})" for column in VALUE_COLUMNS)
    sql = (
        f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}
    for row in fiscal.to_dict("records"):
        result = db.query(
            sql,
            (
                row["period"],
                *(clean_value(row.get(column)) for column in VALUE_COLUMNS),
            ),
        )
        affected = result[0].get("affected_rows", 0) if result else 0
        if affected == 1:
            counts["inserted"] += 1
        elif affected == 2:
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    LOGGER.info(
        "Stored %s fiscal periods: %s inserted, %s updated, %s unchanged",
        len(fiscal),
        counts["inserted"],
        counts["updated"],
        counts["unchanged"],
    )
    return counts


def main():
    fiscal = fetch_fiscal_data()
    db = DoltDBManager()
    try:
        db.connect()
        upsert_fiscal(db, fiscal)
        db.dolt_add(TABLE_NAME)
        result = db.dolt_commit(f"Update Argentina fiscal data - {datetime.now():%Y-%m-%d %H:%M:%S}")
        LOGGER.info("Dolt commit result: %s", result)
    finally:
        db.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    main()
