"""Tests for the v4/v5/v6 data layer: balance editing, manual + report
holdings, account detail fields, and the holdings-constraint repair."""

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
    fill_account_details_if_empty,
    find_account_by_name,
    get_accounts,
    get_holdings,
    get_manual_holdings,
    rebuild_holdings,
    replace_holding_report,
    set_account_balance,
    set_price,
    set_symbol_alias,
    update_account_details,
)


class V5LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_fresh_database_has_v8_structures(self):
        connection = sqlite3.connect(db.DB_PATH)
        account_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(accounts)")
        }
        manual_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(manual_holdings)")
        }
        bank_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(bank_transactions)")
        }
        metadata_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(stock_metadata)")
        }
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()

        self.assertIn("current_balance", account_columns)
        for detail in ("holder_name", "account_number", "phone", "pan", "ucc"):
            self.assertIn(detail, account_columns)
        self.assertIn("manual_holdings", tables)
        self.assertIn("source", manual_columns)
        self.assertIn("bank_transactions", tables)
        for column in ("account_id", "txn_date", "description",
                       "amount", "balance", "source"):
            self.assertIn(column, bank_columns)
        self.assertIn("stock_metadata", tables)
        for column in ("symbol", "sector", "market_cap", "source",
                       "updated_at"):
            self.assertIn(column, metadata_columns)
        self.assertEqual(schema.SCHEMA_VERSION, 8)

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

    def test_add_manual_holding_rejects_unknown_source(self):
        broker = find_account_by_name("Main broker")
        with self.assertRaises(ValueError):
            add_manual_holding(broker["id"], "ITC", 5, 400, source="snacks")

    # ------------------------------------------ holding-report semantics #

    def test_mf_report_and_stock_report_replace_independently(self):
        """Importing one snapshot source never wipes the other's rows."""

        broker = find_account_by_name("Main broker")
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 10, "average_price": 2500}],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "PARAG PARIKH ELSS", "quantity": 60.957,
              "average_price": 32.8}],
            account_id=broker["id"], source="mf_holding_report",
        )

        rebuilt = rebuild_holdings()
        symbols = {row.symbol: row for row in rebuilt}
        self.assertEqual(len(symbols), 2)
        self.assertEqual(symbols["RELIANCE"].quantity, 10)
        self.assertEqual(symbols["PARAG PARIKH ELSS"].quantity, 60.957)

        # A fresher MF report replaces only the MF rows.
        replace_holding_report(
            [{"symbol": "SBI ELSS", "quantity": 4.157, "average_price": 481.1}],
            account_id=broker["id"], source="mf_holding_report",
        )
        rebuilt = rebuild_holdings()
        symbols = {row.symbol for row in rebuilt}
        self.assertEqual(
            symbols,
            {"RELIANCE", "SBI ELSS"},  # Parag Parikh gone, RELIANCE kept
        )

    def test_mf_snapshot_replaces_transaction_position(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "SBI ELSS",
                "transaction_type": "BUY", "quantity": 2, "price": 500,
            }],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "SBI ELSS", "quantity": 4.157,
              "average_price": 481.1}],
            account_id=broker["id"], source="mf_holding_report",
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].quantity, 4.157)  # replaced, not merged

    def test_replace_holding_report_rejects_unknown_source(self):
        broker = find_account_by_name("Main broker")
        with self.assertRaises(ValueError):
            replace_holding_report(
                [{"symbol": "ITC", "quantity": 5, "average_price": 400}],
                account_id=broker["id"], source="snacks",
            )

    def test_holding_report_replaces_transaction_position(self):
        """The broker statement is the authoritative CURRENT position."""

        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 7, "average_price": 3000}],
            account_id=broker["id"],
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].quantity, 7)  # replaced, not merged
        self.assertEqual(rebuilt[0].average_price, 300000)  # paise
        self.assertEqual(rebuilt[0].invested_amount, 2100000)  # paise

    def test_reimport_replaces_previous_report_rows(self):
        """A fresher report cannot leave sold symbols lingering."""

        broker = find_account_by_name("Main broker")
        replace_holding_report(
            [
                {"symbol": "RELIANCE", "quantity": 10, "average_price": 2500},
                {"symbol": "ITC", "quantity": 5, "average_price": 400},
            ],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 8, "average_price": 2600}],
            account_id=broker["id"],
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(
            [(row.symbol, row.quantity) for row in rebuilt],
            [("RELIANCE", 8)],  # ITC vanished with the old report
        )

    def test_manual_rows_survive_a_report_import(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 3, "average_price": 2500}],
            account_id=broker["id"],
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(
            {(row.symbol, row.quantity) for row in rebuilt},
            {("ITC", 5), ("RELIANCE", 3)},
        )

    def test_report_row_replaces_manual_row_for_same_symbol(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        replace_holding_report(
            [{"symbol": "ITC", "quantity": 8, "average_price": 410}],
            account_id=broker["id"],
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].quantity, 8)
        self.assertEqual(rebuilt[0].average_price, 41000)  # paise

        manual = get_manual_holdings()
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual[0]["source"], "holding_report")

    def test_report_scopes_to_its_account(self):
        broker = find_account_by_name("Main broker")
        personal = find_account_by_name("Main personal")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=personal["id"],
        )
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 2, "average_price": 2400}],
            account_id=broker["id"],
        )

        rebuilt = rebuild_holdings()
        by_account = {row.account_id: row for row in rebuilt}
        self.assertEqual(by_account[broker["id"]].quantity, 2)
        self.assertEqual(by_account[personal["id"]].quantity, 10)  # untouched

    def test_replace_holding_report_validates(self):
        broker = find_account_by_name("Main broker")

        with self.assertRaises(ValueError):
            replace_holding_report([], account_id=None)  # no account
        with self.assertRaises(ValueError):
            replace_holding_report([{"symbol": " ", "quantity": 1}], broker["id"])
        with self.assertRaises(ValueError):
            replace_holding_report(
                [{"symbol": "ITC", "quantity": 0, "average_price": 400}],
                broker["id"],
            )
        with self.assertRaises(ValueError):
            replace_holding_report(
                [{"symbol": "ITC", "quantity": 5, "average_price": -1}],
                broker["id"],
            )


class AccountDetailsTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def _account_row(self, name):
        rows = [row for row in get_accounts() if row["name"] == name]
        return rows[0]

    def test_update_account_details_roundtrip(self):
        update_account_details(
            self._account_row("Main broker")["id"],
            holder_name="Demo",
            account_number="1234567890",
            pan="AAAAA0000A",
        )
        row = self._account_row("Main broker")
        self.assertEqual(row["holder_name"], "Demo")
        self.assertEqual(row["account_number"], "1234567890")
        self.assertEqual(row["pan"], "AAAAA0000A")
        # Untouched fields stay empty.
        self.assertEqual(row["phone"] or "", "")
        self.assertEqual(row["ucc"] or "", "")

    def test_update_account_details_partial_and_clearing(self):
        account_id = self._account_row("Main broker")["id"]
        update_account_details(account_id, phone="9876543210", pan="AAAAA0000A")

        # Supplying only one field leaves the others alone.
        update_account_details(account_id, phone="9999999999")
        row = self._account_row("Main broker")
        self.assertEqual(row["phone"], "9999999999")
        self.assertEqual(row["pan"], "AAAAA0000A")

        # Empty string clears a field.
        update_account_details(account_id, phone="")
        row = self._account_row("Main broker")
        self.assertEqual(row["phone"] or "", "")

    def test_update_account_details_values_are_trimmed(self):
        account_id = self._account_row("Main personal")["id"]
        update_account_details(account_id, holder_name="  Nikhil  ")
        self.assertEqual(self._account_row("Main personal")["holder_name"], "Demo")

    def test_update_account_details_unknown_account(self):
        self.assertFalse(update_account_details(99999, pan="AAAAA0000A"))

    def test_fill_account_details_fills_empty_only(self):
        account_id = self._account_row("Main broker")["id"]
        filled = fill_account_details_if_empty(
            account_id, ucc="1234567890", pan="AAAAA0000A",
        )
        self.assertEqual(filled, {"ucc": "1234567890", "pan": "AAAAA0000A"})

        # A second file with different values must not overwrite.
        filled = fill_account_details_if_empty(
            account_id, ucc="0000000000", phone="9876543210",
        )
        self.assertEqual(filled, {"phone": "9876543210"})
        row = self._account_row("Main broker")
        self.assertEqual(row["ucc"], "1234567890")
        self.assertEqual(row["phone"], "9876543210")

    def test_fill_account_details_ignores_unknown_fields_and_blanks(self):
        account_id = self._account_row("Main broker")["id"]
        filled = fill_account_details_if_empty(
            account_id, not_a_field="x", pan=None, ucc="   ",
        )
        self.assertEqual(filled, {})

    def test_fill_account_details_unknown_account(self):
        self.assertEqual(
            fill_account_details_if_empty(99999, pan="AAAAA0000A"), {},
        )


