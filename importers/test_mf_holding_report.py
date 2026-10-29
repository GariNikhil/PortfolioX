"""Tests for the mutual-fund holding-report importer (Excel / CSV)."""

import tempfile
import shutil
import unittest
from pathlib import Path

from database import db, schema
from database.manager import (
    find_account_by_name,
    get_accounts,
    get_holdings,
    get_prices,
)
from importers.common import ImportFileError
from importers.mf_holding_report import (
    import_mf_holding_report,
    parse_mf_holding_report,
)


def write_csv(path, lines):
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_xlsx(path, rows):
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()
    return path


class MfParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def test_groww_shape_with_preamble(self):
        """Preamble + personal details + summary rows are skipped; the
        derived average cost is invested value / units."""
        path = write_xlsx(self.temp / "mf.xlsx", [
            ["Personal Details"],
            ["Name", "Demo Investor"],
            ["Mobile Number", "9000000000"],
            ["PAN", "AAAAA0000A"],
            [],
            ["HOLDING SUMMARY"],
            ["Total Investments", "Current Portfolio Value"],
            ["5999.08", "5605.96"],
            [],
            ["HOLDINGS AS ON 2026-10-28"],
            [],
            ["Scheme Name", "AMC", "Category", "Sub-category", "Folio No.",
             "Source", "Units", "Invested Value", "Current Value",
             "Returns", "XIRR"],
            ["Parag Parikh ELSS Tax Saver Fund Direct Growth",
             "PPFAS Mutual Fund", "Equity", "ELSS", "15600285", "Groww",
             "60.957", "1999.9", "1871.34", "-128.558", "-3.04%"],
            ["SBI ELSS Tax Saver Fund Direct Growth",
             "SBI Mutual Fund", "Equity", "ELSS", "40910701", "Groww",
             "4.157", "1999.96", "1820.97", "-178.989", "-4.26%"],
        ])

        rows, failures = parse_mf_holding_report(path)

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 2)
        parag = rows[0]
        self.assertEqual(
            parag["symbol"], "Parag Parikh ELSS Tax Saver Fund Direct Growth",
        )
        self.assertEqual(parag["quantity"], 60.957)
        self.assertAlmostEqual(parag["average_price"], 1999.9 / 60.957)
        self.assertAlmostEqual(parag["closing_price"], 1871.34 / 60.957)

    def test_csv_without_current_value(self):
        path = write_csv(self.temp / "mf.csv", [
            "Scheme,Units,Invested Value",
            "HDFC ELSS,1.348,1999.22",
        ])

        rows, failures = parse_mf_holding_report(path)

        self.assertEqual(failures, [])
        self.assertAlmostEqual(rows[0]["average_price"], 1999.22 / 1.348)
        self.assertNotIn("closing_price", rows[0])

    def test_bad_rows_are_reported_not_fatal(self):
        path = write_csv(self.temp / "bad.csv", [
            "Scheme,Units,Invested Value",
            "GOOD FUND,10,5000",
            ",5,100",
            "ZERO UNITS,0,100",
            "BAD UNITS,many,100",
        ])

        rows, failures = parse_mf_holding_report(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "GOOD FUND")
        self.assertEqual(len(failures), 3)

    def test_missing_header_raises(self):
        path = write_csv(self.temp / "nope.csv", ["nothing", "here"])
        with self.assertRaises(ImportFileError):
            parse_mf_holding_report(path)

    def test_unsupported_extension_raises(self):
        path = self.temp / "note.pdf"
        path.write_bytes(b"%PDF-1.4")
        with self.assertRaises(ImportFileError):
            parse_mf_holding_report(path)

    def test_missing_file_raises(self):
        with self.assertRaises(ImportFileError):
            parse_mf_holding_report(self.temp / "missing.xlsx")


class MfImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_import_assigns_to_account_and_seeds_nav(self):
        broker = find_account_by_name("Main broker")
        path = write_xlsx(self.temp / "mf.xlsx", [
            ["PAN", "AAAAA0000A"],
            ["Scheme Name", "Units", "Invested Value", "Current Value"],
            ["HDFC ELSS Tax Saver Fund Direct Plan Growth",
             "1.348", "1999.22", "1913.64"],
        ])

        import_mf_holding_report(path, account_id=broker["id"])

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(rows[0]["symbol"],
                         "HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH")
        # Money is stored as paise, so the derived average is rounded.
        self.assertAlmostEqual(rows[0]["average_price"], 1999.22 / 1.348,
                               places=2)

        prices = {row["symbol"]: row["price"] for row in get_prices()}
        self.assertAlmostEqual(
            prices["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"],
            1913.64 / 1.348,
            places=2,
        )

        # PAN auto-filled into the account, never overwriting user data.
        account = [row for row in get_accounts() if row["id"] == broker["id"]][0]
        self.assertEqual(account["pan"], "AAAAA0000A")

    def test_reimport_supersedes_stale_schemes(self):
        broker = find_account_by_name("Main broker")
        first = write_csv(self.temp / "a.csv", [
            "Scheme,Units,Invested Value",
            "OLD FUND,5,500",
        ])
        import_mf_holding_report(first, account_id=broker["id"])

        second = write_csv(self.temp / "b.csv", [
            "Scheme,Units,Invested Value",
            "NEW FUND,2,300",
        ])
        import_mf_holding_report(second, account_id=broker["id"])

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual([row["symbol"] for row in rows], ["NEW FUND"])

    def test_import_requires_an_account(self):
        path = write_csv(self.temp / "mf.csv", [
            "Scheme,Units,Invested Value",
            "SOME FUND,1,100",
        ])
        with self.assertRaises(ImportFileError):
            import_mf_holding_report(path)

    def test_stock_and_mf_reports_coexist(self):
        """The MF import must not wipe the account's stock snapshot."""
        from importers.holding_report import import_holding_report
        from database.manager import add_transactions

        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "PNB",
                "transaction_type": "BUY", "quantity": 20, "price": 62.02,
            }],
            account_id=broker["id"],
        )
        stock = write_csv(self.temp / "stocks.csv", [
            "Symbol,Qty,Average price,Closing price",
            "PNB,20,62.02,65.50",
        ])
        import_holding_report(stock, account_id=broker["id"])

        mf = write_csv(self.temp / "mf.csv", [
            "Scheme,Units,Invested Value",
            "SBI ELSS,4.157,1999.96",
        ])
        import_mf_holding_report(mf, account_id=broker["id"])

        symbols = {row["symbol"] for row in get_holdings(account_id=broker["id"])}
        self.assertEqual(symbols, {"PNB", "SBI ELSS"})


if __name__ == "__main__":
    unittest.main()
