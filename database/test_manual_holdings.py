"""Tests for the v4/v5/v6 data layer: balance editing, manual + report
holdings, account detail fields, and the holdings-constraint repair."""

import sqlite3
import tempfile
import shutil
import unittest
from pathlib import Path

from database import db, schema
from database.manager import (
    UNASSIGNED,
    add_bank_transactions,
    add_import,
    add_manual_holding,
    add_transactions,
    delete_holding,
    delete_import,
    delete_manual_holding,
    fill_account_details_if_empty,
    find_account_by_name,
    get_accounts,
    get_holdings,
    get_import_row_counts,
    get_imports,
    get_manual_holdings,
    get_transactions,
    move_holding,
    rebuild_holdings,
    replace_holding_report,
    set_account_balance,
    set_price,
    set_symbol_alias,
    update_account_details,
    update_manual_holding,
)


class V5LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        db.DB_PATH = self.temp / "scratch.db"
        schema.ensure_schema()

    def test_fresh_database_has_v9_structures(self):
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
        transaction_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(transactions)")
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
        # v9: every data table carries the import link column.
        for columns in (transaction_columns, bank_columns, manual_columns):
            self.assertIn("import_id", columns)
        self.assertEqual(schema.SCHEMA_VERSION, 9)

    def test_upgrade_to_v9_adds_import_id_columns(self):
        """A v8 database (no import_id columns) gains them in place."""

        connection = sqlite3.connect(db.DB_PATH)
        for table in ("transactions", "bank_transactions", "manual_holdings"):
            connection.execute(f"ALTER TABLE {table} DROP COLUMN import_id")
        connection.execute("PRAGMA user_version = 8")
        connection.commit()
        connection.close()

        schema.ensure_schema()

        connection = sqlite3.connect(db.DB_PATH)
        try:
            for table in ("transactions", "bank_transactions",
                          "manual_holdings"):
                columns = {
                    row[1] for row in connection.execute(
                        f"PRAGMA table_info({table})"
                    )
                }
                self.assertIn("import_id", columns)
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                schema.SCHEMA_VERSION,
            )
        finally:
            connection.close()

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

    # -------------------------------------------------- edit + move tests #

    def test_update_manual_holding_roundtrip(self):
        broker = find_account_by_name("Main broker")
        personal = find_account_by_name("Main personal")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        manual_id = get_manual_holdings()[0]["id"]

        self.assertTrue(update_manual_holding(
            manual_id, personal["id"], "itc ltd ", "12", "355.5",
        ))

        rows = get_manual_holdings(account_id=personal["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "ITC LTD")
        self.assertEqual(rows[0]["quantity"], 12)
        self.assertEqual(rows[0]["average_price"], 355.50)
        self.assertEqual(rows[0]["account_name"], "Main personal")
        self.assertEqual(get_manual_holdings(account_id=broker["id"]), [])

        # The edited row drives the rebuilt cache.
        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].account_id, personal["id"])
        self.assertEqual(rebuilt[0].quantity, 12)

    def test_update_manual_holding_missing_id_and_validation(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        manual_id = get_manual_holdings()[0]["id"]

        self.assertFalse(update_manual_holding(
            99999, broker["id"], "ITC", 5, 400,
        ))
        with self.assertRaises(ValueError):
            update_manual_holding(manual_id, broker["id"], "  ", 5, 400)
        with self.assertRaises(ValueError):
            update_manual_holding(manual_id, broker["id"], "ITC", 0, 400)
        with self.assertRaises(ValueError):
            update_manual_holding(manual_id, broker["id"], "ITC", 5, -1)
        with self.assertRaises(ValueError):
            update_manual_holding(manual_id, 9999, "ITC", 5, 400)

    def test_update_manual_holding_rejects_duplicate_symbol(self):
        broker = find_account_by_name("Main broker")
        add_manual_holding(broker["id"], "ITC", 5, 400)
        add_manual_holding(broker["id"], "RELIANCE", 1, 2500)
        rows = get_manual_holdings()
        itc_id = next(row["id"] for row in rows if row["symbol"] == "ITC")

        # Editing ITC into RELIANCE would collide with the other row.
        with self.assertRaises(ValueError):
            update_manual_holding(itc_id, broker["id"], "RELIANCE", 5, 400)

        # Same symbol but a different account is fine.
        personal = find_account_by_name("Main personal")
        self.assertTrue(update_manual_holding(
            itc_id, personal["id"], "RELIANCE", 5, 400,
        ))

    def test_move_holding_retags_transactions_and_manual_rows(self):
        broker = find_account_by_name("Main broker")
        personal = find_account_by_name("Main personal")
        add_transactions([{
            "trade_date": "2026-01-05", "symbol": "RELIANCE",
            "transaction_type": "BUY", "quantity": 10, "price": 2500,
        }], account_id=broker["id"])
        add_manual_holding(broker["id"], "RELIANCE", 2, 2600)

        moved = move_holding(broker["id"], "Reliance", personal["id"])
        self.assertEqual(moved, 2)  # 1 transaction + 1 manual row

        rebuild_holdings()
        rows = get_holdings(account_id=personal["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "RELIANCE")
        # 10 bought + 2 manual merged into one position.
        self.assertEqual(rows[0]["quantity"], 12)
        self.assertEqual(get_holdings(account_id=broker["id"]), [])

    def test_move_holding_moves_unassigned_rows(self):
        add_transactions([{
            "trade_date": "2026-01-05", "symbol": "VEDANTA",
            "transaction_type": "BUY", "quantity": 4, "price": 300,
        }])
        broker = find_account_by_name("Main broker")

        moved = move_holding(None, "VEDANTA", broker["id"])
        self.assertEqual(moved, 1)

        rebuild_holdings()
        rows = get_holdings(account_id=broker["id"])
        self.assertEqual(
            [row["symbol"] for row in rows], ["VEDANTA"],
        )
        self.assertEqual(get_holdings(account_id=UNASSIGNED), [])

    def test_move_holding_missing_target_and_same_account(self):
        broker = find_account_by_name("Main broker")

        self.assertIsNone(move_holding(broker["id"], "ITC", 99999))
        self.assertEqual(move_holding(broker["id"], "ITC", broker["id"]), 0)

    def test_delete_holding_keeps_history_behind_a_snapshot(self):
        broker = find_account_by_name("Main broker")
        add_transactions([{
            "trade_date": "2026-01-05", "symbol": "PUNJAB NATIONAL BANK",
            "transaction_type": "BUY", "quantity": 10, "price": 100,
        }], account_id=broker["id"])
        replace_holding_report(
            [
                {"symbol": "PUNJAB NATIONAL BANK", "quantity": 3,
                 "average_price": 108},
                {"symbol": "ITC", "quantity": 5, "average_price": 400},
            ],
            account_id=broker["id"],
        )
        rebuild_holdings()
        self.assertEqual(len(get_holdings(account_id=broker["id"])), 2)

        manual_rows, transaction_rows = delete_holding(
            broker["id"], "punjab national bank",
        )
        self.assertEqual((manual_rows, transaction_rows), (1, 0))

        rebuild_holdings()
        rows = get_holdings(account_id=broker["id"])
        self.assertEqual([row["symbol"] for row in rows], ["ITC"])
        # The trade history behind the deleted statement row survives.
        self.assertEqual(len(get_transactions(account_id=broker["id"])), 1)

    def test_delete_holding_removes_transaction_derived_position(self):
        broker = find_account_by_name("Main broker")
        add_transactions([{
            "trade_date": "2026-01-05", "symbol": "VEDANTA",
            "transaction_type": "BUY", "quantity": 4, "price": 300,
        }], account_id=broker["id"])
        rebuild_holdings()
        self.assertEqual(len(get_holdings(account_id=broker["id"])), 1)

        manual_rows, transaction_rows = delete_holding(
            broker["id"], "vedanta",
        )
        self.assertEqual((manual_rows, transaction_rows), (0, 1))

        rebuild_holdings()
        self.assertEqual(get_holdings(account_id=broker["id"]), [])
        self.assertEqual(get_transactions(account_id=broker["id"]), [])

    def test_delete_holding_empty_symbol_and_unknown_account(self):
        with self.assertRaises(ValueError):
            delete_holding(None, "   ")
        # Nothing matches: no error, just zero rows everywhere.
        self.assertEqual(delete_holding(99999, "ITC"), (0, 0))

    # ------------------------------------------------- import tagging #

    def test_import_id_tags_rows_and_delete_import_removes_them(self):
        """Every importer-inserted row carries its audit id; Remove works."""

        broker = find_account_by_name("Main broker")
        import_id = add_import("statement.pdf", "CONTRACT_NOTE_PDF", "PENDING")

        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "RELIANCE",
                "transaction_type": "BUY", "quantity": 10, "price": 2500,
            }],
            account_id=broker["id"], import_id=import_id,
        )
        add_bank_transactions(
            [{
                "txn_date": "2026-01-06", "description": "UPI/food",
                "amount": -250.0, "balance": 1000.0,
            }],
            account_id=broker["id"], import_id=import_id,
        )
        replace_holding_report(
            [{"symbol": "ITC", "quantity": 5, "average_price": 400}],
            account_id=broker["id"], import_id=import_id,
        )

        # Untagged rows are invisible to the import's counts.
        add_transactions(
            [{
                "trade_date": "2026-01-07", "symbol": "TATASTEEL",
                "transaction_type": "BUY", "quantity": 1, "price": 100,
            }],
            account_id=broker["id"],
        )
        self.assertEqual(get_import_row_counts(import_id), {
            "transactions": 1,
            "bank_transactions": 1,
            "manual_holdings": 1,
        })

        counts = delete_import(import_id)
        self.assertEqual(counts, {
            "transactions": 1,
            "bank_transactions": 1,
            "manual_holdings": 1,
            "imports": 1,
        })
        self.assertEqual(get_import_row_counts(import_id), {})
        self.assertEqual(
            [row["id"] for row in get_imports() if row["id"] == import_id],
            [],
        )
        # Rows imported by other means are untouched.
        symbols = {row["symbol"] for row in get_transactions()}
        self.assertEqual(symbols, {"TATASTEEL"})

    def test_delete_import_unknown_id_is_harmless(self):
        self.assertEqual(delete_import(99999), {
            "transactions": 0,
            "bank_transactions": 0,
            "manual_holdings": 0,
            "imports": 0,
        })

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

    def test_us_report_replaces_only_its_own_symbols(self):
        """A US statement says nothing about the account's Indian stocks."""

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
                "trade_date": "2026-01-06", "symbol": "AAPL",
                "transaction_type": "BUY", "quantity": 2, "price": 15000,
            }],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "AAPL", "quantity": 3, "average_price": 14500}],
            account_id=broker["id"], source="us_holding_report",
        )

        rebuilt = rebuild_holdings()
        by_symbol = {row.symbol: row for row in rebuilt}
        # The US snapshot replaced the AAPL transaction position...
        self.assertEqual(by_symbol["AAPL"].quantity, 3)
        self.assertEqual(by_symbol["AAPL"].average_price, 1450000)  # paise
        # ...but the Indian transaction-derived position survives.
        self.assertEqual(by_symbol["RELIANCE"].quantity, 10)

    def test_bond_report_replaces_transaction_position(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-05", "symbol": "NHAI BOND",
                "transaction_type": "BUY", "quantity": 10, "price": 1000,
            }],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "NHAI BOND", "quantity": 12, "average_price": 995}],
            account_id=broker["id"], source="bond_holding_report",
        )

        rebuilt = rebuild_holdings()
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].quantity, 12)

    def test_us_and_stock_reports_replace_independently(self):
        """Re-importing one asset class never wipes another's snapshot."""

        broker = find_account_by_name("Main broker")
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 10, "average_price": 2500}],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "AAPL", "quantity": 2, "average_price": 15000}],
            account_id=broker["id"], source="us_holding_report",
        )

        # A fresher US report leaves the Indian snapshot untouched, and
        # replaces the US snapshot wholesale (AAPL is no longer listed).
        replace_holding_report(
            [{"symbol": "MSFT", "quantity": 1, "average_price": 20000}],
            account_id=broker["id"], source="us_holding_report",
        )

        rebuilt = rebuild_holdings()
        by_symbol = {row.symbol: row for row in rebuilt}
        self.assertEqual(by_symbol["RELIANCE"].quantity, 10)
        self.assertEqual(by_symbol["MSFT"].quantity, 1)
        self.assertNotIn("AAPL", by_symbol)

    def test_delete_holding_behind_a_us_snapshot_keeps_history(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [{
                "trade_date": "2026-01-06", "symbol": "AAPL",
                "transaction_type": "BUY", "quantity": 2, "price": 15000,
            }],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "AAPL", "quantity": 3, "average_price": 14500}],
            account_id=broker["id"], source="us_holding_report",
        )

        manual_deleted, transaction_deleted = delete_holding(
            broker["id"], "AAPL",
        )

        self.assertEqual(manual_deleted, 1)
        self.assertEqual(transaction_deleted, 0)  # trade history survives

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

    def test_statement_drops_stale_transaction_positions(self):
        """A stock statement governs its account: unlisted positions drop."""
        broker = find_account_by_name("Main broker")
        add_transactions(
            [
                {
                    "trade_date": "2026-01-05", "symbol": "RELIANCE",
                    "transaction_type": "BUY", "quantity": 10, "price": 2500,
                },
                {
                    "trade_date": "2026-01-06", "symbol": "ITC",
                    "transaction_type": "BUY", "quantity": 5, "price": 400,
                },
                {
                    "trade_date": "2026-01-07", "symbol": "BANKNIFTY 45000 CE 2026-01-29",
                    "transaction_type": "BUY", "quantity": 25, "price": 100,
                },
            ],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "RELIANCE", "quantity": 10, "average_price": 2500}],
            account_id=broker["id"],
        )
        rebuild_holdings()

        rows = get_holdings(account_id=broker["id"])
        # ITC and the F&O contract are not in the statement: sold outside
        # the imported files, so only RELIANCE remains as a holding.
        self.assertEqual([row["symbol"] for row in rows], ["RELIANCE"])
        # The dropped positions stay as transaction history.
        self.assertEqual(len(get_transactions(account_id=broker["id"])), 3)

    def test_mf_statement_governs_only_fund_positions(self):
        broker = find_account_by_name("Main broker")
        add_transactions(
            [
                {
                    "trade_date": "2026-01-05", "symbol": "RELIANCE",
                    "transaction_type": "BUY", "quantity": 10, "price": 2500,
                },
                {
                    "trade_date": "2026-01-06",
                    "symbol": "SBI ELSS TAX SAVER FUND DIRECT GROWTH",
                    "transaction_type": "BUY", "quantity": 2, "price": 500,
                },
            ],
            account_id=broker["id"],
        )
        replace_holding_report(
            [{"symbol": "SBI ELSS TAX SAVER FUND DIRECT GROWTH",
              "quantity": 4, "average_price": 480}],
            account_id=broker["id"],
            source="mf_holding_report",
        )
        rebuild_holdings()

        rows = get_holdings(account_id=broker["id"])
        symbols = {row["symbol"] for row in rows}
        # The fund statement governs funds only; the stock position is
        # untouched because no stock statement exists for the account.
        self.assertEqual(symbols, {"RELIANCE",
                                   "SBI ELSS TAX SAVER FUND DIRECT GROWTH"})

    def test_manual_position_survives_statement_governance(self):
        broker = find_account_by_name("Main broker")
        add_transactions([{
            "trade_date": "2026-01-05", "symbol": "RELIANCE",
            "transaction_type": "BUY", "quantity": 10, "price": 2500,
        }], account_id=broker["id"])
        replace_holding_report(
            [{"symbol": "ITC", "quantity": 5, "average_price": 400}],
            account_id=broker["id"],
        )
        add_manual_holding(broker["id"], "TATASTEEL", 5, 100)
        rebuild_holdings()

        rows = get_holdings(account_id=broker["id"])
        symbols = {row["symbol"] for row in rows}
        # The hand-added position is user intent; only the unlisted
        # transaction-derived RELIANCE drops out.
        self.assertEqual(symbols, {"ITC", "TATASTEEL"})

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
        update_account_details(account_id, holder_name="  Demo  ")
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
