#!/usr/bin/env python3
"""
Populate Argentina fiscal accounts.

Sources
-------
1. Oficina Nacional de Presupuesto (ONP)
   Cuenta Ahorro - Inversión - Financiamiento del
   Sector Público Nacional, Base Caja, mensual.

   The official monthly Excel workbook is used directly so that
   every accounting line stored in fiscal_argentina corresponds
   to the published AIF table. No accounting identities are
   inferred by this ETL.

2. Datos Argentina / IMIG
   Detailed tax revenue components, using fixed official series IDs.

Units
-----
Millions of current Argentine pesos.

First historical load:
    LAST_PERIODS = 1000

Normal update:
    LAST_PERIODS = 6

Usage:
    python etl/populate_fiscal_arg.py
"""

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

# First historical run: 1000
# Normal runs: 6
LAST_PERIODS = 6

AIF_START_YEAR = 2017

ONP_PAGE_URL = (
    "https://www.economia.gob.ar/onp/ejecucion/{year}"
)

SERIES_URL = (
    "https://apis.datos.gob.ar/series/api/series"
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; Macrolytics/1.0)"
    ),
}

ONP_CA_CERT_PATH = os.path.join(
    os.path.dirname(__file__),
    "certs",
    "sectigo_public_server_authentication_ca_dv_r36.crt",
)


class ONPTLSAdapter(HTTPAdapter):
    """
    Complete the certificate chain currently omitted by the ONP server.

    The adapter remains fully verified and is mounted only for ONP URLs.
    Other HTTP clients and the Datos Argentina API keep their default TLS
    configuration.
    """

    def __init__(self, ca_cert_path, *args, **kwargs):
        self.ca_cert_path = ca_cert_path
        super().__init__(*args, **kwargs)

    def init_poolmanager(
        self,
        connections,
        maxsize,
        block=False,
        **pool_kwargs,
    ):
        context = ssl.create_default_context()
        context.load_verify_locations(
            cafile=self.ca_cert_path,
        )
        pool_kwargs["ssl_context"] = context

        super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            **pool_kwargs,
        )


def create_onp_session():
    """Create a verified HTTP session for the ONP website."""
    session = requests.Session()
    session.headers.update(
        REQUEST_HEADERS
    )
    session.mount(
        "https://www.economia.gob.ar/",
        ONPTLSAdapter(ONP_CA_CERT_PATH),
    )
    return session


ONP_SESSION = create_onp_session()


# ------------------------------------------------------------------
# Tax breakdown
# Exact official IMIG series IDs.
# ------------------------------------------------------------------

TAX_SERIES = {
    "ingresos_tributarios_iva":
        "452.2_IVA_NETO_RROS_0_T_19_67",

    "ingresos_tributarios_ganancias":
        "452.2_GANANCIASIAS_0_T_9_51",

    "ingresos_tributarios_debitos_creditos":
        "452.2_DEBITOS_CRTOS_0_T_16_22",

    "ingresos_tributarios_bienes_personales":
        "452.2_BIENES_PERLES_0_T_17_26",

    "ingresos_tributarios_combustibles":
        "452.2_COMBUSTIBLLES_0_T_12_97",

    "ingresos_tributarios_derechos_exportacion":
        "452.2_DERECHOS_EION_0_T_20_42",

    "ingresos_tributarios_derechos_importacion":
        "452.2_DERECHOS_IION_0_T_20_60",

    "ingresos_tributarios_impuestos_internos":
        "452.2_IMPUESTOS_NOS_0_T_18_87",

    "ingresos_tributarios_resto":
        "452.2_RESTO_TRIBIOS_0_T_17_0",
}


# ------------------------------------------------------------------
# AIF rows
#
# IMPORTANT:
# Order matters.
#
# We walk the official Excel from top to bottom. This lets us
# distinguish repeated labels such as:
#   - Transferencias corrientes
#   - Otros gastos
#   - A Provincias y CABA
#
# No accounting totals are calculated here: every value is taken
# directly from the final TOTAL column of the official sheet.
# ------------------------------------------------------------------

