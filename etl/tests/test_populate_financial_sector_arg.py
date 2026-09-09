import sys
import unittest
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

from openpyxl import Workbook

ETL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL_DIR))

import populate_financial_sector_arg as financial


class FinancialSectorETLTest(unittest.TestCase):
    def test_ensure_tables_creates_every_financial_table(self):
        db = Mock()

        financial.ensure_tables(db)

        self.assertEqual(
            db.query.call_count,
            len(financial.TABLE_SCHEMAS),
        )
        executed_sql = " ".join(
            call.args[0] for call in db.query.call_args_list
        )
        for table_name in financial.TABLE_SCHEMAS:
            self.assertIn(table_name, executed_sql)

    def test_fetch_series_parses_bcra_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": 200,
            "metadata": {"resultset": {"count": 2}},
            "results": [{
                "idVariable": 1,
                "detalle": [
                    {"fecha": "2026-08-15", "valor": 41234.5},
                    {"fecha": "2026-08-14", "valor": 41000},
                ],
            }],
        }
        session = Mock()
        session.get.return_value = response

        result = financial.fetch_series(
            1,
            date(2026, 8, 1),
            date(2026, 8, 17),
            session=session,
        )

        self.assertEqual(
            result[date(2026, 8, 15)],
            Decimal("41234.5"),
        )
        session.get.assert_called_once()

    def test_parse_localized_decimal_accepts_both_bcra_formats(self):
        self.assertEqual(
            financial.parse_localized_decimal("47.599,19"),
            Decimal("47599.19"),
        )
        self.assertEqual(
            financial.parse_localized_decimal("46,886.71"),
            Decimal("46886.71"),
        )

    def test_fetch_financial_sector_outer_joins_dates(self):
        series = {
            1: {date(2026, 8, 14): Decimal("41000")},
            78: {date(2026, 8, 14): Decimal("100")},
            109: {date(2026, 8, 15): Decimal("500000")},
            7: {date(2026, 8, 14): Decimal("35.5")},
            44: {date(2026, 8, 14): Decimal("37.5")},
        }

        original = financial.fetch_series
        financial.fetch_series = lambda series_id, *args, **kwargs: series.get(
            series_id,
            {},
        )
        try:
            rows = financial.fetch_financial_sector(
                date(2026, 8, 14),
                date(2026, 8, 15),
            )
        finally:
            financial.fetch_series = original

        self.assertEqual([row["periodo"] for row in rows], [
            date(2026, 8, 14),
            date(2026, 8, 15),
        ])
        self.assertIsNone(rows[0]["m2_millones_ars"])
        self.assertIsNone(rows[1]["badlar_bancos_privados_tna"])

    def test_fetch_monthly_balance_converts_thousands_to_millions(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = (
            "86;31/07/2026;58612001168.6986\n"
            "94;31/07/2026;2799021279\n"
            "9999;31/07/2026;123\n"
        )
        session = Mock()
        session.get.return_value = response

        rows = financial.fetch_monthly_balance(
            date(2026, 1, 1),
            session=session,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["activos_externos_netos_millones_ars"],
            Decimal("58612001.1686986"),
        )
        self.assertEqual(
            rows[0]["adelantos_transitorios_millones_ars"],
            Decimal("2799021.279"),
        )

    def test_fetch_credit_quality_reads_official_workbook_columns(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "8"
        sheet.append(["Fecha", "Sistema", None, None, None, None, "Empresas", "Familias"])
        sheet.append([
            datetime(2026, 6, 1),
            7.63,
            None,
            None,
            None,
            None,
            3.5,
            12.77,
        ])
        content = BytesIO()
        workbook.save(content)

        original = financial._latest_bank_report_workbook
        financial._latest_bank_report_workbook = lambda **kwargs: content.getvalue()
        try:
            rows = financial.fetch_credit_quality(date(2026, 1, 1))
        finally:
            financial._latest_bank_report_workbook = original

        self.assertEqual(rows[0]["periodo"], date(2026, 6, 1))
        self.assertEqual(
            rows[0]["morosidad_sector_privado_porcentaje"],
            Decimal("7.63"),
        )

    def test_fetch_reserve_liquidity_filters_and_parses_index(self):
        index_response = Mock()
        index_response.raise_for_status.return_value = None
        index_response.json.return_value = {
            "data": {"items": [
                {"url": "/archivos/temp0626.pdf"},
                {"url": "/archivos/temp1225.pdf"},
            ]},
        }
        pdf_response = Mock()
        pdf_response.raise_for_status.return_value = None
        pdf_response.content = b"pdf"
        session = Mock()
        session.get.side_effect = [index_response, pdf_response]

        original = financial.parse_reserve_liquidity_pdf
        financial.parse_reserve_liquidity_pdf = lambda content: {
            "periodo": date(2026, 6, 30),
            "reservas_netas_liquidez_millones_usd": Decimal("100"),
            "drenajes_netos_corto_plazo_millones_usd": Decimal("50"),
        }
        try:
            rows = financial.fetch_reserve_liquidity(
                date(2026, 1, 1),
                session=session,
            )
        finally:
            financial.parse_reserve_liquidity_pdf = original

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["periodo"], date(2026, 6, 30))

    def test_get_start_date_uses_historical_default_for_empty_table(self):
        db = Mock()
        db.query.return_value = [{"latest_period": None}]

        self.assertEqual(
            financial.get_start_date(db, 30),
            financial.DEFAULT_START_DATE,
        )

    def test_needs_daily_backfill_detects_late_new_series(self):
        db = Mock()
        db.query.return_value = [{
            "c0": date(2026, 7, 1),
            "c1": date(2026, 7, 1),
            "c2": date(2026, 7, 1),
        }]

        self.assertTrue(financial.needs_daily_backfill(db))


if __name__ == "__main__":
    unittest.main()
