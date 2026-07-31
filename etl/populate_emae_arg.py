#!/usr/bin/env python3
"""
Fetch Argentina's monthly EMAE series from Datos Argentina and store them in Dolt.

Source: INDEC, republished by Datos Argentina.
Dates are stored exactly as returned by the API.
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

# Database column -> Datos Argentina series ID.
EMAE_SERIES = {
     # EMAE general
    "indice": "143.3_NO_PR_2004_A_21",
    "indice_desestacionalizado": "143.3_NO_PR_2004_A_31",
    "indice_tendencia_ciclo": "143.3_NO_PR_2004_A_28",

    # Apertura sectorial
    "agricultura_ganaderia_caza_silvicultura": "11.3_ISOM_2004_M_39",
    "pesca": "11.3_VIPAA_2004_M_5",
    "explotacion_minas_canteras": "11.3_ISD_2004_M_26",
    "industria_manufacturera": "11.3_VMASD_2004_M_23",
    "electricidad_gas_agua": "11.3_ITC_2004_M_21",
    "construccion": "11.3_VMATC_2004_M_12",
    "comercio_mayorista_minorista_reparaciones": "11.3_AGCS_2004_M_41",
    "hoteles_restaurantes": "11.3_P_2004_M_20",
    "transporte_comunicaciones": "11.3_EMC_2004_M_25",
    "intermediacion_financiera": "11.3_IM_2004_M_25",
    "actividades_inmobiliarias_empresariales_alquiler": "11.3_SEGA_2004_M_48",
    "administracion_publica_defensa_seguridad_social": "11.3_C_2004_M_60",
    "ensenanza": "11.3_CMMR_2004_M_10",
    "servicios_sociales_salud": "11.3_HR_2004_M_24",
    "otras_actividades_servicios_comunitarios": "11.3_TAC_2004_M_60",
    "impuestos_netos_subsidios": "11.3_IF_2004_M_25",
}


def fetch_emae(last_periods: int = DEFAULT_LAST_PERIODS) -> pd.DataFrame:
    """Fetch the latest monthly EMAE observations."""
    if last_periods <= 0:
        raise ValueError("last_periods must be greater than zero")

    response = requests.get(
        API_URL,
        params={
            "ids": ",".join(EMAE_SERIES.values()),
            "last": last_periods,
            "metadata": "none",
        },
        timeout=45,
    )
    response.raise_for_status()

    data = response.json().get("data", [])
    if not data:
        raise RuntimeError("Datos Argentina returned no EMAE observations")

    emae = pd.DataFrame(data, columns=["periodo", *EMAE_SERIES])
    emae["periodo"] = pd.to_datetime(emae["periodo"], errors="raise").dt.date
    emae = emae.sort_values("periodo").reset_index(drop=True)

    LOGGER.info(
        "Fetched %s EMAE periods from %s through %s",
        len(emae),
        emae["periodo"].min(),
        emae["periodo"].max(),
    )

    return emae


def upsert_emae(db: DoltDBManager, emae: pd.DataFrame) -> None:
    """Insert new EMAE rows and update revised values."""
    if emae.empty:
        return

    value_columns = list(EMAE_SERIES)
    columns = ["periodo", *value_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(
        f"{column}=VALUES({column})"
        for column in value_columns
    )

    sql = (
        f"INSERT INTO emae ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    for row in emae.itertuples(index=False, name=None):
        db.query(sql, row)


def main() -> None:
    """Fetch EMAE data, store it and create a Dolt commit."""
    last_periods = int(
        os.getenv("EMAE_LAST_PERIODS", DEFAULT_LAST_PERIODS)
    )

    db = DoltDBManager()

    try:
        db.connect()

        emae = fetch_emae(last_periods)
        upsert_emae(db, emae)

        db.dolt_add("emae")
        result = db.dolt_commit(
            f"Update Argentina EMAE data - {datetime.now():%Y-%m-%d %H:%M:%S}"
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