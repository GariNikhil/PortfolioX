"""Tests for the display formatting helpers (no Tk required)."""

import unittest

from ui.formatting import format_quantity, format_rupees, kpi_cards


class FormatRupeesTests(unittest.TestCase):
    def test_indian_grouping(self):
        # 1,23,45,678.90 - first comma after 3 digits, then every 2.
        self.assertEqual(format_rupees(12345678.9), "₹1,23,45,678.90")

    def test_small_amounts(self):
        self.assertEqual(format_rupees(0), "₹0.00")
        self.assertEqual(format_rupees(5), "₹5.00")
        self.assertEqual(format_rupees(1234.56), "₹1,234.56")

    def test_negative_amounts(self):
        self.assertEqual(format_rupees(-113.5), "-₹113.50")
        self.assertEqual(format_rupees(-1234567.89), "-₹12,34,567.89")

    def test_none_and_rounding(self):
        self.assertEqual(format_rupees(None), "₹0.00")
        self.assertEqual(format_rupees(10.123), "₹10.12")
        self.assertEqual(format_rupees(10.129), "₹10.13")


class FormatQuantityTests(unittest.TestCase):
    def test_trailing_zeros_removed(self):
        self.assertEqual(format_quantity(17.0), "17")
        self.assertEqual(format_quantity(0.5), "0.5")
        self.assertEqual(format_quantity(21), "21")

    def test_none_is_zero(self):
        self.assertEqual(format_quantity(None), "0")


class KpiCardsTests(unittest.TestCase):
    def test_cards_from_summary(self):
        cards = kpi_cards({
            "total_transactions": 174,
            "total_holdings": 5,
            "total_invested": 123456.5,
            "total_market_value": 0,
            "total_profit_loss": 0,
        })

        self.assertEqual(cards[0], ("Total Invested", "₹1,23,456.50", "across holdings"))
        self.assertEqual(cards[1], ("Holdings", "5", "open positions"))
        self.assertEqual(cards[2], ("Transactions", "174", "recorded trades"))
        # No live prices yet: dash, not a fake zero.
        self.assertEqual(cards[3], ("Market Value", "—", "live prices coming soon"))

    def test_market_value_shown_when_priced(self):
        cards = kpi_cards({
            "total_transactions": 1,
            "total_holdings": 1,
            "total_invested": 100,
            "total_market_value": 120.5,
            "total_profit_loss": 20.5,
        })

        self.assertEqual(cards[3][1], "₹120.50")


if __name__ == "__main__":
    unittest.main()