AIF_ROWS = [
    # I) Ingresos corrientes
    (
        "ingresos_corrientes_total",
        ("INGRESOS CORRIENTES",),
    ),
    (
        "ingresos_tributarios_total",
        ("INGRESOS IMPOSITIVOS",),
    ),
    (
        "ingresos_aportes_contribuciones_seguridad_social",
        (
            "APORTES Y CONTRIB. A LA SEG. SOCIAL",
            "APORTES Y CONTRIB A LA SEG SOCIAL",
        ),
    ),
    (
        "ingresos_no_tributarios",
        ("INGRESOS NO IMPOSITIVOS",),
    ),
    (
        "ingresos_ventas_bienes_servicios_adm_publica",
        (
            "VENTAS DE BS.Y SERV.DE LAS ADM.PUB.",
            "VENTAS DE BS Y SERV DE LAS ADM PUB",
        ),
    ),
    (
        "ingresos_operacion",
        ("INGRESOS DE OPERACION",),
    ),
    (
        "ingresos_rentas_propiedad_netas",
        ("RENTAS DE LA PROPIEDAD NETAS",),
    ),
    (
        "ingresos_transferencias_corrientes",
        ("TRANSFERENCIAS CORRIENTES",),
    ),
    (
        "ingresos_otros",
        ("OTROS INGRESOS",),
    ),
    (
        "ingresos_superavit_operativo_empresas_publicas",
        (
            "SUPERAVIT OPERATIVO EMPRESAS PUB.",
            "SUPERAVIT OPERATIVO EMPRESAS PUB",
        ),
    ),

    # II) Gastos corrientes
    (
        "gastos_corrientes_total",
        ("GASTOS CORRIENTES",),
    ),
    (
        "gastos_consumo_operacion_total",
        ("GASTOS DE CONSUMO Y OPERACION",),
    ),
    (
        "gastos_consumo_operacion_remuneraciones",
        ("REMUNERACIONES",),
    ),
    (
        "gastos_consumo_operacion_bienes_servicios",
        ("BIENES Y SERVICIOS",),
    ),
    (
        "gastos_consumo_operacion_otros",
        ("OTROS GASTOS",),
    ),
    (
        "gastos_intereses_otras_rentas_total",
        (
            "INTERESES Y OTRAS RENTAS DE LA PROP.",
            "INTERESES Y OTRAS RENTAS DE LA PROP",
        ),
    ),
    (
        "gastos_intereses_netos",
        ("INTERESES NETOS",),
    ),
    (
        "gastos_otras_rentas",
        ("OTRAS RENTAS",),
    ),
    (
        "gastos_prestaciones_seguridad_social",
        ("PRESTACIONES DE LA SEGURIDAD SOCIAL",),
    ),
    (
        "gastos_otros_corrientes",
        ("OTROS GASTOS CORRIENTES",),
    ),
    (
        "gastos_transferencias_corrientes_total",
        ("TRANSFERENCIAS CORRIENTES",),
    ),
    (
        "gastos_transferencias_sector_privado",
        ("AL SECTOR PRIVADO",),
    ),
    (
        "gastos_transferencias_sector_publico_total",
        ("AL SECTOR PUBLICO",),
    ),
    (
        "gastos_transferencias_provincias_caba",
        (
            "PROVINCIAS Y CABA",
            "PROVINCIAS Y C.A.B.A.",
        ),
    ),
    (
        "gastos_transferencias_universidades",
        ("UNIVERSIDADES",),
    ),
    (
        "gastos_transferencias_sector_publico_otras",
        ("OTRAS",),
    ),
    (
        "gastos_transferencias_sector_externo",
        ("AL SECTOR EXTERNO",),
    ),
    (
        "gastos_otros",
        ("OTROS GASTOS",),
    ),
    (
        "gastos_deficit_operativo_empresas_publicas",
        (
            "DEFICIT OPERATIVO EMPRESAS PUB.",
            "DEFICIT OPERATIVO EMPRESAS PUB",
        ),
    ),

    # III) Resultado económico
    (
        "resultado_economico",
        (
            "RESULT.ECON.: AHORRO/DESAHORRO",
            "RESULT ECON AHORRO DESAHORRO",
        ),
    ),

    # IV) Recursos de capital
    (
        "recursos_capital",
        ("RECURSOS DE CAPITAL",),
    ),

    # V) Gastos de capital
    (
        "gastos_capital_total",
        ("GASTOS DE CAPITAL",),
    ),
    (
        "gastos_capital_inversion_real_directa",
        ("INVERSION REAL DIRECTA",),
    ),
    (
        "gastos_capital_transferencias_total",
        ("TRANSFERENCIAS DE CAPITAL",),
    ),
    (
        "gastos_capital_transferencias_provincias_caba",
        (
            "A PROVINCIAS Y CABA",
            "A PROVINCIAS Y C.A.B.A.",
        ),
    ),
    (
        "gastos_capital_transferencias_otras",
        ("OTRAS",),
    ),
    (
        "gastos_capital_inversion_financiera_total",
        ("INVERSION FINANCIERA",),
    ),
    (
        "gastos_capital_inversion_financiera_provincias_caba",
        (
            "A PROVINCIAS Y CABA",
            "A PROVINCIAS Y C.A.B.A.",
        ),
    ),
    (
        "gastos_capital_inversion_financiera_resto",
        ("RESTO",),
    ),

    # VI-VIII
    (
        "ingresos_antes_figurativos",
        ("INGRESOS ANTES DE FIGURAT",),
    ),
    (
        "gastos_antes_figurativos",
        ("GASTOS ANTES DE FIGURAT",),
    ),
    (
        "resultado_financiero_antes_figurativos",
        ("RESULT.FINANC.ANTES DE FIGURAT",),
    ),

    # IX-X
    (
        "contribuciones_figurativas_total",
        ("CONTRIBUCIONES FIGURATIVAS",),
    ),
    (
        "contribuciones_figurativas_tesoro_nacional",
        ("DEL TESORO NACIONAL",),
    ),
    (
        "contribuciones_figurativas_recursos_afectados",
        ("DE RECURSOS AFECTADOS",),
    ),
    (
        "contribuciones_figurativas_organismos_descentralizados",
        ("DE ORGANISMOS DESCENTRALIZADOS",),
    ),
    (
        "contribuciones_figurativas_seguridad_social",
        (
            "DE INSTITUCIONES DE SEGURIDAD SOCIAL",
            "DE INSTITUCIONES DE LA SEGURIDAD SOCIAL",
        ),
    ),
    (
        "contribuciones_figurativas_pami_fondos_otros",
        (
            "DE PAMI, FDOS. FIDUCIARIOS Y OTROS",
            "DE PAMI FDOS FIDUCIARIOS Y OTROS",
        ),
    ),
    (
        "gastos_figurativos",
        ("GASTOS FIGURATIVOS",),
    ),

    # XI-XV
    (
        "ingresos_despues_figurativos",
        ("INGRESOS DESPUES DE FIGURAT",),
    ),
    (
        "gastos_primarios_despues_figurativos",
        ("GASTOS PRIMARIOS DESPUES DE FIGURAT",),
    ),
    (
        "gastos_despues_figurativos",
        ("GASTOS DESPUES DE FIGURAT",),
    ),
    (
        "resultado_primario",
        ("RESULTADO PRIMARIO",),
    ),
    (
        "resultado_financiero",
        ("RESULTADO FINANCIERO",),
    ),

    # Memo items
    (
        "rentas_percibidas_bcra",
        ("RENTAS PERCIBIDAS DEL BCRA",),
    ),
    (
        "rentas_publicas_fgs_otros",
        (
            "RENTAS PUBL. PERCIBIDAS POR EL FGS Y OTROS",
            "RENTAS PUBLICAS PERCIBIDAS POR EL FGS Y OTROS",
        ),
    ),
    (
        "intereses_pagados_intrasector_publico",
        (
            "INTERESES PAGADOS INTRA-SECTOR PUBLICO",
            "INTERESES PAGADOS INTRA SECTOR PUBLICO",
        ),
    ),
]


