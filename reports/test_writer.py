"""Tests for the report writers (pure functions, no database needed)."""

import csv
import io
import unittest
from datetime import datetime

from reports.writer import (
    HOLDINGS_CSV_COLUMNS,
    TRANSACTIONS_CSV_COLUMNS,
    holdings_csv,
    portfolio_text_report,
    transactions_csv,
)

HOLDING = {
    "symbol": "RELIANCE",
    "quantity": 20.0,
    "average_price": 2500.5,
    "invested_amount": 50010.0,
    "market_value": 0.0,
    "profit_loss": 0.0,
}

TRANSACTION = {
    "trade_date": "2023-07-03",
    "symbol": "RELIANCE",
    "transaction_type": "BUY",
    "quantity": 20.0,
    "price": 2500.5,
    "brokerage": 20.0,
    "taxes": 50.0,
    "net_amount": 50070.0,
}


def rows_of(csv_text):
    return list(csv.reader(io.StringIO(csv_text)))


class HoldingsCsvTests(unittest.TestCase):
    def test_header_and_row(self):
        rows = rows_of(holdings_csv([HOLDING]))

        self.assertEqual(rows[0], list(HOLDINGS_CSV_COLUMNS))
        self.assertEqual(
            rows[1],
            ["RELIANCE", "20.0", "2500.5", "50010.0", "0.0", "0.0"],
        )

    def test_empty_holdings_produce_header_only(self):
        self.assertEqual(len(rows_of(holdings_csv([]))), 1)

    def test_symbols_with_commas_are_quoted(self):
        weird = dict(HOLDING, symbol="A,B LTD")
        rows = rows_of(holdings_csv([weird]))

        self.assertEqual(rows[1][0], "A,B LTD")


class TransactionsCsvTests(unittest.TestCase):
    def test_header_and_row(self):
        rows = rows_of(transactions_csv([TRANSACTION]))

        self.assertEqual(rows[0], list(TRANSACTIONS_CSV_COLUMNS))
        self.assertEqual(
            rows[1],
            ["2023-07-03", "RELIANCE", "BUY", "20.0", "2500.5", "20.0", "50.0", "50070.0"],
        )

    def test_row_order_is_preserved(self):
        newest = dict(TRANSACTION, trade_date="2023-07-05")
        rows = rows_of(transactions_csv([newest, TRANSACTION]))

        self.assertEqual([row[0] for row in rows[1:]], ["2023-07-05", "2023-07-03"])


class PortfolioTextReportTests(unittest.TestCase):
    def test_summary_lines(self):
        report = portfolio_text_report(
            {
                "total_transactions": 174,
                "total_holdings": 5,
                "total_invested": 56848.89,
                "total_market_value": 0,
                "total_profit_loss": 0,
            },
            [HOLDING],
            generated_at=datetime(2026, 10, 28, 9, 30),
        )

        self.assertIn("PortfolioX report - 2026-10-28 09:30", report)
        self.assertIn("Total invested : ₹56,848.89", report)
        self.assertIn("Holdings       : 5 open positions", report)
        self.assertIn("Transactions   : 174 recorded trades", report)
        self.assertIn("Market value   : - (live prices coming soon)", report)

    def test_holdings_sorted_by_invested_descending(self):
        big = dict(HOLDING, symbol="AAA BIG", invested_amount=90000.0)
        small = dict(HOLDING, symbol="BBB SMALL", invested_amount=100.0)
        report = portfolio_text_report(
            {"total_transactions": 2, "total_holdings": 2,
             "total_invested": 90100.0, "total_market_value": 0,
             "total_profit_loss": 0},
            [small, big],
        )
        lines = report.splitlines()
        big_line = next(i for i, line in enumerate(lines) if "AAA BIG" in line)
        small_line = next(i for i, line in enumerate(lines) if "BBB SMALL" in line)

        self.assertLess(big_line, small_line)

    def test_indian_grouping_in_text_report(self):
        big = dict(HOLDING, symbol="X", invested_amount=12345678.9)
        report = portfolio_text_report(
            {"total_transactions": 1, "total_holdings": 1,
             "total_invested": 12345678.9, "total_market_value": 0,
             "total_profit_loss": 0},
            [big],
        )

        self.assertIn("₹1,23,45,678.90", report)

    def test_empty_holdings_note(self):
        report = portfolio_text_report(
            {"total_transactions": 0, "total_holdings": 0,
             "total_invested": 0, "total_market_value": 0,
             "total_profit_loss": 0},
            [],
        )

        self.assertIn("(no open positions)", report)


if __name__ == "__main__":
    unittest.main()
