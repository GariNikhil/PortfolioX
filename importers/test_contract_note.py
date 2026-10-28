"""Tests for the contract-note Orders sheet importer (Phase 3)."""

import unittest
from pathlib import Path

import openpyxl

from database.manager import get_transactions
from importers.common import ImportFileError
from importers.contract_note import (
    import_contract_note,
    parse_contract_note,
)
from importers.support import ScratchDbTestCase

TRADE_DATE = "2023-07-03"

# Layout mirrors the real referance/stock/inter (1).xlsx Orders sheet:
# wrapped header, trade rows, a shifted repeated header, Total rows and an
# expired-option row (zero price, no side flag).
ORDERS_ROWS = [
    ["Order no.", "Order time", "Trade no.", "Trade time",
     "Security/Contract description", "Exchange", "Buy(B)/ Sell(S)",
     "Quantity", "Gross Rate/ Trade Price Per unit (Rs)",
     "Brokerage per Unit (Rs)", "Net Rate per Unit (Rs)",
     "Closing Rate per Unit (only for Derivatives) (Rs)",
     "Net Total (Before Levies) (Rs)", "Remarks"],
    ["1600000010337984", "09:36:25", "516770253", "09:36:25",
     "BANKNIFTY 45500 CE 13 Jul 2023", "NSE", "B", 25, 44.10, None,
     44.10, None, -1102.50, None],
    ["1600000022929648", "10:15:16", "517377189", "10:15:16",
     "BANKNIFTY 45500 CE 13 Jul 2023", "NSE", "S", -25, 39.90, None,
     39.90, None, 997.50, None],
    ["Column1", "Order time", "Trade no.", "Trade time",
     "Security/Contract description", "Exchange", "Buy(B)/ Sell(S)",
     "Quantity", "Gross Rate/ Trade Price Per unit (Rs)",
     "Brokerage per Unit (Rs)", "Net Rate per Unit (Rs)",
     "Closing Rate per Unit (only for Derivatives) (Rs)",
     "Net Total (Before Levies) (Rs)", "Remarks"],
    ["", "", "Total", "", "BANKNIFTY 45500 CE 13 Jul 2023", "", "", 0, "",
     "", "", "", -105.00, ""],
    ["", "", "", "", "Net Total", "", "", "", "", "", "", "", -105.00, ""],
    ["1700000099999990", "13:50:00", "599999990", "13:50:00",
     "NIFTY 19300 PE 03 Aug 2023", "NSE", "B", 75, 1.00, None, 1.00, None,
     75.00, None],
    ["1700000099999999", "14:05:00", "599999999", "14:05:00",
     "NIFTY 19300 PE 03 Aug 2023", "NSE", "", -75, 0, None, 0, None, 0,
     "Expired"],
    ["1700000011111111", "11:00:00", "588888888", "11:00:00",
     "BANKNIFTY 46000 CE 27 Jul 2023", "NSE", "B", "not-a-number", 10, None,
     10, None, None, None],
    ["1700000022222222", "11:30:00", "577777777", "11:30:00",
     "BANKNIFTY 46100 CE 27 Jul 2023", "NSE", "B", 25, 100.50, 0.20, None,
     None, None, None],
]


def write_orders_xlsx(directory, name="orders.xlsx", rows=ORDERS_ROWS,
                      sheet_name="Orders"):
    path = Path(directory) / name
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()
    return path


