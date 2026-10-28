"""Tests for the Groww tradebook importer (Phase 3).

The committed fixture uses obviously-synthetic symbols (DEMO_A, DEMO_B,
DEMO_C) — real broker files live under referance/ and are never read by the
test suite, following the project's no-real-financial-data-in-tests rule.
"""

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import openpyxl

from database import db
from database.manager import get_holdings, get_transactions
from database.schema import ensure_schema
from importers.groww import (
    GrowwImportError,
    import_groww_tradebook,
    parse_groww_tradebook,
)

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "groww_tradebook_sample.csv"

NOT_A_TRADEBOOK_CSV = (
    "Id,Date,Status,Type,Account,payee,Amount\n"
    ",01-10-2025,R,withwrawal,PNB,UPI,-30\n"
)


def write_text_file(directory, name, content):
    path = Path(directory) / name
    path.write_text(content, encoding="utf-8")
    return path


class PortfolioXImportTestCase(unittest.TestCase):
    """Shared setup: every test runs against a throwaway database."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "portfoliox.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)


class ParseTests(PortfolioXImportTestCase):
    def test_parses_fixture_rows_and_collects_row_failures(self):
        rows, failures = parse_groww_tradebook(FIXTURE_CSV)

        self.assertEqual(len(rows), 4)
        self.assertEqual([failure.row_number for failure in failures], [6, 7, 8])
        self.assertIn("invalid date", failures[0].reason)
        self.assertIn("quantity", failures[1].reason)
        self.assertIn("buy/sell", failures[2].reason)

        first = rows[0]
        self.assertEqual(first["trade_date"], "2026-03-05")
        self.assertEqual(first["symbol"], "DEMO_A")
        self.assertEqual(first["transaction_type"], "BUY")
        self.assertEqual(first["quantity"], 10.0)
        self.assertEqual(first["price"], 1275.35)
        self.assertEqual(first["brokerage"], 0.0)

    def test_supported_date_formats_all_normalize_to_iso(self):
        content = "Date,Symbol,Quantity,Price,Buy/Sell\n" + "".join(
            f"{raw},DEMO_D,1,10,Buy\n"
            for raw in (
                "2026-03-10", "10-03-2026", "10/03/2026",
                "10 Mar 2026", "10 March 2026",
            )
        )
        source = write_text_file(self.temporary_directory.name, "dates.csv", content)

        rows, failures = parse_groww_tradebook(source)

        self.assertEqual(failures, [])
        self.assertEqual([row["trade_date"] for row in rows], ["2026-03-10"] * 5)

    def test_rejects_non_tradebook_file_naming_missing_columns(self):
        source = write_text_file(
            self.temporary_directory.name, "upi_export.csv", NOT_A_TRADEBOOK_CSV
        )

        with self.assertRaisesRegex(GrowwImportError, "missing required column"):
            parse_groww_tradebook(source)


class ImportTests(PortfolioXImportTestCase):
    def test_import_end_to_end_with_side_aware_net_amounts(self):
        result = import_groww_tradebook(FIXTURE_CSV)

        self.assertEqual(result.imported, 4)
        self.assertEqual(result.duplicates, 0)
        self.assertEqual(len(result.failures), 3)

        transactions = get_transactions()
        self.assertEqual(len(transactions), 4)

        nets = {
            (row["symbol"], row["transaction_type"], round(row["price"], 2)): row["net_amount"]
            for row in transactions
        }
        # BUY debits quantity*price + charges (no charges in a tradebook).
        self.assertAlmostEqual(nets[("DEMO_A", "BUY", 1275.35)], 12753.50, places=2)
        self.assertAlmostEqual(nets[("DEMO_A", "BUY", 1298.25)], 3894.75, places=2)
        # SELL credits quantity*price - charges.
        self.assertAlmostEqual(nets[("DEMO_A", "SELL", 1310.00)], 3930.00, places=2)
        self.assertAlmostEqual(nets[("DEMO_B", "BUY", 2780.50)], 11122.00, places=2)

        # The holdings cache was rebuilt from the imported rows.
        symbols = {row["symbol"] for row in get_holdings()}
        self.assertEqual(symbols, {"DEMO_A", "DEMO_B"})

        # The attempt was recorded in the imports audit table.
        import_log = db.fetch_all("SELECT filename, import_type, status FROM imports")
        self.assertEqual(len(import_log), 1)
        self.assertEqual(import_log[0]["status"], "SUCCESS")
        self.assertEqual(import_log[0]["import_type"], "GROWW_TRADEBOOK")

    def test_reimport_skips_previously_imported_transactions(self):
        first = import_groww_tradebook(FIXTURE_CSV)
        second = import_groww_tradebook(FIXTURE_CSV)

        self.assertEqual(first.imported, 4)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.duplicates, 4)
        self.assertEqual(len(get_transactions()), 4)

        import_log = db.fetch_all("SELECT status FROM imports")
        self.assertEqual(len(import_log), 2)

    def test_skip_duplicates_false_allows_full_reimport(self):
        import_groww_tradebook(FIXTURE_CSV)
        second = import_groww_tradebook(FIXTURE_CSV, skip_duplicates=False)

        self.assertEqual(second.imported, 4)
        self.assertEqual(len(get_transactions()), 8)

    def test_failed_file_is_recorded_and_leaves_database_untouched(self):
        source = write_text_file(
            self.temporary_directory.name, "upi_export.csv", NOT_A_TRADEBOOK_CSV
        )

        with self.assertRaises(GrowwImportError):
            import_groww_tradebook(source)

        self.assertEqual(get_transactions(), [])
        import_log = db.fetch_all("SELECT status FROM imports")
        self.assertEqual(len(import_log), 1)
        self.assertIn("FAILED", import_log[0]["status"])

    def test_xlsx_tradebook_import(self):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Date", "Symbol", "Quantity", "Price", "Buy/Sell", "Trade Type"])
        sheet.append([date(2026, 3, 10), "DEMO_X", 5, 412.75, "Buy", "Delivery"])
        sheet.append([datetime(2026, 3, 11, 9, 36), "DEMO_X", 2, 419.10, "Buy", "Intraday"])
        source = Path(self.temporary_directory.name) / "tradebook.xlsx"
        workbook.save(source)

        result = import_groww_tradebook(source)

        self.assertEqual(result.imported, 2)
        transactions = get_transactions()
        self.assertEqual(
            [row["trade_date"] for row in transactions],
            ["2026-03-11", "2026-03-10"],  # newest trade date first
        )
        self.assertEqual(transactions[0]["transaction_type"], "BUY")


if __name__ == "__main__":
    unittest.main()
