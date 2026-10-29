"""Tests for the v3 data layer: accounts, prices, per-account holdings."""

import sqlite3
import tempfile
import shutil
import unittest
from pathlib import Path

from database import db, schema
from database.manager import (
    UNASSIGNED,
    add_account,
    add_transactions,
    apply_prices_to_holdings,
    find_account_by_name,
    get_accounts,
    get_holdings,
    get_prices,
    get_portfolio_summary,
    get_prices_paise,
    get_transactions,
    rebuild_holdings,
    set_main_account,
    set_price,
)


class V3LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_fresh_database_seeds_two_main_accounts(self):
        accounts = get_accounts()
        names = [(row["name"], row["kind"], row["is_main"]) for row in accounts]

        self.assertIn(("Main broker", "BROKER", 1), names)
        self.assertIn(("Main personal", "PERSONAL", 1), names)

    def test_add_account_validates(self):
        with self.assertRaises(ValueError):
            add_account("", "BROKER")
        with self.assertRaises(ValueError):
            add_account("Zerodha", "INVALID")
        with self.assertRaises(ValueError):  # duplicate, case-insensitive
            add_account("main broker", "BROKER")

        account_id = add_account("Zerodha", "BROKER")
        self.assertIsNotNone(find_account_by_name("zerodha"))
        self.assertEqual(find_account_by_name("zerodha")["id"], account_id)

    def test_set_main_account_is_one_per_kind(self):
        second_broker = add_account("Groww", "BROKER")

        # Marking the new broker main clears the seeded broker's flag,
        # and leaves the personal main untouched.
        updated = set_main_account(second_broker)
        self.assertEqual(updated["is_main"], 1)
        self.assertEqual(find_account_by_name("Main broker")["is_main"], 0)
        self.assertEqual(find_account_by_name("Main personal")["is_main"], 1)

        # Same for the personal kind, independently.
        axis = add_account("Axis Bank", "PERSONAL")
        set_main_account(axis)
        self.assertEqual(find_account_by_name("Axis Bank")["is_main"], 1)
        self.assertEqual(find_account_by_name("Main personal")["is_main"], 0)
        self.assertEqual(find_account_by_name("Groww")["is_main"], 1)

    def test_set_main_account_missing_id(self):
        self.assertIsNone(set_main_account(99999))

    def test_transactions_can_be_tagged_with_an_account(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"],
        )
        add_transactions(
            [{
                "trade_date": "2026-01-06", "symbol": "ITC",
                "transaction_type": "BUY", "quantity": 5, "price": 400,
            }],
        )  # unassigned

        self.assertEqual(len(get_transactions(account_id=broker["id"])), 1)
        self.assertEqual(len(get_transactions()), 2)

    def test_holdings_are_per_account(self):
        broker = find_account_by_name("Main broker")
        personal = find_account_by_name("Main personal")

        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"],
        )
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 4, "price": 2600,
            }],
            account_id=personal["id"],
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 2)
        self.assertEqual(
            {(row.account_id, row.symbol) for row in rebuilt},
            {(broker["id"], "RELIANCE"), (personal["id"], "RELIANCE")},
        )

        broker_rows = get_holdings(account_id=broker["id"])
        self.assertEqual(len(broker_rows), 1)
        self.assertEqual(broker_rows[0]["quantity"], 10)
        self.assertEqual(broker_rows[0]["account_name"], "Main broker")

    def test_set_price_values_the_holding(self):
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
        )
        rebuild_holdings()

        set_price("RELIANCE", 2600.5)
        row = get_holdings()[0]

        self.assertEqual(row["market_value"], 26005.0)
        self.assertEqual(row["profit_loss"], 1005.0)

        # A later price update flows through without a rebuild.
        set_price("RELIANCE", 2400)
        self.assertEqual(get_holdings()[0]["market_value"], 24000.0)

    def test_price_matches_canonical_fno_symbol(self):
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "NIFTY 19150 PE 03 AUG 2023",
                "transaction_type": "BUY", "quantity": 50, "price": 30.3,
            }],
        )
        rebuild_holdings()  # canonicalizes to NIFTY 19150 PE 2023-08-03

        set_price("NIFTY 19150 PE 2023-08-03", 55)
        row = get_holdings()[0]

        self.assertEqual(row["symbol"], "NIFTY 19150 PE 2023-08-03")
        self.assertEqual(row["market_value"], 2750.0)

    def test_unpriced_symbols_keep_zero_valuation(self):
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "ITC",
                "transaction_type": "BUY", "quantity": 5, "price": 400,
            }],
        )
        rebuild_holdings()
        apply_prices_to_holdings()  # no prices at all

        row = get_holdings()[0]
        self.assertEqual(row["market_value"], 0)
        self.assertEqual(row["profit_loss"], 0)

    def test_summary_scopes_to_account(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"],
        )
        add_transactions(
            [{
                "trade_date": "2026-01-06", "symbol": "ITC",
                "transaction_type": "BUY", "quantity": 5, "price": 400,
            }],
        )
        rebuild_holdings()

        scoped = get_portfolio_summary(account_id=broker["id"])
        self.assertEqual(scoped["total_transactions"], 1)
        self.assertEqual(scoped["total_holdings"], 1)
        self.assertEqual(scoped["total_invested"], 25000.0)

        every = get_portfolio_summary()
        self.assertEqual(every["total_transactions"], 2)
        self.assertEqual(every["total_holdings"], 2)

    def test_unassigned_sentinel_filters_accountless_rows(self):
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "ITC",
                "transaction_type": "BUY", "quantity": 5, "price": 400,
            }],
        )  # no account
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-06", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 1, "price": 2500,
            }],
            account_id=broker["id"],
        )
        rebuild_holdings()

        self.assertEqual(
            {row["symbol"] for row in get_transactions(account_id=UNASSIGNED)},
            {"ITC"},
        )
        self.assertEqual(
            {row["symbol"] for row in get_holdings(account_id=UNASSIGNED)},
            {"ITC"},
        )
        summary = get_portfolio_summary(account_id=UNASSIGNED)
        self.assertEqual(summary["total_transactions"], 1)
        self.assertEqual(summary["total_holdings"], 1)
        self.assertEqual(summary["total_invested"], 2000.0)

    def test_prices_roundtrip(self):
        set_price("RELIANCE", 2600.5, source="manual")
        prices = {row["symbol"]: row["price"] for row in get_prices()}

        self.assertEqual(prices["RELIANCE"], 2600.5)
        self.assertEqual(get_prices_paise(), {"RELIANCE": 260050})


