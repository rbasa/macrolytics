#!/usr/bin/env python3
"""Load Argentina's quarterly GDP data into four Dolt tables.

The source is INDEC, republished through the Datos Argentina Time Series API.
Every series is selected with a fixed official identifier. Constant-price and
current-price observations are stored separately, published totals are not
reconstructed, and missing observations remain NULL.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Mapping

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))

from utils.db_manager import DoltDBManager


LOGGER = logging.getLogger(__name__)

API_URL = "https://apis.datos.gob.ar/series/api/series"
DEFAULT_LAST_PERIODS = 8

PBI_CONSTANT_TABLE = "pbi_argentina_precios_2004"
PBI_CURRENT_TABLE = "pbi_argentina_precios_corrientes"
DEMAND_CONSTANT_TABLE = "pbi_demanda_argentina_precios_2004"
DEMAND_CURRENT_TABLE = "pbi_demanda_argentina_precios_corrientes"

PBI_CONSTANT_SERIES = {
    "agricultura_ganaderia_caza_silvicultura": "6.2_AGCS_2004_T_39",
    "pesca": "6.2_P_2004_T_5",
    "explotacion_minas_canteras": "6.2_EMC_2004_T_26",
    "industria_manufacturera": "6.2_IM_2004_T_23",
    "electricidad_gas_agua": "6.2_SEGA_2004_T_32",
    "construccion": "6.2_C_2004_T_12",
    "comercio_mayorista_minorista_reparaciones": "6.2_CMMR_2004_T_41",
    "hoteles_restaurantes": "6.2_HR_2004_T_20",
    "transporte_almacenamiento_comunicaciones": "6.2_TAC_2004_T_40",
    "intermediacion_financiera": "6.2_IF_2004_T_25",
    "actividades_inmobiliarias_empresariales_alquiler": "6.2_AIEA_2004_T_48",
    "administracion_publica_defensa_seguridad_social": "6.2_APDPSSAO_2004_T_60",
    "ensenanza": "6.2_E_2004_T_10",
    "servicios_sociales_salud": "6.2_SSS_2004_T_24",
    "otras_actividades_servicios_comunitarios": "6.2_OASCSP_2004_T_60",
    "hogares_servicio_domestico": "6.2_HPSD_2004_T_32",
    "sectores_productores_bienes": "6.2_SPB_2004_T_27",
    "sectores_productores_servicios": "6.2_SPS_2004_T_30",
    "valor_agregado_bruto_precios_basicos": "6.2_VABPB_2004_T_36",
    "impuesto_valor_agregado": "6.2_IVA_2004_T_23",
    "derechos_importacion": "6.2_DI_2004_T_20",
    "impuestos_productos_netos_subsidios": "6.2_IPNS_2004_T_35",
    "pib": "6.2_PIBPM_2004_T_38",
    "pib_desestacionalizado": "3.2_OGP_D_2004_T_17",
}

PBI_CURRENT_SERIES = {
    "agricultura_ganaderia_caza_silvicultura": "8.2_AGCS_2004_T_39",
    "pesca": "8.2_P_2004_T_5",
    "explotacion_minas_canteras": "8.2_EMC_2004_T_26",
    "industria_manufacturera": "8.2_IM_2004_T_23",
    "electricidad_gas_agua": "8.2_SEGA_2004_T_32",
    "construccion": "8.2_C_2004_T_12",
    "comercio_mayorista_minorista_reparaciones": "8.2_CMMR_2004_T_41",
    "hoteles_restaurantes": "8.2_HR_2004_T_20",
    "transporte_almacenamiento_comunicaciones": "8.2_TAC_2004_T_40",
    "intermediacion_financiera": "8.2_IF_2004_T_25",
    "actividades_inmobiliarias_empresariales_alquiler": "8.2_AIEA_2004_T_48",
    "administracion_publica_defensa_seguridad_social": "8.2_APDPSSAO_2004_T_60",
    "ensenanza": "8.2_E_2004_T_10",
    "servicios_sociales_salud": "8.2_SSS_2004_T_24",
    "otras_actividades_servicios_comunitarios": "8.2_OASCSP_2004_T_60",
    "hogares_servicio_domestico": "8.2_HPSD_2004_T_32",
    "sectores_productores_bienes": "8.2_SPB_2004_T_27",
    "sectores_productores_servicios": "8.2_SPS_2004_T_30",
    "valor_agregado_bruto_precios_basicos": "8.2_VABPB_2004_T_36",
    "impuesto_valor_agregado": "8.2_IVA_2004_T_23",
    "derechos_importacion": "8.2_DI_2004_T_20",
    "impuestos_productos_netos_subsidios": "8.2_IPNS_2004_T_35",
    "pib": "8.2_PIBPM_2004_T_38",
}

DEMAND_CONSTANT_SERIES = {
    "pib": "4.2_OGP_2004_T_17",
    "importaciones": "4.2_OGI_2004_T_25",
    "oferta_global": "4.2_OGT_2004_T_19",
    "exportaciones": "4.2_DGE_2004_T_26",
    "formacion_bruta_capital_fijo": "4.2_DGIT_2004_T_25",
    "consumo_privado": "4.2_MGCP_2004_T_25",
    "consumo_publico": "4.2_DGCP_2004_T_30",
    "variacion_existencias": "4.2_VE_2004_T_21",
    "discrepancia_estadistica": "4.2_DE_2004_T_24",
    "demanda_global": "4.2_DGT_2004_T_20",
    "ibif_construccion": "4.2_DGIC_2004_T_32",
    "ibif_equipo_durable_produccion": "4.2_DGIEDP_2004_T_45",
    "ibif_equipo_durable_nacional": "4.2_DGIEDPN_2004_T_54",
    "ibif_equipo_durable_importado": "4.2_DGIEDPI_2004_T_55",
    "ibif_otros_activos_fijos": "4.2_DGIOAF_2004_T_39",
    "pib_desestacionalizado": "3.2_OGP_D_2004_T_17",
    "importaciones_desestacionalizadas": "3.2_OGI_D_2004_T_25",
    "exportaciones_desestacionalizadas": "3.2_DGE_D_2004_T_26",
    "formacion_bruta_capital_fijo_desestacionalizada": "3.2_DGI_D_2004_T_19",
    "consumo_privado_desestacionalizado": "3.2_DGCP_D_2004_T_27",
    "consumo_publico_desestacionalizado": "3.2_DGCP_D_2004_T_30",
}

DEMAND_CURRENT_SERIES = {
    "pib": "4.4_OGP_2004_T_17",
    "importaciones": "4.4_OGI_2004_T_25",
    "oferta_global": "4.4_OGT_2004_T_19",
    "exportaciones": "4.4_DGE_2004_T_26",
    "formacion_bruta_capital_fijo": "4.4_DGI_2004_T_19",
    "consumo_privado": "4.4_DGCP_2004_T_27",
    "consumo_publico": "4.4_DGCP_2004_T_30",
    "variacion_existencias": "4.4_VE_2004_T_21",
    "discrepancia_estadistica": "4.4_DE_2004_T_24",
    "demanda_global": "4.4_DGT_2004_T_20",
    "ibif_construccion": "4.4_DGIC_2004_T_32",
    "ibif_equipo_durable_produccion": "4.4_DGIEDP_2004_T_45",
    "ibif_equipo_durable_nacional": "4.4_DGIEDPN_2004_T_54",
    "ibif_equipo_durable_importado": "4.4_DGIEDPI_2004_T_55",
    "ibif_otros_activos_fijos": "4.4_DGIOAF_2004_T_39",
}

TABLE_SERIES = {
    PBI_CONSTANT_TABLE: PBI_CONSTANT_SERIES,
    PBI_CURRENT_TABLE: PBI_CURRENT_SERIES,
    DEMAND_CONSTANT_TABLE: DEMAND_CONSTANT_SERIES,
    DEMAND_CURRENT_TABLE: DEMAND_CURRENT_SERIES,
}


def _table_schema(table_name: str, value_columns: list[str]) -> str:
    definitions = ",\n          ".join(
        f"{column} DECIMAL(30,6)" for column in value_columns
    )
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
          periodo DATE PRIMARY KEY,
          {definitions}
        )
    """


