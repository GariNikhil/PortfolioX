import unittest

from calculations.holdings import calculate_holdings


def trade(symbol, transaction_type, quantity, price, brokerage=0, taxes=0):
    return {
        "symbol": symbol,
        "isin": "ISIN-1",
        "exchange": "NSE",
        "transaction_type": transaction_type,
        "quantity": quantity,
        "price": price,
        "brokerage": brokerage,
        "taxes": taxes,
    }


class HoldingsCalculationTests(unittest.TestCase):
    def test_combines_buys_using_weighted_average_and_reduces_partial_sell(self):
        holdings = calculate_holdings([
            trade("abc", "BUY", 10, 100, brokerage=10),
            trade("ABC", "BUY", 10, 200),
            trade("ABC", "SELL", 5, 250),
        ])

        self.assertEqual(len(holdings), 1)
        holding = holdings[0]
        self.assertEqual(holding.symbol, "ABC")
        self.assertEqual(holding.quantity, 15)
        self.assertAlmostEqual(holding.invested_amount, 2257.5)
        self.assertAlmostEqual(holding.average_price, 150.5)
        self.assertEqual(holding.isin, "ISIN-1")
        self.assertEqual(holding.exchange, "NSE")

    def test_omits_fully_sold_position(self):
        holdings = calculate_holdings([
            trade("ABC", "BUY", 3, 40),
            trade("ABC", "SELL", 3, 50),
        ])
        self.assertEqual(holdings, [])

    def test_rejects_oversell(self):
        with self.assertRaisesRegex(ValueError, "only 2 are held"):
            calculate_holdings([
                trade("ABC", "BUY", 2, 10),
                trade("ABC", "SELL", 3, 10),
            ])

    def test_rejects_unsupported_transaction_type(self):
        with self.assertRaisesRegex(ValueError, "expected BUY or SELL"):
            calculate_holdings([trade("ABC", "DIVIDEND", 1, 10)])

    def test_rejects_non_finite_numbers(self):
        with self.assertRaisesRegex(ValueError, "quantity must be finite"):
            calculate_holdings([trade("ABC", "BUY", float("nan"), 10)])

    def test_accepts_database_tuple_rows(self):
        row = (
            1, "2026-01-01", "ABC", "ISIN-1", "NSE", "BUY", 2, 10,
            0, 0, 20, "2026-01-01 00:00:00",
        )
        holdings = calculate_holdings([row])
        self.assertEqual(holdings[0].quantity, 2)
        self.assertEqual(holdings[0].invested_amount, 20)

    def test_processes_newest_first_database_rows_chronologically(self):
        buy = (
            1, "2026-01-01", "ABC", "ISIN-1", "NSE", "BUY", 5, 10,
            0, 0, 50, "2026-01-01 00:00:00",
        )
        sell = (
            2, "2026-01-02", "ABC", "ISIN-1", "NSE", "SELL", 2, 12,
            0, 0, 24, "2026-01-02 00:00:00",
        )
        holdings = calculate_holdings([sell, buy])
        self.assertEqual(holdings[0].quantity, 3)
        self.assertEqual(holdings[0].invested_amount, 30)


if __name__ == "__main__":
    unittest.main()