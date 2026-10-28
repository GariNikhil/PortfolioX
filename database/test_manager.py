import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    add_dividend,
    add_import,
    add_transaction,
    add_transactions,
    delete_transaction,
    get_dividends,
    get_holdings,
    get_portfolio_summary,
    get_transactions,
    rebuild_holdings,
    update_holding,
)
from database.schema import ensure_schema


class PortfolioManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "portfoliox.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()

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
        self.assertEqual(transactions[0]["symbol"], "RELIANCE")
        self.assertAlmostEqual(transactions[0]["net_amount"], 25035, places=2)
        self.assertEqual(get_holdings()[0]["symbol"], "RELIANCE")
        self.assertEqual(len(get_dividends()), 1)

        summary = get_portfolio_summary()
        self.assertEqual(summary["total_transactions"], 1)
        self.assertEqual(summary["total_holdings"], 1)
        self.assertAlmostEqual(summary["total_invested"], 25035, places=2)
        self.assertAlmostEqual(summary["total_market_value"], 26000, places=2)
        self.assertAlmostEqual(summary["total_profit_loss"], 965, places=2)

    def test_buy_net_adds_charges_and_sell_net_subtracts_charges(self):
        add_transaction("2026-08-05", "RELIANCE", "INE002A01018", "NSE", "BUY", 10, 2500, 20, 15)
        add_transaction("2026-08-09", "RELIANCE", "INE002A01018", "NSE", "SELL", 4, 2600, 20, 15)

        rows = {row["transaction_type"]: row["net_amount"] for row in get_transactions()}
        self.assertAlmostEqual(rows["BUY"], 10 * 2500 + 20 + 15, places=2)
        self.assertAlmostEqual(rows["SELL"], 4 * 2600 - 20 - 15, places=2)

    def test_money_stored_as_paise_remains_exact(self):
        add_transaction("2026-08-05", "TCS", "INE469I01027", "NSE", "BUY", 3, 3827.45, 18.99, 11.73)

        connection = db.create_connection()
        try:
            stored = connection.execute("SELECT price, brokerage, taxes FROM transactions").fetchone()
            self.assertEqual(stored["price"], 382745)
            self.assertEqual(stored["brokerage"], 1899)
            self.assertEqual(stored["taxes"], 1173)
        finally:
            connection.close()

        row = get_transactions()[0]
        self.assertAlmostEqual(row["price"], 3827.45, places=2)
        self.assertAlmostEqual(row["brokerage"], 18.99, places=2)
        self.assertAlmostEqual(row["taxes"], 11.73, places=2)

    def test_rejects_unsupported_transaction_type(self):
        with self.assertRaisesRegex(ValueError, "expected BUY or SELL"):
            add_transaction("2026-08-05", "RELIANCE", "INE002A01018", "NSE", "DIVIDEND", 1, 100)

    def test_batch_insert_is_atomic(self):
        rows = [
            {"trade_date": "2026-08-05", "symbol": "TCS", "isin": "INE469I01027",
             "exchange": "NSE", "transaction_type": "BUY", "quantity": 2, "price": 3000},
            {"trade_date": "2026-08-06", "symbol": "TCS", "isin": "INE469I01027",
             "exchange": "NSE", "transaction_type": "SELL", "quantity": 1, "price": 3100},
        ]
        self.assertEqual(add_transactions(rows), 2)
        self.assertEqual(len(get_transactions()), 2)

        # One unsupported row rolls the whole batch back.
        rows.append({"trade_date": "2026-08-07", "symbol": "TCS", "isin": "INE469I01027",
                     "exchange": "NSE", "transaction_type": "DIVIDEND", "quantity": 1, "price": 1})
        with self.assertRaises(ValueError):
            add_transactions(rows)
        self.assertEqual(len(get_transactions()), 2)

    def test_delete_transaction_removes_and_reports_missing(self):
        add_transaction("2026-08-05", "TCS", "INE469I01027", "NSE", "BUY", 1, 3000)
        transaction_id = get_transactions()[0]["id"]

        self.assertTrue(delete_transaction(transaction_id))
        self.assertEqual(get_transactions(), [])
        self.assertFalse(delete_transaction(transaction_id))

    def test_rebuild_holdings_recomputes_and_clears_fully_sold_symbols(self):
        add_transaction("2026-08-01", "RELIANCE", "INE002A01018", "NSE", "BUY", 10, 2500)
        add_transaction("2026-08-02", "RELIANCE", "INE002A01018", "NSE", "BUY", 5, 3000)
        add_transaction("2026-08-03", "RELIANCE", "INE002A01018", "NSE", "SELL", 12, 2900)
        add_transaction("2026-08-01", "ITC", "INE154A01025", "NSE", "BUY", 2, 400)
        add_transaction("2026-08-04", "ITC", "INE154A01025", "NSE", "SELL", 2, 420)

        holdings = rebuild_holdings()
        symbols = [holding.symbol for holding in holdings]
        self.assertEqual(symbols, ["RELIANCE"])

        rows = get_holdings()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "RELIANCE")
        self.assertEqual(rows[0]["quantity"], 3)
        self.assertAlmostEqual(rows[0]["invested_amount"], 8000, places=2)
        # Repeating averages round to the nearest paise on read.
        self.assertAlmostEqual(rows[0]["average_price"], 2666.67, places=2)

        # A later transaction reflects through a rebuild, not drift.
        add_transaction("2026-08-05", "RELIANCE", "INE002A01018", "NSE", "SELL", 3, 3400)
        rebuild_holdings()
        self.assertEqual(get_holdings(), [])


if __name__ == "__main__":
    unittest.main()
