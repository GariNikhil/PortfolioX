"""Tests for the XIRR solver and dashboard cashflow builder."""

import unittest
from datetime import date

from calculations.xirr import xirr, xirr_cashflows


class XirrTests(unittest.TestCase):
    def test_simple_one_year_return(self):
        rate = xirr([(date(2023, 1, 1), -1000.0),
                     (date(2024, 1, 1), 1100.0)])

        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate, 0.10, places=6)

    def test_two_year_return(self):
        rate = xirr([(date(2022, 1, 1), -1000.0),
                     (date(2024, 1, 1), 1210.0)])

        self.assertAlmostEqual(rate, 0.10, places=6)

    def test_mixed_flows(self):
        # -1000, +500 after half a year, +600 at one year: the money
        # worked for different durations, so the rate sits between the
        # naive total-return bounds.
        rate = xirr([
            (date(2023, 1, 1), -1000.0),
            (date(2023, 7, 1), 500.0),
            (date(2024, 1, 1), 600.0),
        ])

        self.assertIsNotNone(rate)
        self.assertTrue(0.0 < rate < 0.20)

    def test_all_outflows_return_none(self):
        self.assertIsNone(
            xirr([(date(2023, 1, 1), -500.0), (date(2023, 6, 1), -500.0)])
        )

    def test_single_flow_returns_none(self):
        self.assertIsNone(xirr([(date(2023, 1, 1), -500.0)]))

    def test_losing_position_has_negative_rate(self):
        rate = xirr([(date(2023, 1, 1), -1000.0),
                     (date(2024, 1, 1), 900.0)])

        self.assertIsNotNone(rate)
        self.assertLess(rate, 0.0)


class XirrCashflowsTests(unittest.TestCase):
    def test_buys_negative_sells_positive_terminal_today(self):
        transactions = [
            {"trade_date": "2023-07-03", "transaction_type": "BUY",
             "net_amount": 4744.70},
            {"trade_date": "2023-07-13", "transaction_type": "SELL",
             "net_amount": 1236.00},
        ]

        flows = xirr_cashflows(transactions, 3000.0,
                               valuation_date=date(2026, 10, 28))

        self.assertEqual(flows, [
            (date(2023, 7, 3), -4744.70),
            (date(2023, 7, 13), 1236.00),
            (date(2026, 10, 28), 3000.0),
        ])

    def test_zero_market_value_adds_no_terminal_flow(self):
        flows = xirr_cashflows(
            [{"trade_date": "2023-07-03", "transaction_type": "BUY",
              "net_amount": 4744.70}],
            0,
        )

        self.assertEqual(len(flows), 1)

    def test_zero_net_amount_rows_are_skipped(self):
        flows = xirr_cashflows(
            [{"trade_date": "2023-07-03", "transaction_type": "BUY",
              "net_amount": 0}],
            0,
        )

        self.assertEqual(flows, [])


if __name__ == "__main__":
    unittest.main()
