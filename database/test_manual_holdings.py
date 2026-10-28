"""Tests for the v4 data layer: account balance editing, manual holdings."""

import sqlite3
import tempfile
import shutil
import unittest
from pathlib import Path

from database import db, schema
from database.manager import (
    add_manual_holding,
    add_transactions,
    delete_manual_holding,
    find_account_by_name,
    get_accounts,
    get_holdings,
    get_manual_holdings,
    rebuild_holdings,
    set_account_balance,
    set_price,
    set_symbol_alias,
)


class V4LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_fresh_database_has_v4_structures(self):
        connection = sqlite3.connect(db.DB_PATH)
        account_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(accounts)")
        }
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()

        self.assertIn("current_balance", account_columns)
        self.assertIn("manual_holdings", tables)
        self.assertEqual(schema.SCHEMA_VERSION, 4)

    def test_set_account_balance_roundtrip(self):
        broker = find_account_by_name("Main broker")

        self.assertTrue(set_account_balance(broker["id"], 125000.50))
        accounts = {row["name"]: row for row in get_accounts()}
        self.assertEqual(accounts["Main broker"]["current_balance"], 125000.50)
        self.assertEqual(accounts["Main personal"]["current_balance"], 0)

    def test_set_account_balance_allows_negative_and_rejects_unknown(self):
        broker = find_account_by_name("Main broker")

        self.assertTrue(set_account_balance(broker["id"], -2500))
        self.assertEqual(
            get_accounts()[0]["current_balance"], -2500.0,
        )
        self.assertFalse(set_account_balance(9999, 100))

    def test_manual_holding_appears_in_rebuilt_cache(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "Tata Motors", 50, 640.25)

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].symbol, "TATA MOTORS")
        self.assertEqual(rebuilt[0].quantity, 50)
        self.assertEqual(rebuilt[0].average_price, 64025)

        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "TATA MOTORS")
        self.assertEqual(rows[0]["quantity"], 50)
        self.assertEqual(rows[0]["average_price"], 640.25)
        self.assertEqual(rows[0]["invested_amount"], 32012.50)
        self.assertEqual(rows[0]["account_name"], "Main broker")

    def test_manual_holding_merges_with_transaction_position(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"],
        )
        add_manual_holding(broker["id"], "RELIANCE", 5, 3000)

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].quantity, 15)
        # (10 x 2500 + 5 x 3000) / 15
        self.assertEqual(rebuilt[0].average_price, 266667)  # paise
        self.assertEqual(rebuilt[0].invested_amount, 4000000)  # paise

    def test_manual_holding_gets_market_value_when_priced(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        set_price("ITC", 420)
        rebuild_holdings()

        row = get_holdings()[0]
        self.assertEqual(row["market_value"], 2100.0)
        self.assertEqual(row["profit_loss"], 100.0)

    def test_manual_symbol_canonicalizes_for_merge(self):
        broker = find_account_by_name("Main broker")
        set_symbol_alias("TELCO", "TATA MOTORS")
        add_manual_holding(broker["id"], "TELCO", 10, 700)

        rebuilt = rebuild_holdings()
        self.assertEqual([row.symbol for row in rebuilt], ["TATA MOTORS"])

        # The manual table keeps the verbatim symbol.
        self.assertEqual(
            get_manual_holdings()[0]["symbol"], "TELCO",
        )

    def test_readd_replaces_manual_entry(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        add_manual_holding(broker["id"], "ITC", 8, 410)

        manual = get_manual_holdings()
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual[0]["quantity"], 8)
        self.assertEqual(manual[0]["average_price"], 410.0)

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].quantity, 8)

    def test_delete_manual_holding_removes_it_from_rebuild(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        manual_id = get_manual_holdings()[0]["id"]

        self.assertTrue(delete_manual_holding(manual_id))
        self.assertEqual(get_manual_holdings(), [])
        self.assertEqual(rebuild_holdings(), [])

        self.assertFalse(delete_manual_holding(manual_id))  # already gone

    def test_add_manual_holding_validates(self):
        broker = find_account_by_name("Main broker")

        with self.assertRaises(ValueError):
            add_manual_holding(broker["id"], "  ", 5, 400)
        with self.assertRaises(ValueError):
            add_manual_holding(broker["id"], "ITC", 0, 400)
        with self.assertRaises(ValueError):
            add_manual_holding(broker["id"], "ITC", -3, 400)
        with self.assertRaises(ValueError):
            add_manual_holding(broker["id"], "ITC", 5, -1)
        with self.assertRaises(ValueError):
            add_manual_holding(9999, "ITC", 5, 400)

    def test_get_manual_holdings_scopes_to_account(self):
        broker = find_account_by_name("Main broker")
        personal = find_account_by_name("Main personal")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        add_manual_holding(personal["id"], "RELIANCE", 1, 2500)

        self.assertEqual(len(get_manual_holdings()), 2)
        broker_rows = get_manual_holdings(account_id=broker["id"])
        self.assertEqual(
            [row["symbol"] for row in broker_rows], ["ITC"],
        )
        self.assertEqual(broker_rows[0]["account_name"], "Main broker")


class V3ToV4MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "v3.db"

        # Build a genuine v3 database: accounts without current_balance,
        # no manual_holdings table.
        connection = sqlite3.connect(db.DB_PATH)
        connection.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK (kind IN ('BROKER', 'PERSONAL')),
            is_main INTEGER NOT NULL DEFAULT 0 CHECK (is_main IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
            account_id INTEGER REFERENCES accounts(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER REFERENCES accounts(id),
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            average_price INTEGER NOT NULL DEFAULT 0 CHECK (average_price >= 0),
            invested_amount INTEGER NOT NULL DEFAULT 0 CHECK (invested_amount >= 0),
            market_value INTEGER NOT NULL DEFAULT 0 CHECK (market_value >= 0),
            profit_loss INTEGER NOT NULL DEFAULT 0,
            UNIQUE (account_id, symbol)
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
        CREATE TABLE prices (
            symbol TEXT PRIMARY KEY,
            price INTEGER NOT NULL CHECK (price >= 0),
            source TEXT NOT NULL DEFAULT 'manual',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO accounts (name, kind, is_main) VALUES ('Main broker', 'BROKER', 1);
        INSERT INTO transactions (trade_date, symbol, transaction_type,
                                  quantity, price, net_amount, account_id)
        VALUES ('2026-01-05', 'RELIANCE', 'BUY', 10, 250000, 250000, 1);
        """)
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
        connection.close()

    def test_v3_database_upgrades_in_place(self):
        schema.ensure_schema()

        connection = sqlite3.connect(db.DB_PATH)
        connection.row_factory = sqlite3.Row
        account_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(accounts)")
        }
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        balance_row = connection.execute(
            "SELECT current_balance FROM accounts WHERE id = 1"
        ).fetchone()
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.close()

        self.assertIn("current_balance", account_columns)
        self.assertIn("manual_holdings", tables)
        self.assertEqual(balance_row["current_balance"], 0)  # defaulted
        self.assertEqual(version, 4)

        # Pre-existing data survives untouched.
        accounts = get_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["transaction_count"], 1)

    def test_upgrade_is_idempotent(self):
        schema.ensure_schema()
        schema.ensure_schema()  # must not raise or duplicate anything

        self.assertEqual(len(get_accounts()), 1)


if __name__ == "__main__":
    unittest.main()