class V2ToV3MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "v2.db"

        # Build a genuine v2 database with the old table shapes.
        connection = sqlite3.connect(db.DB_PATH)
        connection.executescript("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            isin TEXT,
            exchange TEXT,
            transaction_type TEXT NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
            quantity REAL NOT NULL,
            price INTEGER NOT NULL DEFAULT 0 CHECK (price >= 0),
            brokerage INTEGER NOT NULL DEFAULT 0 CHECK (brokerage >= 0),
            taxes INTEGER NOT NULL DEFAULT 0 CHECK (taxes >= 0),
            net_amount INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            average_price INTEGER NOT NULL DEFAULT 0,
            invested_amount INTEGER NOT NULL DEFAULT 0,
            market_value INTEGER NOT NULL DEFAULT 0,
            profit_loss INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE dividends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            dividend_date TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            import_type TEXT,
            imported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT
        );
        CREATE TABLE symbol_aliases (
            alias TEXT PRIMARY KEY,
            canonical TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO transactions (trade_date, symbol, transaction_type,
                                  quantity, price, net_amount)
        VALUES ('2026-01-05', 'RELIANCE', 'BUY', 10, 250000, 250000);
        INSERT INTO holdings (symbol, quantity, average_price, invested_amount)
        VALUES ('RELIANCE', 10.0, 250000, 250000);
        """)
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
        connection.close()

    def test_v2_database_upgrades_in_place(self):
        schema.ensure_schema()

        connection = sqlite3.connect(db.DB_PATH)
        connection.row_factory = sqlite3.Row
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertIn("accounts", tables)
        self.assertIn("prices", tables)

        tx_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(transactions)")
        }
        self.assertIn("account_id", tx_columns)

        accounts = list(connection.execute("SELECT name, kind FROM accounts"))
        self.assertEqual(
            [(row["name"], row["kind"]) for row in accounts],
            [("Main broker", "BROKER"), ("Main personal", "PERSONAL")],
        )

        # Pre-existing data survives with account_id NULL (Unassigned).
        row = connection.execute(
            "SELECT symbol, price, account_id FROM transactions"
        ).fetchone()
        self.assertEqual(row["symbol"], "RELIANCE")
        self.assertEqual(row["price"], 250000)
        self.assertIsNone(row["account_id"])
        connection.close()

    def test_upgrade_is_idempotent(self):
        schema.ensure_schema()
        schema.ensure_schema()  # must not raise or duplicate seeds

        self.assertEqual(len(get_accounts()), 2)


if __name__ == "__main__":
    unittest.main()
