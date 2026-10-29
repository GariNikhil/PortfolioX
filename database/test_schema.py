"""Tests for ensure_schema: fresh creation and the v1 -> v2 migration."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import get_dividends, get_transactions
from database.schema import SCHEMA_VERSION, ensure_schema

# Original v1 definitions from the baseline commit: money stored as REAL rupees.
V1_DDL = {
    "transactions": """
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT,
        symbol TEXT,
        isin TEXT,
        exchange TEXT,
        transaction_type TEXT,
        quantity REAL,
        price REAL,
        brokerage REAL DEFAULT 0,
        taxes REAL DEFAULT 0,
        net_amount REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "holdings": """
    CREATE TABLE holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE,
        quantity REAL,
        average_price REAL,
        invested_amount REAL,
        market_value REAL DEFAULT 0,
        profit_loss REAL DEFAULT 0
    )
    """,
    "dividends": """
    CREATE TABLE dividends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        dividend_date TEXT,
        amount REAL
    )
    """,
    "imports": """
    CREATE TABLE imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        import_type TEXT,
        imported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT
    )
    """,
}


def money_column_type(connection, table, column):
    """Read a column's declared type from the migrated table."""

    info = connection.execute(f"PRAGMA table_info({table})").fetchall()
    for cell in info:
        if cell["name"] == column:
            return cell["type"]
    return None


class EnsureSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "portfoliox.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.temporary_directory.cleanup()

    def test_fresh_database_gets_v2_tables_and_constraints(self):
        ensure_schema()

        connection = db.create_connection()
        try:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("transactions", names)
            self.assertIn("holdings", names)
            self.assertIn("dividends", names)
            self.assertIn("imports", names)
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
            )
            self.assertEqual(
                money_column_type(connection, "transactions", "price"), "INTEGER"
            )
        finally:
            connection.close()

        # Invalid transaction type is refused by the CHECK constraint.
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute_query(
                """
                INSERT INTO transactions (
                    trade_date, symbol, transaction_type, quantity, price, net_amount
                )
                VALUES ('2026-01-01', 'ABC', 'DIVIDEND', 1, 100, 100)
                """
            )

        # Negative money is refused.
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute_query(
                """
                INSERT INTO transactions (
                    trade_date, symbol, transaction_type, quantity, price, net_amount
                )
                VALUES ('2026-01-01', 'ABC', 'BUY', 1, -100, 100)
                """
            )

    def test_bank_transactions_table_and_unique_constraint(self):
        ensure_schema()

        connection = db.create_connection()
        try:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("bank_transactions", names)

            # The uniqueness that makes re-imports idempotent.
            indexes = [
                [row["name"] for row in connection.execute(
                    f"PRAGMA index_info({index['name']})"
                )]
                for index in connection.execute(
                    "PRAGMA index_list(bank_transactions)"
                )
                if index["unique"] and index["origin"] in ("u", "pk")
            ]
            self.assertIn(
                ["account_id", "txn_date", "description", "amount", "balance"],
                indexes,
            )
        finally:
            connection.close()

        # A dropped table is recreated by the next ensure_schema (the
        # upgrade path is structural, so it also covers v6 databases).
        connection = db.create_connection()
        try:
            connection.execute("DROP TABLE bank_transactions")
            connection.commit()
        finally:
            connection.close()

        ensure_schema()

        connection = db.create_connection()
        try:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("bank_transactions", names)
        finally:
            connection.close()

    def test_migrates_v1_database_and_multiplies_money_by_100(self):
        connection = db.create_connection()
        try:
            for ddl in V1_DDL.values():
                connection.execute(ddl)
            connection.execute(
                """
                INSERT INTO transactions (
                    trade_date, symbol, isin, exchange, transaction_type,
                    quantity, price, brokerage, taxes, net_amount
                )
                VALUES ('2026-01-01', 'ABC', 'ISIN-1', 'NSE', 'BUY',
                        2, 1234.56, 10.25, 3.5, 2482.87)
                """
            )
            connection.execute(
                "INSERT INTO dividends (symbol, dividend_date, amount)"
                " VALUES ('ABC', '2026-02-01', 1050.25)"
            )
            connection.commit()
        finally:
            connection.close()

        ensure_schema()

        connection = db.create_connection()
        try:
            self.assertEqual(
                money_column_type(connection, "transactions", "price"), "INTEGER"
            )
            self.assertEqual(
                money_column_type(connection, "dividends", "amount"), "INTEGER"
            )
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
            )
        finally:
            connection.close()

        transaction_row = get_transactions()[0]
        self.assertEqual(transaction_row["quantity"], 2)
        self.assertAlmostEqual(transaction_row["price"], 1234.56, places=2)
        self.assertAlmostEqual(transaction_row["brokerage"], 10.25, places=2)
        self.assertAlmostEqual(transaction_row["taxes"], 3.5, places=2)
        self.assertAlmostEqual(transaction_row["net_amount"], 2482.87, places=2)

        dividend_row = get_dividends()[0]
        self.assertAlmostEqual(dividend_row["amount"], 1050.25, places=2)


if __name__ == "__main__":
    unittest.main()
