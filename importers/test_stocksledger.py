"""Tests for the stocksledger Portfolio snapshot importer (Phase 3)."""

import unittest
from datetime import datetime
from pathlib import Path

import openpyxl

from database.manager import get_holdings, get_transactions
from importers.common import ImportFileError
from importers.stocksledger import (
    import_stocksledger_portfolio,
    parse_stocksledger_portfolio,
)
from importers.support import ScratchDbTestCase

# Layout mirrors the real referance/stock/stocksledger.xlsx Portfolio sheet:
# a title row, the header on the next row, then holdings (with the
# template's many derived columns stubbed as None).
HEADER = [
    "Name", "Purchase Price", "Qty", "Gainers", "Losers", "Pur Dt",
    "Current Price", "Target", "Profit/Loss", "Brokerage",
]


def holding_row(name="Vedanta", price=279.1, qty=17,
                date=datetime(2023, 7, 3), brokerage=2.37):
    return [name, price, qty, None, None, date, None, None, None, brokerage]


SNAPSHOT_ROWS = [
    ["MY PORTFOLIO version: 2014.1"],
    HEADER,
    holding_row(),
    holding_row(name="Coal India Ltd.", price=233.05, qty=1,
                date=datetime(2023, 7, 3), brokerage=0.12),
    HEADER,  # repeated template header
    holding_row(),  # in-file copy of the first holding: imported once
    holding_row(name="Punj. NationlBak", price=61.8, qty=20,
                date=datetime(2023, 7, 13), brokerage=0.62),
    holding_row(name="Reliance Power L", price=None, qty=35,
                date=datetime(2023, 7, 13)),  # missing price: failure
]


def write_portfolio_xlsx(directory, name="stocksledger.xlsx",
                         rows=SNAPSHOT_ROWS, sheet_name="Portfolio"):
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
    def test_parses_holdings_as_buys_and_dedupes_in_file_copies(self):
        source = write_portfolio_xlsx(self.temporary_directory.name)

        rows, failures = parse_stocksledger_portfolio(source)

        self.assertEqual(len(failures), 1)  # the missing-price row
        self.assertIn("purchase price", failures[0].reason)

        # Vedanta appears twice in the sheet but is imported once.
        self.assertEqual(len(rows), 3)
        symbols = [row["symbol"] for row in rows]
        self.assertEqual(symbols, ["VEDANTA", "COAL INDIA LTD.", "PUNJ. NATIONLBAK"])

        first = rows[0]
        self.assertEqual(first["transaction_type"], "BUY")  # snapshot: no sells
        self.assertEqual(first["trade_date"], "2023-07-03")
        self.assertEqual(first["quantity"], 17.0)
        self.assertEqual(first["price"], 279.1)
        self.assertEqual(first["brokerage"], 2.37)

    def test_row_without_date_fails(self):
        rows_spec = [HEADER, holding_row(date=None)]
        source = write_portfolio_xlsx(self.temporary_directory.name, rows=rows_spec)

        rows, failures = parse_stocksledger_portfolio(source)

        self.assertEqual(rows, [])
        self.assertEqual(len(failures), 1)
        self.assertIn("missing purchase date", failures[0].reason)

    def test_rejects_workbook_without_portfolio_header(self):
        path = Path(self.temporary_directory.name) / "other.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active.append(["Date", "Amount"])
        workbook.save(path)
        workbook.close()

        with self.assertRaisesRegex(ImportFileError, "no sheet"):
            parse_stocksledger_portfolio(path)

    def test_missing_file_raises(self):
        with self.assertRaisesRegex(ImportFileError, "file not found"):
            parse_stocksledger_portfolio(
                Path(self.temporary_directory.name) / "missing.xlsx"
            )


class ImportTests(ScratchDbTestCase):
    def test_import_end_to_end(self):
        source = write_portfolio_xlsx(self.temporary_directory.name)

        result = import_stocksledger_portfolio(source)

        self.assertEqual(result.imported, 3)
        self.assertEqual(len(result.failures), 1)

        holdings = get_holdings()
        self.assertEqual(len(holdings), 3)
        self.assertEqual(holdings[0]["symbol"], "COAL INDIA LTD.")
        self.assertEqual(holdings[0]["quantity"], 1.0)

        # BUY net = qty*price + charges ( Vedanta: 17*279.1 + 2.37 ).
        transactions = get_transactions()
        vedanta = next(t for t in transactions if t["symbol"] == "VEDANTA")
        self.assertEqual(vedanta["net_amount"], 4747.07)

    def test_reimport_skips_duplicates(self):
        source = write_portfolio_xlsx(self.temporary_directory.name)

        first = import_stocksledger_portfolio(source)
        second = import_stocksledger_portfolio(source)

        self.assertEqual(first.imported, 3)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.duplicates, 3)


if __name__ == "__main__":
    unittest.main()
