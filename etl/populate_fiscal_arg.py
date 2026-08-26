#!/usr/bin/env python3
"""Load Argentina's official monthly AIF statement and fixed IMIG tax series."""

import logging
import os
import re
import ssl
import sys
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)
TABLE_NAME = "fiscal_argentina"
AIF_START_YEAR = 2017
LAST_PERIODS = int(os.getenv("FISCAL_LAST_PERIODS", "6"))

ONP_PAGE_URL = "https://www.economia.gob.ar/onp/ejecucion/{year}"
SERIES_URL = "https://apis.datos.gob.ar/series/api/series"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Macrolytics/1.0)"}
ONP_CA_CERT_PATH = os.path.join(
    os.path.dirname(__file__),
    "certs",
    "sectigo_public_server_authentication_ca_dv_r36.crt",
)

# ONP's leaf certificate expired on 2026-08-15. The fallback remains authenticated
# by its exact fingerprint and is used only while the normally verified request fails
# specifically because of that expiry. Once ONP renews it, normal TLS wins again.
ONP_EXPIRED_CERT_SHA256 = (
    "7A:6C:38:EB:DE:47:23:77:27:E3:85:59:5B:81:66:58:"
    "EA:B9:6A:20:7B:71:DB:B9:3D:A5:84:EB:D6:1A:46:D2"
)


class ONPPinnedTLSAdapter(HTTPAdapter):
    """Accept only the known expired ONP certificate in the fallback session."""

    def __init__(self, fingerprint=ONP_EXPIRED_CERT_SHA256):
        self.fingerprint = fingerprint
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        pool_kwargs.update(
            ssl_context=context,
            assert_fingerprint=self.fingerprint,
        )
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    def cert_verify(self, connection, url, verify, cert):
        # Let urllib3 verify the fingerprint before Requests rejects the expiry.
        super().cert_verify(connection, url, False, cert)


def make_session(adapter=None):
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    if adapter:
        session.mount("https://www.economia.gob.ar/", adapter)
    return session


ONP_SESSION = make_session()
ONP_PINNED_SESSION = make_session(ONPPinnedTLSAdapter())
_ONP_PINNED_FALLBACK_LOGGED = False


def get_onp_response(url, timeout=60):
    """Fetch ONP with normal TLS, or the exact pinned expired certificate."""
    global _ONP_PINNED_FALLBACK_LOGGED

    try:
        # ONP omits this intermediate CA from its TLS chain.
        return ONP_SESSION.get(url, timeout=timeout, verify=ONP_CA_CERT_PATH)
    except requests.exceptions.SSLError as exc:
        if "certificate has expired" not in str(exc).lower():
            raise
        if not _ONP_PINNED_FALLBACK_LOGGED:
            LOGGER.warning("ONP certificate expired; using pinned fingerprint")
            _ONP_PINNED_FALLBACK_LOGGED = True
        return ONP_PINNED_SESSION.get(url, timeout=timeout)


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
    response = get_onp_response(page_url)
    response.raise_for_status()
    if not response.encoding:
        response.encoding = response.apparent_encoding
    parser = AIFPageParser()
    parser.feed(response.text)
    return [
        {"period": date(year, month, 1), "url": urljoin(page_url, href)}
        for month, href in parser.links.items()
    ]


def collect_aif_links(last_periods):
    """Return the latest workbooks, scanning all years only for backfills."""
    if last_periods <= 0:
        raise ValueError("FISCAL_LAST_PERIODS must be positive")
    current_year = date.today().year
    start_year = AIF_START_YEAR if last_periods >= 100 else max(AIF_START_YEAR, current_year - 1)
    links = [
        link
        for year in range(start_year, current_year + 1)
        for link in fetch_aif_links(year)
    ]
    if not links:
        raise RuntimeError("No monthly AIF Excel files were found")
    return sorted(links, key=lambda item: item["period"])[-last_periods:]


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
    response = get_onp_response(url)
    response.raise_for_status()
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
    return (
        fetch_aif_data()
        .merge(fetch_imig_data(), on="period", how="left")
        .sort_values("period")
        .reset_index(drop=True)
    )


def clean_value(value):
    return None if pd.isna(value) else float(value)


def upsert_fiscal(db, fiscal):
    columns = ["period", *VALUE_COLUMNS]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{column}=VALUES({column})" for column in VALUE_COLUMNS)
    sql = (
        f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    for row in fiscal.to_dict("records"):
        db.query(sql, (row["period"], *(clean_value(row.get(column)) for column in VALUE_COLUMNS)))
    LOGGER.info("Stored %s fiscal periods", len(fiscal))


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
