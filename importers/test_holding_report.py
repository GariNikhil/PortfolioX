"""Tests for the holding-report importer (Excel / CSV snapshot)."""

import csv
import tempfile
import shutil
import unittest
from pathlib import Path

from database import db, schema
from database.manager import (
    add_manual_holding,
    add_transactions,
    find_account_by_name,
    get_accounts,
    get_holdings,
    get_prices,
    rebuild_holdings,
)
from importers.common import ImportFileError
from importers.holding_report import import_holding_report, parse_holding_report


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


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def test_csv_with_plain_headers(self):
        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,10,2500.50",
            "ITC,5,₹400",
        ])

        rows, failures = parse_holding_report(path)

        self.assertEqual(failures, [])
        self.assertEqual(rows, [
            {"symbol": "RELIANCE", "quantity": 10.0, "average_price": 2500.50},
            {"symbol": "ITC", "quantity": 5.0, "average_price": 400.0},
        ])

    def test_xlsx_with_preamble_rows_before_header(self):
        path = write_xlsx(self.temp / "report.xlsx", [
            ["My Broker Ltd"],
            ["Holdings as on 31-Mar-2026"],
            [],
            ["Instrument", "Free Qty", "Buy Avg", "Sell Avg", "LTP"],
            ["TATA MOTORS", 50, "640.25", "700.00", "655.00"],
            ["ITC LTD", 5, 400, "", ""],
        ])

        rows, failures = parse_holding_report(path)

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 2)
        # Buy Avg (index 2) must win over Sell Avg and LTP.
        self.assertEqual(rows[0]["symbol"], "TATA MOTORS")
        self.assertEqual(rows[0]["quantity"], 50.0)
        self.assertEqual(rows[0]["average_price"], 640.25)

    def test_zero_average_is_allowed_for_bonus_shares(self):
        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Average Price",
            "RELIANCE,10,0",
        ])

        rows, failures = parse_holding_report(path)

        self.assertEqual(failures, [])
        self.assertEqual(rows[0]["average_price"], 0.0)

    def test_bad_rows_are_reported_not_fatal(self):
        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,10,2500",
            ",5,400",
            "ITC,not-a-number,400",
            "WIPRO,5,-3",
            "HDFC,2,1500",
        ])

        rows, failures = parse_holding_report(path)

        self.assertEqual(
            [row["symbol"] for row in rows], ["RELIANCE", "HDFC"],
        )
        self.assertEqual(len(failures), 3)

    def test_missing_header_raises(self):
        path = write_csv(self.temp / "report.csv", [
            "some,random,columns",
            "1,2,3",
        ])

        with self.assertRaises(ImportFileError):
            parse_holding_report(path)

    def test_unsupported_extension_raises(self):
        path = self.temp / "report.txt"
        path.write_text("Symbol,Quantity,Avg Price")

        with self.assertRaises(ImportFileError):
            parse_holding_report(path)

    def test_missing_file_raises(self):
        with self.assertRaises(ImportFileError):
            parse_holding_report(self.temp / "nope.csv")


class ImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_import_assigns_to_account_and_rebuilds(self):
        broker = find_account_by_name("Main broker")
        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,7,3000",
        ])

        result = import_holding_report(path, account_id=broker["id"])

        self.assertEqual(result.summary(),
                         "report.csv: 1 imported, 0 duplicates, 0 failed rows")

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "RELIANCE")
        self.assertEqual(rows[0]["quantity"], 7)
        self.assertEqual(rows[0]["average_price"], 3000.0)
        self.assertEqual(rows[0]["invested_amount"], 21000.0)

    def test_import_requires_an_account(self):
        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,7,3000",
        ])

        with self.assertRaises(ImportFileError):
            import_holding_report(path, account_id=None)

    def test_import_replaces_transaction_derived_position(self):
        """The dashboard avg price follows the latest report, not the notes."""

        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"],
        )
        rebuild_holdings()

        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,6,3100",
        ])
        import_holding_report(path, account_id=broker["id"])

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(rows[0]["quantity"], 6)
        self.assertEqual(rows[0]["average_price"], 3100.0)

    def test_reimport_supersedes_stale_symbols(self):
        broker = find_account_by_name("Main broker")
        first = write_csv(self.temp / "first.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,10,2500",
            "ITC,5,400",
        ])
        import_holding_report(first, account_id=broker["id"])

        second = write_csv(self.temp / "second.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,8,2600",
        ])
        import_holding_report(second, account_id=broker["id"])

        self.assertEqual(
            [row["symbol"] for row in get_holdings(account_id=broker["id"])],
            ["RELIANCE"],  # ITC no longer held per the newer report
        )

    def test_user_added_manual_rows_survive_a_report_import(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "TATA MOTORS", 5, 700)

        path = write_csv(self.temp / "report.csv", [
            "Symbol,Quantity,Avg Price",
            "RELIANCE,3,2500",
        ])
        import_holding_report(path, account_id=broker["id"])

        self.assertEqual(
            {(row["symbol"], row["quantity"])
             for row in get_holdings(account_id=broker["id"])},
            {("TATA MOTORS", 5), ("RELIANCE", 3)},
        )

    def test_xlsx_import_roundtrip(self):
        broker = find_account_by_name("Main broker")
        path = write_xlsx(self.temp / "report.xlsx", [
            ["Company", "Quantity", "Average Price"],
            ["COAL INDIA LTD", 3, "234.67"],
        ])

        import_holding_report(path, account_id=broker["id"])

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(rows[0]["symbol"], "COAL INDIA LTD")
        self.assertEqual(rows[0]["average_price"], 234.67)

    def test_closing_price_seeds_prices_table(self):
        broker = find_account_by_name("Main broker")
        path = write_csv(self.temp / "with_close.csv", [
            "Symbol,Qty,Average price,Closing price",
            "PNB,20,62.02,65.50",
        ])

        import_holding_report(path, account_id=broker["id"])

        prices = {row["symbol"]: row["price"] for row in get_prices()}
        self.assertEqual(prices["PNB"], 65.50)

    def test_closing_price_bad_value_does_not_fail_the_row(self):
        broker = find_account_by_name("Main broker")
        path = write_csv(self.temp / "bad_close.csv", [
            "Symbol,Qty,Average price,Closing price",
            "PNB,20,62.02,not-a-number",
        ])

        result = import_holding_report(path, account_id=broker["id"])

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["average_price"], 62.02)
        self.assertTrue(any("closing price" in f.reason for f in result.failures))

    def test_import_autofills_account_details(self):
        broker = find_account_by_name("Main broker")
        path = write_xlsx(self.temp / "groww.xlsx", [
            ["Name", "Demo Investor"],
            ["Unique Client Code", "1234567890"],
            [],
            ["Stock Name", "ISIN", "Quantity", "Average buy price"],
            ["PUNJAB NATIONAL BANK", "INE160A01022", 3, "108.04"],
        ])

        import_holding_report(path, account_id=broker["id"])

        rows = [row for row in get_accounts() if row["id"] == broker["id"]]
        self.assertEqual(rows[0]["ucc"], "1234567890")
        self.assertEqual(rows[0]["holder_name"], "Demo Investor")

    def test_import_autofill_never_overwrites_user_data(self):
        from database.manager import update_account_details
        broker = find_account_by_name("Main broker")
        update_account_details(broker["id"], ucc="1111111111")

        detail_path = write_csv(self.temp / "details.csv", [
            "Unique Client Code,9999999999",
            "Symbol,Qty,Average price",
            "PNB,20,62.02",
        ])

        import_holding_report(detail_path, account_id=broker["id"])

        rows = [row for row in get_accounts() if row["id"] == broker["id"]]
        self.assertEqual(rows[0]["ucc"], "1111111111")


class AccountDetailsExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def test_label_value_rows_are_extracted(self):
        path = write_xlsx(self.temp / "header.xlsx", [
            ["Name", "Demo Investor"],
            ["Unique Client Code", "1234567890"],
            ["PAN", "AAAAA0000A"],
            ["Mobile", "9876543210"],
            [],
            ["Stock Name", "Quantity", "Average buy price"],
        ])

        from importers.holding_report import extract_account_details
        details = extract_account_details(path)

        self.assertEqual(details, {
            "holder_name": "Demo Investor",
            "ucc": "1234567890",
            "pan": "AAAAA0000A",
            "phone": "9876543210",
        })

    def test_unreadable_file_yields_empty_dict(self):
        from importers.holding_report import extract_account_details
        self.assertEqual(
            extract_account_details(self.temp / "missing.xlsx"), {},
        )


if __name__ == "__main__":
    unittest.main()