AIF_COLUMNS = [
    column
    for column, _ in AIF_ROWS
]

VALUE_COLUMNS = [
    *AIF_COLUMNS,
    *TAX_SERIES.keys(),
]


MONTHS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "SETIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}


def normalize_text(value):
    """
    Normalize labels from the official Excel / HTML.

    This is only used to identify known row labels.
    It is NOT used to resolve statistical series.
    """
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )

    value = value.upper()

    # Remove leading Roman-number section markers:
    # I), II), III), ...
    value = re.sub(
        r"^\s*[IVXLCDM]+\)\s*",
        "",
        value,
    )

    # Remove numeric footnotes:
    # (1), (2), (3), ...
    value = re.sub(
        r"\(\s*\d+\s*\)",
        " ",
        value,
    )

    value = re.sub(
        r"[^A-Z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def row_matches(
    actual,
    aliases,
):
    """
    Match an Excel label against an explicit set of known aliases.

    Prefix matching is allowed because several published rows include
    accounting references after the label, e.g.:
        RESULTADO PRIMARIO (XI-XII)

    The ordered AIF_ROWS definition prevents repeated labels from
    being confused with one another.
    """
    actual = normalize_text(actual)

    for alias in aliases:
        expected = normalize_text(alias)

        if actual == expected:
            return True

        if actual.startswith(
            expected + " "
        ):
            return True

    return False


