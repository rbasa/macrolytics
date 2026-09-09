import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

ETL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_DIR))

import populate_pbi_arg as pbi


class QuarterlyPBIETLTest(unittest.TestCase):
    def test_ensure_tables_creates_four_tables(self):
        db = Mock()

        pbi.ensure_tables(db)

        self.assertEqual(db.query.call_count, 4)
        executed_sql = " ".join(
            call.args[0] for call in db.query.call_args_list
        )
        for table_name in pbi.TABLE_SERIES:
            self.assertIn(table_name, executed_sql)

    def test_tables_do_not_mix_valuation_bases(self):
        self.assertEqual(
            set(pbi.PBI_CONSTANT_SERIES) - {"pib_desestacionalizado"},
            set(pbi.PBI_CURRENT_SERIES),
        )
        seasonally_adjusted = {
            "pib_desestacionalizado",
            "importaciones_desestacionalizadas",
            "exportaciones_desestacionalizadas",
            "formacion_bruta_capital_fijo_desestacionalizada",
            "consumo_privado_desestacionalizado",
            "consumo_publico_desestacionalizado",
        }
        self.assertEqual(
            set(pbi.DEMAND_CURRENT_SERIES),
            set(pbi.DEMAND_CONSTANT_SERIES) - seasonally_adjusted,
        )
        for columns in pbi.TABLE_SERIES.values():
            self.assertFalse(
                any("precios_corrientes" in column for column in columns)
            )
            self.assertFalse(
                any("precios_2004" in column for column in columns)
            )

    def test_every_api_request_stays_below_the_series_limit(self):
        self.assertTrue(
            all(len(series) <= 40 for series in pbi.TABLE_SERIES.values())
        )

    def test_fetch_table_uses_fixed_ids_and_parses_quarters(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": [
                ["2025-10-01", 700000.5, None],
                ["2026-01-01", 710000.25, 720000.75],
            ]
        }
        session = Mock()
        session.get.return_value = response
        series = {
            "pib": "6.2_PIBPM_2004_T_38",
            "pib_desestacionalizado": "3.2_OGP_D_2004_T_17",
        }

        result = pbi.fetch_table(series, 8, session=session)

        self.assertEqual(
            list(result["periodo"]),
            [date(2025, 10, 1), date(2026, 1, 1)],
        )
        self.assertTrue(pd.isna(result.iloc[0]["pib_desestacionalizado"]))
        session.get.assert_called_once_with(
            pbi.API_URL,
            params={
                "ids": "6.2_PIBPM_2004_T_38,3.2_OGP_D_2004_T_17",
                "last": 8,
                "metadata": "none",
            },
            timeout=45,
        )

    def test_fetch_table_rejects_non_quarter_start_dates(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": [["2026-03-31", 1]]}
        session = Mock()
        session.get.return_value = response

        with self.assertRaisesRegex(ValueError, "non-quarter-start"):
            pbi.fetch_table(
                {"pib": "6.2_PIBPM_2004_T_38"},
                1,
                session=session,
            )

    def test_upsert_preserves_missing_values_as_null(self):
        db = Mock()
        db.query.return_value = [{"affected_rows": 1}]
        dataset = pd.DataFrame(
            [{
                "periodo": date(2026, 1, 1),
                "pib": 725600.25,
                "pib_desestacionalizado": float("nan"),
            }]
        )

        pbi.upsert_table(
            db,
            pbi.PBI_CONSTANT_TABLE,
            dataset,
            ["pib", "pib_desestacionalizado"],
        )

        _, params = db.query.call_args.args
        self.assertEqual(params[0], date(2026, 1, 1))
        self.assertEqual(params[1], 725600.25)
        self.assertIsNone(params[2])
        self.assertIn("ON DUPLICATE KEY UPDATE", db.query.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
