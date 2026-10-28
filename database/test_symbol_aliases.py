"""Tests for symbol aliasing (cross-source symbol identity).

The same company arrives under different verbatim names from different
sources (VEDANTA vs VEDANTA LIMITED, PUNJ. NATIONLBAK vs PUNJAB NATIONAL
BANK). Aliases merge them at holdings-aggregation time while transactions
keep their verbatim symbols.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    add_transaction,
    canonical_symbol,
    delete_symbol_alias,
    get_holdings,
    get_symbol_aliases,
    rebuild_holdings,
    set_symbol_alias,
)
from database.schema import ensure_schema


class SymbolAliasTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "portfoliox.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def test_set_get_and_delete_alias(self):
        set_symbol_alias("vedanta limited", "VEDANTA")

        aliases = get_symbol_aliases()
        self.assertEqual(len(aliases), 1)
        self.assertEqual(aliases[0]["alias"], "VEDANTA LIMITED")
        self.assertEqual(aliases[0]["canonical"], "VEDANTA")

        delete_symbol_alias("VEDANTA LIMITED")
        self.assertEqual(get_symbol_aliases(), [])

    def test_canonical_symbol_resolves_case_insensitively(self):
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")

        self.assertEqual(canonical_symbol("vedanta Limited"), "VEDANTA")
        self.assertEqual(canonical_symbol("TATASTEEL"), "TATASTEEL")
        self.assertEqual(canonical_symbol(None), "")

    def test_self_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot map to itself"):
            set_symbol_alias("VEDANTA", "VEDANTA")

    def test_alias_chains_rejected(self):
        # A chain needs a symbol to be both a canonical target and an
        # alias key: PUNJ. NATIONLBAK -> PNB already exists, so mapping
        # PNB itself onto something else would resolve in two hops.
        set_symbol_alias("PUNJ. NATIONLBAK", "PNB")

        with self.assertRaisesRegex(ValueError, "no chains"):
            set_symbol_alias("PNB", "PUNJAB NATIONAL BANK")

    def test_empty_names_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            set_symbol_alias("  ", "VEDANTA")

    def test_transactions_keep_verbatim_symbols(self):
        add_transaction("2023-07-03", "VEDANTA LIMITED", None, "NSE",
                        "BUY", 4, 279.1)
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")

        rebuild_holdings()

        transactions = db.fetch_all("SELECT symbol FROM transactions")
        self.assertEqual(transactions[0]["symbol"], "VEDANTA LIMITED")

    def test_rebuild_merges_variant_symbols_into_one_holding(self):
        # The real cross-source situation: 17 shares hand-entered as
        # VEDANTA, 4 shares imported from IIFL as VEDANTA LIMITED.
        add_transaction("2023-07-03", "VEDANTA", None, None, "BUY", 17, 279.1)
        add_transaction("2022-06-27", "VEDANTA LIMITED", None, "NSECASH",
                        "BUY", 4, 279.1)
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")

        rebuild_holdings()

        holdings = get_holdings()
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0]["symbol"], "VEDANTA")
        self.assertEqual(holdings[0]["quantity"], 21.0)

    def test_rebuild_merges_buys_with_sells_across_names(self):
        # A buy under one name and a sell under the other must net out
        # instead of tripping the oversell check.
        add_transaction("2023-07-03", "COAL INDIA LTD", None, None, "BUY", 4, 233.05)
        add_transaction("2023-07-10", "COAL INDIA LTD.", None, None, "SELL", 1, 240.0)
        set_symbol_alias("COAL INDIA LTD.", "COAL INDIA LTD")

        rebuild_holdings()

        holdings = get_holdings()
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0]["quantity"], 3.0)

    def test_alias_repointing_changes_next_rebuild(self):
        add_transaction("2023-07-03", "VEDANTA LIMITED", None, None, "BUY", 4, 279.1)
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")
        rebuild_holdings()
        self.assertEqual(get_holdings()[0]["symbol"], "VEDANTA")

        set_symbol_alias("VEDANTA LIMITED", "VEDLTD")
        rebuild_holdings()
        self.assertEqual(get_holdings()[0]["symbol"], "VEDLTD")


if __name__ == "__main__":
    unittest.main()