TABLE_SCHEMAS = {
    table_name: _table_schema(table_name, list(series))
    for table_name, series in TABLE_SERIES.items()
}


def ensure_tables(db: DoltDBManager) -> None:
    """Create the four ETL-owned quarterly GDP tables if needed."""
    for schema in TABLE_SCHEMAS.values():
        db.query(schema)


def fetch_table(
    series: Mapping[str, str],
    last_periods: int = DEFAULT_LAST_PERIODS,
    *,
    session=requests,
) -> pd.DataFrame:
    """Fetch one deterministic group of quarterly series."""
    if last_periods <= 0:
        raise ValueError("last_periods must be greater than zero")

    response = session.get(
        API_URL,
        params={
            "ids": ",".join(series.values()),
            "last": last_periods,
            "metadata": "none",
        },
        timeout=45,
    )
    response.raise_for_status()

    data = response.json().get("data", [])
    if not data:
        raise RuntimeError("Datos Argentina returned no quarterly GDP data")

    frame = pd.DataFrame(data, columns=["periodo", *series])
    frame["periodo"] = pd.to_datetime(
        frame["periodo"], errors="raise"
    ).dt.date

    invalid_periods = [
        period
        for period in frame["periodo"]
        if period.day != 1 or period.month not in (1, 4, 7, 10)
    ]
    if invalid_periods:
        raise ValueError(
            f"GDP source returned non-quarter-start dates: {invalid_periods}"
        )

    return frame.sort_values("periodo").reset_index(drop=True)


def upsert_table(
    db: DoltDBManager,
    table_name: str,
    dataset: pd.DataFrame,
    value_columns: list[str],
) -> None:
    """Insert new quarters and update revised official observations."""
    if dataset.empty:
        LOGGER.info("No %s observations to store", table_name)
        return

    columns = ["periodo", *value_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column}=VALUES({column})" for column in value_columns
    )
    sql = (
        f"INSERT INTO {table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    affected_rows = 0
    for raw_row in dataset[columns].itertuples(index=False, name=None):
        row = tuple(None if pd.isna(value) else value for value in raw_row)
        result = db.query(sql, row)
        affected_rows += result[0]["affected_rows"]

    LOGGER.info(
        "Stored %s quarters in %s; Dolt reported %s affected rows",
        len(dataset),
        table_name,
        affected_rows,
    )


def main() -> None:
    """Fetch the four GDP datasets, store them and create one Dolt commit."""
    last_periods = int(os.getenv("PBI_LAST_PERIODS", DEFAULT_LAST_PERIODS))
    db = DoltDBManager()

    try:
        db.connect()
        ensure_tables(db)

        periods = []
        for table_name, series in TABLE_SERIES.items():
            dataset = fetch_table(series, last_periods)
            periods.extend(dataset["periodo"])
            upsert_table(db, table_name, dataset, list(series))
            db.dolt_add(table_name)

        LOGGER.info(
            "Fetched quarterly GDP data from %s through %s",
            min(periods),
            max(periods),
        )
        result = db.dolt_commit(
            "Update Argentina quarterly GDP data - "
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