def parse_amount(value):
    """
    Convert one published Excel amount to float.

    Excel numeric cells normally arrive already as int/float.
    String handling is included for older workbook formats.
    """
    if pd.isna(value):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    text = str(value).strip()

    if text in {
        "",
        "-",
        "–",
        "—",
    }:
        return 0.0

    text = text.replace(
        "\xa0",
        "",
    ).replace(
        " ",
        "",
    )

    # Format such as:
    # 5,247,480.8
    if (
        "," in text
        and "." in text
        and text.rfind(".") > text.rfind(",")
    ):
        text = text.replace(
            ",",
            "",
        )

    # Format such as:
    # 5.247.480,8
    elif (
        "," in text
        and "." in text
        and text.rfind(",") > text.rfind(".")
    ):
        text = text.replace(
            ".",
            "",
        ).replace(
            ",",
            ".",
        )

    elif "," in text:
        parts = text.split(",")

        if (
            len(parts) == 2
            and len(parts[1]) <= 2
        ):
            text = text.replace(
                ",",
                ".",
            )
        else:
            text = text.replace(
                ",",
                "",
            )

    try:
        return float(text)

    except ValueError as exc:
        raise RuntimeError(
            f"Could not parse fiscal amount: {value!r}"
        ) from exc


class AIFPageParser(HTMLParser):
    """
    Extract monthly Excel links from the AIF section of an ONP page.

    The ONP page also contains other execution reports. We begin
    collecting only after finding the AIF heading and stop when the
    Divisas section begins.
    """

    def __init__(self):
        super().__init__()

        self.in_aif = False
        self.finished = False

        self.pending_month = None
        self.pending_excel_href = None

        self.current_href = None
        self.in_anchor = False

        self.links = {}

    def store_pending_link(self):
        """Store a link once both its month and Excel URL are known."""
        if (
            self.pending_month is None
            or self.pending_excel_href is None
        ):
            return

        self.links.setdefault(
            self.pending_month,
            self.pending_excel_href,
        )

        self.pending_month = None
        self.pending_excel_href = None

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        if self.finished:
            return

        if tag.lower() != "a":
            return

        self.in_anchor = True

        attributes = dict(attrs)

        self.current_href = attributes.get(
            "href"
        )

    def handle_data(
        self,
        data,
    ):
        if self.finished:
            return

        text = normalize_text(data)

        if not text:
            return

        if (
            not self.in_aif
            and "CUENTA AIF SEC PUBLICO NACIONAL"
            in text
        ):
            self.in_aif = True
            return

        if not self.in_aif:
            return

        if "EJECUCION DIVISAS" in text:
            self.finished = True
            return

        if text in MONTHS:
            self.pending_month = MONTHS[text]
            self.store_pending_link()

    def handle_endtag(
        self,
        tag,
    ):
        if tag.lower() != "a":
            return

        if (
            self.in_aif
            and not self.finished
            and self.current_href
        ):
            path = urlparse(
                self.current_href
            ).path.lower()

            if path.endswith(
                (
                    ".xls",
                    ".xlsx",
                )
            ):
                self.pending_excel_href = (
                    self.current_href
                )
                self.store_pending_link()

        self.in_anchor = False
        self.current_href = None


