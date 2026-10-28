import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    add_dividend,
    add_import,
    add_transaction,
    get_dividends,
    get_holdings,
    get_portfolio_summary,
    get_transactions,
    update_holding,
)
from database.schema import create_tables


class PortfolioManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "portfoliox.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        create_tables()

    def tearDown(self):
        self.database_patch.stop()
        self.temporary_directory.cleanup()

    def test_adds_and_reads_portfolio_records(self):
        add_transaction("2026-08-05", "RELIANCE", "INE002A01018", "NSE", "BUY", 10, 2500, 20, 15)
        update_holding("RELIANCE", 10, 2500, 25035, 26000, 965)
        add_dividend("RELIANCE", "2026-08-05", 100)
        add_import("sample_tradebook.csv", "GROWW_TRADEBOOK", "SUCCESS")

        transactions = get_transactions()
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0][2], "RELIANCE")
        self.assertEqual(transactions[0][10], 25035)
        self.assertEqual(get_holdings()[0][1], "RELIANCE")
        self.assertEqual(len(get_dividends()), 1)

        summary = get_portfolio_summary()
        self.assertEqual(summary["total_transactions"], 1)
        self.assertEqual(summary["total_holdings"], 1)
        self.assertEqual(summary["total_invested"], 25035)
        self.assertEqual(summary["total_market_value"], 26000)
        self.assertEqual(summary["total_profit_loss"], 965)


if __name__ == "__main__":
    unittest.main()