class ParseTests(ScratchDbTestCase):
    def test_parses_trade_rows_and_skips_headers_totals_and_blanks(self):
        source = write_orders_xlsx(self.temporary_directory.name)

        rows, failures = parse_contract_note(source, TRADE_DATE)

        self.assertEqual(len(rows), 5)
        # The one deliberately bad row (not-a-number quantity) fails.
        self.assertEqual([f.row_number for f in failures], [9])
        self.assertEqual(len(failures), 1)

        first = rows[0]
        self.assertEqual(first["trade_date"], TRADE_DATE)
        self.assertEqual(first["symbol"], "BANKNIFTY 45500 CE 13 JUL 2023")
        self.assertEqual(first["transaction_type"], "BUY")
        self.assertEqual(first["quantity"], 25.0)
        self.assertEqual(first["price"], 44.10)
        self.assertEqual(first["exchange"], "NSE")
        self.assertEqual(first["brokerage"], 0.0)
        self.assertEqual(first["taxes"], 0.0)

    def test_side_falls_back_to_negative_quantity_for_expired_rows(self):
        source = write_orders_xlsx(self.temporary_directory.name)

        rows, _ = parse_contract_note(source, TRADE_DATE)

        expired = rows[3]
        self.assertEqual(expired["symbol"], "NIFTY 19300 PE 03 AUG 2023")
        self.assertEqual(expired["transaction_type"], "SELL")
        self.assertEqual(expired["quantity"], 75.0)
        self.assertEqual(expired["price"], 0.0)

    def test_brokerage_per_unit_is_multiplied_by_quantity(self):
        rows_spec = [ORDERS_ROWS[0], ORDERS_ROWS[-1]]
        source = write_orders_xlsx(self.temporary_directory.name, rows=rows_spec)

        rows, failures = parse_contract_note(source, TRADE_DATE)

        self.assertEqual(failures, [])
        self.assertEqual(rows[0]["brokerage"], 0.20 * 25)

    def test_bad_row_becomes_failure_with_sheet_row_number(self):
        source = write_orders_xlsx(self.temporary_directory.name)

        _, failures = parse_contract_note(source, TRADE_DATE)

        self.assertEqual([f.row_number for f in failures], [9])
        self.assertIn("quantity", failures[0].reason)

    def test_trade_date_must_be_valid(self):
        source = write_orders_xlsx(self.temporary_directory.name)

        with self.assertRaisesRegex(ValueError, "invalid date"):
            parse_contract_note(source, "not-a-date")

    def test_rejects_workbook_without_orders_header(self):
        path = Path(self.temporary_directory.name) / "other.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active.append(["Date", "Amount"])
        workbook.save(path)
        workbook.close()

        with self.assertRaisesRegex(ImportFileError, "no sheet"):
            parse_contract_note(path, TRADE_DATE)

    def test_missing_file_raises(self):
        with self.assertRaisesRegex(ImportFileError, "file not found"):
            parse_contract_note(
                Path(self.temporary_directory.name) / "missing.xlsx",
                TRADE_DATE,
            )


class ImportTests(ScratchDbTestCase):
    def test_import_end_to_end_with_side_aware_net_amounts(self):
        source = write_orders_xlsx(self.temporary_directory.name)

        result = import_contract_note(source, TRADE_DATE)

        self.assertEqual(result.imported, 5)
        self.assertEqual(result.duplicates, 0)
        # The one bad row (not-a-number quantity) is reported, not imported.
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].row_number, 9)

        transactions = get_transactions()
        self.assertEqual(len(transactions), 5)

        # BUY net = qty*price + charges; SELL net = qty*price - charges.
        amounts = sorted(t["net_amount"] for t in transactions)
        self.assertEqual(amounts[0], 0.0)      # expired at 0
        self.assertEqual(amounts[1], 75.00)    # 75*1.00, no charges
        self.assertEqual(amounts[2], 997.50)   # 25*39.90, no charges
        self.assertEqual(amounts[3], 1102.50)  # 25*44.10, no charges
        self.assertEqual(amounts[4], 2517.50)  # 25*100.50 + 25*0.20

    def test_reimport_skips_duplicates(self):
        source = write_orders_xlsx(self.temporary_directory.name)

        first = import_contract_note(source, TRADE_DATE)
        second = import_contract_note(source, TRADE_DATE)

        self.assertEqual(first.imported, 5)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.duplicates, 5)

    def test_oversell_rows_fail_without_killing_the_batch(self):
        # DR. REDDY S LABORATORIES is sold in the real file without a
        # matching buy (shares held in demat) - one such row used to fail
        # the whole batch at rebuild time.
        oversell_rows = [
            ORDERS_ROWS[0],
            ["1800000000000001", "09:00:00", "500000001", "09:00:00",
             "DR. REDDY S LABORATORIES", "NSE", "S", -3, 500.00, None,
             500.00, None, 1500.00, None],
            ORDERS_ROWS[1],
            ORDERS_ROWS[2],
        ]
        source = write_orders_xlsx(
            self.temporary_directory.name, rows=oversell_rows
        )

        result = import_contract_note(source, TRADE_DATE)

        self.assertEqual(result.imported, 2)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("cannot sell", result.failures[0].reason)
        self.assertIn("DR. REDDY S LABORATORIES", result.failures[0].reason)

        transactions = get_transactions()
        self.assertEqual(len(transactions), 2)  # the buy and the sell pair


if __name__ == "__main__":
    unittest.main()