def fetch_aif_links(
    year,
):
    """
    Read the ONP execution page and return the monthly AIF Excel URLs.
    """
    page_url = ONP_PAGE_URL.format(
        year=year,
    )

    response = ONP_SESSION.get(
        page_url,
        timeout=60,
    )

    response.raise_for_status()

    if not response.encoding:
        response.encoding = (
            response.apparent_encoding
        )

    parser = AIFPageParser()

    parser.feed(
        response.text
    )

    return [
        {
            "period": date(
                year,
                month,
                1,
            ),
            "url": urljoin(
                page_url,
                href,
            ),
        }
        for month, href
        in parser.links.items()
    ]


def collect_aif_links(
    last_periods,
):
    """
    Get the latest N published monthly AIF workbooks.

    With LAST_PERIODS = 1000 the full post-2017 history is scanned.
    With LAST_PERIODS = 6 only the current and previous year pages
    need to be inspected.
    """
    current_year = date.today().year

    if last_periods >= 100:
        start_year = AIF_START_YEAR

    else:
        start_year = max(
            AIF_START_YEAR,
            current_year - 1,
        )

    links = []

    for year in range(
        start_year,
        current_year + 1,
    ):
        year_links = fetch_aif_links(
            year,
        )

        links.extend(
            year_links
        )

    links.sort(
        key=lambda item:
            item["period"]
    )

    if not links:
        raise RuntimeError(
            "No monthly AIF Excel files were found"
        )

    return links[-last_periods:]


def find_sheet_layout(
    frame,
):
    """
    Locate CONCEPTO and the final TOTAL column in the workbook.

    The published table contains more than one column named TOTAL.
    The rightmost TOTAL is the total Sector Público Nacional value
    shown in the official sheet.
    """
    max_rows = min(
        25,
        len(frame),
    )

    concept_row = None
    concept_column = None

    for row_index in range(
        max_rows
    ):
        for column_index in range(
            frame.shape[1]
        ):
            if normalize_text(
                frame.iat[
                    row_index,
                    column_index,
                ]
            ) == "CONCEPTO":
                concept_row = row_index
                concept_column = column_index
                break

        if concept_row is not None:
            break

    if concept_row is None:
        return None

    total_columns = []

    for row_index in range(
        concept_row,
        min(
            concept_row + 4,
            len(frame),
        ),
    ):
        for column_index in range(
            frame.shape[1]
        ):
            if normalize_text(
                frame.iat[
                    row_index,
                    column_index,
                ]
            ) == "TOTAL":
                total_columns.append(
                    column_index
                )

    if not total_columns:
        return None

    return {
        "header_row": concept_row,
        "concept_column": concept_column,
        "total_column": max(
            total_columns
        ),
    }


def read_aif_workbook(
    content,
):
    """
    Find the AIF sheet inside one official Excel workbook.
    """
    excel = pd.ExcelFile(
        BytesIO(content)
    )

    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(
            excel,
            sheet_name=sheet_name,
            header=None,
        )

        layout = find_sheet_layout(
            frame
        )

        if layout:
            return (
                frame,
                layout,
            )

    raise RuntimeError(
        "Could not locate AIF table in workbook"
    )


def extract_aif_values(
    frame,
    layout,
):
    """
    Extract every required fiscal line from the official TOTAL column.

    Rows are matched in their published order. If the structure of the
    official workbook changes, the ETL fails instead of silently using
    a different row.
    """
    concept_column = (
        layout["concept_column"]
    )

    total_column = (
        layout["total_column"]
    )

    cursor = (
        layout["header_row"] + 1
    )

    result = {}

    for column, aliases in AIF_ROWS:
        found_row = None

        for row_index in range(
            cursor,
            len(frame),
        ):
            label = frame.iat[
                row_index,
                concept_column,
            ]

            if row_matches(
                label,
                aliases,
            ):
                found_row = row_index
                break

        if found_row is None:
            expected = " / ".join(
                aliases
            )

            raise RuntimeError(
                "Official AIF workbook structure changed. "
                f"Could not find row for "
                f"{column}: {expected}"
            )

        result[column] = parse_amount(
            frame.iat[
                found_row,
                total_column,
            ]
        )

        cursor = found_row + 1

    return result


