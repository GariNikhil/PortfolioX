"""Tests for the IIFL Trade Listing importer (Phase 3).

xlrd cannot write .xls files, so the parser core is tested with synthetic
row lists and only the file-level error paths touch the filesystem.
"""

import unittest
from pathlib import Path

import xlrd

from importers.common import ImportFileError
from importers.iifl import parse_iifl_trade_listing, parse_trade_listing_rows
from importers.support import ScratchDbTestCase

# Mirrors the real Trade_Listing DEMO_8_19_2024.xls layout: header at
# row index 11, then one row per instrument per date with both sides.
HEADER_ROW = [
    "Exchange", "Trade Date", None, "Code", "Name", None, "Expiry Date",
    "Strike Price", "Option Type", None, None, "Buy Qty", "Buy Market Rate",
    None, "Buy Brokerage", "Buy Net Rate", "Buy Amt", None, "Sell Qty", None,
    "Sell Market Rate", "Sell Brokerage", None, "Sell Net Rate", "Sell Amt",
    "Net Qty", "Net Value", None, None,
]

EQUITY_ROW = [
    "NSECASH", "27/06/2022", None, 513228.0, "PENIND", None, None, 0.0, None,
    None, None, 4.0, 36.0, None, 0.9, 36.9, 144.0, None, 4.0, None, 36.25,
    0.9075, None, 35.34, 145.0, 0.0, 1.0, None, None,
]

OPTION_ROW = [
    "NSEFNO", "03/08/2023", None, "NIFTY", "OPTIDX", None, 20230803.0,
    19300.0, "PE", None, None, 75.0, 1.05, None, 10.5, 1.19, 78.75, None,
    None, None, None, None, None, None, None, 75.0, -78.75, None, None,
]

BLANK_AND_BAD_ROWS = [
    [None] * 29,  # blank sheet row: skipped
    ["NSECASH", "29/07/2022", None, 500470.0, "TATASTEEL", None, None, 0.0,
     None, None, None, None, None, None, None, None, None, None, None, None,
     None, None, None, None, None, 0.0, 0.0, None, None],  # no quantities
]


def rows_below_header():
    return [HEADER_ROW, EQUITY_ROW, OPTION_ROW] + BLANK_AND_BAD_ROWS


class CoreParseTests(ScratchDbTestCase):
    def test_equity_row_yields_buy_and_sell_transactions(self):
        rows, failures = parse_trade_listing_rows(rows_below_header(), 0)

        # The blank row is skipped; the no-quantity TATASTEEL row fails.
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].row_number, 5)
        self.assertIn("no buy or sell quantity", failures[0].reason)

        self.assertEqual(len(rows), 3)

        buy, sell, option = rows
        self.assertEqual(buy["trade_date"], "2022-06-27")
        self.assertEqual(buy["symbol"], "PENIND")
        self.assertEqual(buy["transaction_type"], "BUY")
        self.assertEqual(buy["quantity"], 4.0)
        self.assertEqual(buy["price"], 36.0)
        self.assertEqual(buy["brokerage"], 0.9)
        self.assertEqual(buy["exchange"], "NSECASH")

        self.assertEqual(sell["transaction_type"], "SELL")
        self.assertEqual(sell["price"], 36.25)
        self.assertEqual(sell["brokerage"], 0.9075)

    def test_option_row_builds_composite_symbol_with_iso_expiry(self):
        rows, _ = parse_trade_listing_rows(rows_below_header(), 0)

        option = rows[-1]
        self.assertEqual(option["symbol"], "NIFTY 19300 PE 2023-08-03")
        self.assertEqual(option["trade_date"], "2023-08-03")
        self.assertEqual(option["transaction_type"], "BUY")
        self.assertEqual(option["exchange"], "NSEFNO")

    def test_excel_serial_date_cells_are_converted(self):
        # The real file stores Trade Date as DD/MM/YYYY text, but date cells
        # can also arrive as Excel serial floats; 44739.0 is 2022-06-27 in
        # the 1900 datemode.
        dated_row = list(EQUITY_ROW)
        dated_row[1] = 44739.0

        rows, failures = parse_trade_listing_rows(
            [HEADER_ROW, dated_row], 0, datemode=0
        )

        self.assertEqual(failures, [])
        self.assertEqual(rows[0]["trade_date"], "2022-06-27")

    def test_row_without_quantities_fails(self):
        _, failures = parse_trade_listing_rows(rows_below_header(), 0)

        self.assertEqual(len(failures), 1)
        self.assertIn("no buy or sell quantity", failures[0].reason)
        self.assertEqual(failures[0].row_number, 5)  # blank row is skipped

    def test_blank_rows_are_skipped_entirely(self):
        rows, failures = parse_trade_listing_rows(
            [HEADER_ROW, [None] * 29, EQUITY_ROW], 0
        )

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 2)


class FileLevelTests(ScratchDbTestCase):
    def test_missing_file_raises(self):
        with self.assertRaisesRegex(ImportFileError, "file not found"):
            parse_iifl_trade_listing(
                Path(self.temporary_directory.name) / "missing.xls"
            )

    def test_non_xls_file_raises_readable_error(self):
        not_really_xls = Path(self.temporary_directory.name) / "fake.xls"
        not_really_xls.write_text("just some text", encoding="utf-8")

        with self.assertRaisesRegex(ImportFileError, "could not open"):
            parse_iifl_trade_listing(not_really_xls)


if __name__ == "__main__":
    unittest.main()
