"""Tests for the spreadsheet bank-statement importer (XLSX / CSV)."""

import csv
import tempfile
import shutil
import unittest
from pathlib import Path

from database import db, schema
from database.manager import (
    find_account_by_name,
    get_accounts,
    get_bank_transactions,
)
from importers.bank_statement_tabular import (
    import_bank_statement_tabular,
    parse_bank_statement_tabular,
)
from importers.common import ImportFileError


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


AXIS_ROWS = [
    ["Statement of Axis Account No : 912345678901234"],
    [],
    ["Tran Date", "Chq No", "Particulars", "Debit", "Credit", "Balance"],
    ["01-03-2026", "", "UPI/SALARY CREDIT", "", "50000.00", "150000.00"],
    ["05-03-2026", "", "UPI/AMAZON PAY", "2500.50", "", "147499.50"],
    ["09-03-2026", "", "NEFT RENT", "12000.00", "", "135499.50"],
]


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def test_xlsx_with_preamble_and_axis_headers(self):
        path = write_xlsx(self.temp / "statement.xlsx", AXIS_ROWS)

        rows, failures, meta = parse_bank_statement_tabular(path)

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 3)
        # Credits positive, debits negative.
        self.assertEqual(rows[0]["amount"], 50000.0)
        self.assertEqual(rows[1]["amount"], -2500.5)
        self.assertEqual(rows[2]["amount"], -12000.0)
        # Dates normalize to ISO; descriptions survive.
        self.assertEqual(rows[0]["txn_date"], "2026-03-01")
        self.assertEqual(rows[1]["description"], "UPI/AMAZON PAY")
        # Running balance column is carried; the last one closes.
        self.assertEqual(rows[1]["balance"], 147499.5)
        self.assertEqual(meta["closing_balance"], 135499.5)

    def test_csv_with_generic_headers(self):
        path = write_csv(self.temp / "statement.csv", [
            "Date,Description,Withdrawal,Deposit,Balance",
            "2026-03-01,SALARY,,50000,50000",
            "2026-03-02,RENT,12000,,38000",
        ])

        rows, failures, meta = parse_bank_statement_tabular(path)

        self.assertEqual(failures, [])
        self.assertEqual(rows[0]["amount"], 50000.0)
        self.assertEqual(rows[1]["amount"], -12000.0)
        self.assertEqual(meta["closing_balance"], 38000.0)

    def test_missing_balance_column_is_not_fatal(self):
        path = write_csv(self.temp / "statement.csv", [
            "Txn Date,Narration,Debit,Credit",
            "01-03-2026,SALARY,,50000",
            "02-03-2026,RENT,12000",
        ])

        rows, failures, meta = parse_bank_statement_tabular(path)

        self.assertEqual(failures, [])
        self.assertIsNone(rows[0]["balance"])
        self.assertIsNone(meta["closing_balance"])

    def test_bad_rows_are_reported_not_fatal(self):
        path = write_csv(self.temp / "statement.csv", [
            "Date,Description,Debit,Credit",
            "not-a-date,SALARY,,50000",
            "2026-03-02,,12000,",
            "2026-03-03,ZERO ROW,,",
            "2026-03-04,GOOD ROW,100,",
        ])

        rows, failures, meta = parse_bank_statement_tabular(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"], "GOOD ROW")
        self.assertEqual(
            [failure.row_number for failure in failures], [2, 3, 4],
        )

    def test_missing_header_raises(self):
        path = write_csv(self.temp / "statement.csv", [
            "some,random,columns,here",
            "1,2,3,4",
        ])

        with self.assertRaises(ImportFileError):
            parse_bank_statement_tabular(path)


class ImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_import_auto_creates_the_banks_account(self):
        path = write_xlsx(self.temp / "statement.xlsx", AXIS_ROWS)

        result = import_bank_statement_tabular(
            path, bank_name="Axis Bank",
        )

        self.assertEqual(result.imported, 3)
        account = find_account_by_name("Axis Bank")
        self.assertIsNotNone(account)
        rows = get_bank_transactions(account_id=account["id"])
        self.assertEqual(len(rows), 3)
        # The closing balance seeds the account balance (stored as paise).
        self.assertEqual(account["current_balance"], 13549950)

    def test_reimport_skips_duplicates(self):
        path = write_csv(self.temp / "statement.csv", [
            "Date,Description,Withdrawal,Deposit,Balance",
            "2026-03-01,SALARY,,50000,50000",
            "2026-03-02,RENT,12000,,38000",
        ])

        first = import_bank_statement_tabular(path, bank_name="Axis Bank")
        second = import_bank_statement_tabular(path, bank_name="Axis Bank")

        self.assertEqual(first.imported, 2)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.duplicates, 2)

    def test_explicit_account_wins_over_auto_creation(self):
        path = write_xlsx(self.temp / "statement.xlsx", AXIS_ROWS)
        personal = add_personal_account()

        result = import_bank_statement_tabular(
            path, account_id=personal, bank_name="Axis Bank",
        )

        self.assertEqual(result.imported, 3)
        names = [account["name"] for account in get_accounts()]
        self.assertNotIn("Axis Bank", names)


def add_personal_account():
    from database.manager import add_account

    return add_account("My Bank", "PERSONAL")


if __name__ == "__main__":
    unittest.main()