def fetch_aif_period(
    period,
    url,
):
    """
    Download and parse one official monthly AIF workbook.
    """
    response = ONP_SESSION.get(
        url,
        timeout=60,
    )

    response.raise_for_status()

    frame, layout = read_aif_workbook(
        response.content
    )

    values = extract_aif_values(
        frame,
        layout,
    )

    return {
        "period": period,
        **values,
    }


def fetch_aif_data():
    """
    Fetch the latest AIF monthly observations directly from ONP.
    """
    links = collect_aif_links(
        LAST_PERIODS
    )

    rows = []

    for item in links:
        rows.append(
            fetch_aif_period(
                item["period"],
                item["url"],
            )
        )

    frame = pd.DataFrame(
        rows
    )

    frame = (
        frame
        .sort_values("period")
        .reset_index(drop=True)
    )

    LOGGER.info(
        "Fetched %s AIF periods from %s through %s",
        len(frame),
        frame["period"].min(),
        frame["period"].max(),
    )

    return frame


def fetch_tax_data():
    """
    Fetch detailed tax revenue components using fixed IMIG IDs.
    """
    columns = list(
        TAX_SERIES
    )

    ids = list(
        TAX_SERIES.values()
    )

    response = requests.get(
        SERIES_URL,
        params={
            "ids": ",".join(ids),
            "last": LAST_PERIODS,
            "metadata": "none",
        },
        headers=REQUEST_HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json().get(
        "data",
        [],
    )

    if not data:
        raise RuntimeError(
            "Datos Argentina returned "
            "no IMIG tax observations"
        )

    frame = pd.DataFrame(
        data,
        columns=[
            "period",
            *columns,
        ],
    )

    frame["period"] = pd.to_datetime(
        frame["period"],
        errors="raise",
    ).dt.date

    frame = (
        frame
        .sort_values("period")
        .reset_index(drop=True)
    )

    LOGGER.info(
        "Fetched %s IMIG tax periods from %s through %s",
        len(frame),
        frame["period"].min(),
        frame["period"].max(),
    )

    return frame


def fetch_fiscal_data():
    """
    Merge official AIF rows with the fixed IMIG tax breakdown.

    AIF is the master calendar. A tax series that has not yet been
    published for an AIF month remains NULL rather than causing the
    whole fiscal observation to disappear.
    """
    aif = fetch_aif_data()

    taxes = fetch_tax_data()

    fiscal = aif.merge(
        taxes,
        on="period",
        how="left",
    )

    return (
        fiscal
        .sort_values("period")
        .reset_index(drop=True)
    )


def clean_value(
    value,
):
    """
    Convert pandas NaN into SQL NULL.
    """
    if pd.isna(value):
        return None

    return float(value)


def upsert_fiscal(
    db,
    fiscal,
):
    """
    Insert new monthly observations and update revisions.
    """
    columns = [
        "period",
        *VALUE_COLUMNS,
    ]

    placeholders = ", ".join(
        ["%s"] * len(columns)
    )

    updates = ", ".join(
        f"{column}=VALUES({column})"
        for column in VALUE_COLUMNS
    )

    sql = (
        f"INSERT INTO {TABLE_NAME} "
        f"({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE "
        f"{updates}"
    )

    for _, row in fiscal.iterrows():
        values = [
            row["period"],
            *[
                clean_value(
                    row.get(column)
                )
                for column
                in VALUE_COLUMNS
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
    fiscal = fetch_fiscal_data()

    db = DoltDBManager()

    try:
        db.connect()

        upsert_fiscal(
            db,
            fiscal,
        )

        db.dolt_add(
            TABLE_NAME
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
