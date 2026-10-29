"""Tests for bank-statement storage (schema v7 bank_transactions)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    add_bank_transactions,
    count_bank_transactions,
    find_account_by_name,
    get_accounts,
    get_bank_transactions,
    set_account_balance,
)
from database.schema import ensure_schema


def _row(date_text, description, amount, balance):
    return {
        "txn_date": date_text,
        "description": description,
        "amount": amount,
        "balance": balance,
    }


class BankTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "p.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

        self.personal = find_account_by_name("Main personal")

    def test_add_and_get_roundtrip_in_rupees(self):
        imported, duplicates = add_bank_transactions(
            [
                _row("2025-08-18", "UPI/P2M/1/SHOP", -50.0, 950.0),
                _row("2025-08-19", "UPI/CR/2/REFUND", 2.0, 952.0),
            ],
            account_id=self.personal["id"],
        )

        self.assertEqual((imported, duplicates), (2, 0))
        rows = get_bank_transactions(account_id=self.personal["id"])
        self.assertEqual([row["description"] for row in rows],
                         ["UPI/P2M/1/SHOP", "UPI/CR/2/REFUND"])
        self.assertEqual(rows[0]["amount"], -50.0)
        self.assertEqual(rows[0]["balance"], 950.0)
        self.assertEqual(rows[1]["amount"], 2.0)

    def test_reimport_is_idempotent(self):
        rows = [
            _row("2025-08-18", "UPI/P2M/1/SHOP", -50.0, 950.0),
            _row("2025-08-19", "UPI/CR/2/REFUND", 2.0, 952.0),
        ]
        add_bank_transactions(rows, account_id=self.personal["id"])

        imported, duplicates = add_bank_transactions(
            rows, account_id=self.personal["id"],
        )
        self.assertEqual((imported, duplicates), (0, 2))
        self.assertEqual(
            count_bank_transactions(account_id=self.personal["id"]), 2,
        )

    def test_overlapping_period_imports_only_new_rows(self):
        add_bank_transactions(
            [
                _row("2025-08-18", "UPI/P2M/1/SHOP", -50.0, 950.0),
                _row("2025-08-19", "UPI/CR/2/REFUND", 2.0, 952.0),
            ],
            account_id=self.personal["id"],
        )
        imported, duplicates = add_bank_transactions(
            [
                # same line as before (overlapping period)...
                _row("2025-08-19", "UPI/CR/2/REFUND", 2.0, 952.0),
                # ...plus a genuinely new one
                _row("2025-08-20", "UPI/P2M/3/TEA", -30.0, 922.0),
            ],
            account_id=self.personal["id"],
        )
        self.assertEqual((imported, duplicates), (1, 1))
        self.assertEqual(
            count_bank_transactions(account_id=self.personal["id"]), 3,
        )

    def test_same_description_different_amount_both_stored(self):
        add_bank_transactions(
            [
                _row("2025-08-18", "UPI WDR 111", -500.0, 500.0),
                _row("2025-08-18", "UPI WDR 111", -300.0, 200.0),
            ],
            account_id=self.personal["id"],
        )
        self.assertEqual(
            count_bank_transactions(account_id=self.personal["id"]), 2,
        )

    def test_requires_an_existing_account(self):
        with self.assertRaises(ValueError):
            add_bank_transactions(
                [_row("2025-08-18", "X", -1.0, 1.0)],
                account_id=99999,
            )

    def test_rejects_zero_amount_and_blank_description(self):
        with self.assertRaises(ValueError):
            add_bank_transactions(
                [_row("2025-08-18", "X", 0.0, 1.0)],
                account_id=self.personal["id"],
            )
        with self.assertRaises(ValueError):
            add_bank_transactions(
                [_row("2025-08-18", "   ", -1.0, 1.0)],
                account_id=self.personal["id"],
            )

    def test_closing_balance_updates_the_account(self):
        set_account_balance(self.personal["id"], 2859.07)
        accounts = {row["name"]: row for row in get_accounts()}
        self.assertEqual(accounts["Main personal"]["current_balance"], 2859.07)

    def test_unfiltered_get_spans_accounts(self):
        broker = find_account_by_name("Main broker")
        add_bank_transactions(
            [_row("2025-08-18", "A", -1.0, 1.0)],
            account_id=self.personal["id"],
        )
        add_bank_transactions(
            [_row("2025-08-19", "B", 1.0, 2.0)],
            account_id=broker["id"],
        )
        rows = get_bank_transactions()
        self.assertEqual([row["description"] for row in rows], ["A", "B"])
        self.assertEqual(
            {row["account_name"] for row in rows},
            {"Main personal", "Main broker"},
        )


if __name__ == "__main__":
    unittest.main()