class HoldingsConstraintRepairTests(unittest.TestCase):
    """Databases migrated from the pre-account era can carry a holdings
    table with UNIQUE(symbol) only; ensure_schema must rebuild it."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "stale.db"
        schema.ensure_schema()

        # Degrade the holdings table to the pre-v3 shape: symbol-only
        # uniqueness with account_id tacked on by ALTER, exactly like the
        # live database carried for months.
        connection = sqlite3.connect(db.DB_PATH)
        connection.executescript("""
        CREATE TABLE holdings_old (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            average_price INTEGER NOT NULL DEFAULT 0,
            invested_amount INTEGER NOT NULL DEFAULT 0,
            market_value INTEGER NOT NULL DEFAULT 0,
            profit_loss INTEGER NOT NULL DEFAULT 0,
            account_id INTEGER REFERENCES accounts(id)
        );
        INSERT INTO holdings_old (symbol, quantity, average_price,
            invested_amount, market_value, profit_loss)
        VALUES ('PNB', 20, 6202, 124040, 0, 0);
        DROP TABLE holdings;
        ALTER TABLE holdings_old RENAME TO holdings;
        """)
        connection.commit()
        connection.close()

    def _unique_index_columns(self):
        connection = sqlite3.connect(db.DB_PATH)
        try:
            found = []
            for index in connection.execute("PRAGMA index_list(holdings)"):
                if not index[2]:  # not unique
                    continue
                columns = [
                    row[2] for row in connection.execute(
                        f"PRAGMA index_info({index[1]})"
                    )
                ]
                found.append(columns)
            return found
        finally:
            connection.close()

    def test_stale_holdings_table_gets_composite_constraint(self):
        # Before the repair runs, uniqueness is symbol-only.
        self.assertIn(["symbol"], self._unique_index_columns())

        schema.ensure_schema()

        self.assertIn(["account_id", "symbol"], self._unique_index_columns())
        self.assertNotIn(["symbol"], self._unique_index_columns())

    def test_repair_preserves_rows_and_allows_same_symbol_two_accounts(self):
        connection = sqlite3.connect(db.DB_PATH)
        connection.execute(
            "INSERT INTO accounts (name, kind) VALUES ('A', 'BROKER')"
        )
        connection.execute(
            "INSERT INTO accounts (name, kind) VALUES ('B', 'PERSONAL')"
        )
        connection.commit()
        connection.close()

        schema.ensure_schema()

        # Rows survived the rebuild.
        connection = sqlite3.connect(db.DB_PATH)
        rows = connection.execute(
            "SELECT symbol, quantity FROM holdings ORDER BY symbol"
        ).fetchall()
        connection.close()
        self.assertEqual(
            [(row[0], row[1]) for row in rows], [("PNB", 20.0)],
        )

        # Two accounts may now hold the same symbol...
        from database.manager import add_transactions, rebuild_holdings
        accounts = {row["name"]: row["id"] for row in get_accounts()}
        add_transactions([{
            "trade_date": "2026-10-29", "symbol": "PNB",
            "transaction_type": "BUY", "quantity": 1, "price": 100,
        }], account_id=accounts["A"])
        add_transactions([{
            "trade_date": "2026-10-29", "symbol": "PNB",
            "transaction_type": "BUY", "quantity": 2, "price": 101,
        }], account_id=accounts["B"])
        rebuilt = rebuild_holdings()
        pnb_rows = [row for row in rebuilt if row.symbol == "PNB"]
        self.assertEqual(len(pnb_rows), 2)
        self.assertEqual(
            {row.account_id for row in pnb_rows},
            {accounts["A"], accounts["B"]},
        )

    def test_repair_is_idempotent(self):
        schema.ensure_schema()
        schema.ensure_schema()  # must not raise or duplicate anything
        self.assertIn(["account_id", "symbol"], self._unique_index_columns())


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
        # The v3 database upgrades all the way through v4 to the current
        # version in one pass.
        self.assertEqual(version, schema.SCHEMA_VERSION)

        # Pre-existing data survives untouched.
        accounts = get_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["transaction_count"], 1)

    def test_upgrade_is_idempotent(self):
        schema.ensure_schema()
        schema.ensure_schema()  # must not raise or duplicate anything

        self.assertEqual(len(get_accounts()), 1)


class V4ToV5MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "v4.db"

        # Build a genuine v4 database: manual_holdings without a source
        # column.
        connection = sqlite3.connect(db.DB_PATH)
        connection.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK (kind IN ('BROKER', 'PERSONAL')),
            is_main INTEGER NOT NULL DEFAULT 0 CHECK (is_main IN (0, 1)),
            current_balance INTEGER NOT NULL DEFAULT 0,
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
        CREATE TABLE manual_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL CHECK (quantity > 0),
            average_price INTEGER NOT NULL DEFAULT 0 CHECK (average_price >= 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (account_id, symbol)
        );
        INSERT INTO accounts (name, kind, is_main) VALUES ('Main broker', 'BROKER', 1);
        INSERT INTO manual_holdings (account_id, symbol, quantity, average_price)
        VALUES (1, 'ITC', 5, 40000);
        """)
        connection.execute("PRAGMA user_version = 4")
        connection.commit()
        connection.close()

    def test_v4_database_upgrades_in_place(self):
        schema.ensure_schema()

        # The pre-existing manual row survives, defaulted to 'manual'.
        manual = get_manual_holdings()
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual[0]["symbol"], "ITC")
        self.assertEqual(manual[0]["source"], "manual")

        connection = sqlite3.connect(db.DB_PATH)
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.close()
        self.assertEqual(version, schema.SCHEMA_VERSION)

        # The defaulted rows merge additively, exactly as before v5.
        rebuilt = rebuild_holdings()
        self.assertEqual(
            [(row.symbol, row.quantity) for row in rebuilt],
            [("ITC", 5)],
        )

    def test_upgrade_is_idempotent(self):
        schema.ensure_schema()
        schema.ensure_schema()  # must not raise or duplicate anything

        self.assertEqual(len(get_manual_holdings()), 1)


if __name__ == "__main__":
    unittest.main()
