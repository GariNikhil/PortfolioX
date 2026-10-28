"""Tests for the shared importer helpers (dedup-key canonicalization)."""

import unittest

from database.manager import add_transaction, rebuild_holdings, set_symbol_alias
from importers.common import (
    _split_oversells,
    canonical_trade_symbol,
    existing_trade_keys,
    trade_key,
)
from importers.support import ScratchDbTestCase


def _row(symbol, side="BUY", quantity=17, price=279.10,
         trade_date="2023-07-03"):
    return {
        "trade_date": trade_date,
        "symbol": symbol,
        "transaction_type": side,
        "quantity": quantity,
        "price": price,
    }


class CanonicalTradeSymbolTests(ScratchDbTestCase):
    def test_alias_maps_verbatim_variants_to_one_name(self):
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")

        self.assertEqual(
            canonical_trade_symbol("VEDANTA"),
            canonical_trade_symbol("VEDANTA LIMITED"),
        )

    def test_fno_expiry_spellings_share_one_name(self):
        self.assertEqual(
            canonical_trade_symbol("BANKNIFTY 45500 PE 27 Jul 2023"),
            canonical_trade_symbol("BANKNIFTY 45500 PE 2023-07-27"),
        )

    def test_unknown_symbol_passes_through_uppercased(self):
        self.assertEqual(canonical_trade_symbol("reliance"), "RELIANCE")


class TradeKeyTests(ScratchDbTestCase):
    def test_same_trade_under_different_verbatim_names_shares_key(self):
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")

        self.assertEqual(
            trade_key(_row("VEDANTA")),
            trade_key(_row("VEDANTA LIMITED")),
        )

    def test_different_price_stays_a_different_trade(self):
        self.assertNotEqual(
            trade_key(_row("VEDANTA", price=279.10)),
            trade_key(_row("VEDANTA", price=279.20)),
        )

    def test_existing_trade_keys_canonicalizes_stored_rows(self):
        # The live-database failure mode: the same trade stored once as
        # 'VEDANTA LIMITED' (snapshot import) and re-imported as 'VEDANTA'
        # (contract note) used to produce two different keys, so both rows
        # landed in the database and the holding doubled.
        set_symbol_alias("VEDANTA LIMITED", "VEDANTA")
        add_transaction(
            "2023-07-03", "VEDANTA LIMITED", None, "NSE", "BUY", 17, 279.10,
        )

        self.assertIn(trade_key(_row("VEDANTA")), existing_trade_keys())


class SplitOversellsTests(ScratchDbTestCase):
    def test_sell_canonicalizes_against_holding_name(self):
        # A holding stored as 'PNB' (the alias target) must cover a note
        # selling 'PUNJAB NATIONAL BANK'; verbatim matching rejected it.
        set_symbol_alias("PUNJ. NATIONLBAK", "PNB")
        set_symbol_alias("PUNJAB NATIONAL BANK", "PNB")
        add_transaction(
            "2023-07-13", "PUNJ. NATIONLBAK", None, "NSE", "BUY", 20, 61.80,
        )
        rebuild_holdings()

        pending = [
            _row("PUNJAB NATIONAL BANK", side="SELL", quantity=20,
                 price=62.80, trade_date="2023-07-18"),
        ]
        insertable, oversells = _split_oversells(pending)

        self.assertEqual(oversells, [])
        self.assertEqual(len(insertable), 1)

    def test_same_day_sell_first_roundtrip_is_reordered_not_rejected(self):
        # Real note 1234567890-9 (Zomato, 2023-07-24): sells listed before
        # the same-day buys. Net zero, so nothing is oversold - the rows
        # only need buy-first ordering for the (date, id) rebuild.
        pending = [
            _row("ZOMATO LIMITED", side="BUY", quantity=200, price=81.85),
            _row("ZOMATO LIMITED", side="SELL", quantity=200, price=81.75),
            _row("ZOMATO LIMITED", side="SELL", quantity=10, price=81.70),
            _row("ZOMATO LIMITED", side="BUY", quantity=10, price=81.65),
            _row("ZOMATO LIMITED", side="SELL", quantity=51, price=81.70),
            _row("ZOMATO LIMITED", side="BUY", quantity=21, price=81.70),
            _row("ZOMATO LIMITED", side="BUY", quantity=30, price=81.70),
        ]
        insertable, oversells = _split_oversells(pending)

        self.assertEqual(oversells, [])
        self.assertEqual(len(insertable), 7)
        sides = [row["transaction_type"] for row in insertable]
        self.assertEqual(sides, ["BUY"] * 4 + ["SELL"] * 3)

    def test_genuine_oversell_still_rejected(self):
        pending = [
            _row("RELIANCE", side="SELL", quantity=10, price=2500.0),
        ]
        insertable, oversells = _split_oversells(pending)

        self.assertEqual(insertable, [])
        self.assertEqual(len(oversells), 1)
        row, held = oversells[0]
        self.assertEqual(row["symbol"], "RELIANCE")
        self.assertEqual(held, 0.0)


if __name__ == "__main__":
    unittest.main()
