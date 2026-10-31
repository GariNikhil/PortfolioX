"""Tests for the FIFO realized P&L calculation."""

import unittest

from calculations.fifo import calculate_fifo_realized


def trade(symbol, transaction_type, quantity, price, brokerage=0, taxes=0,
          isin="ISIN-1", exchange="NSE", trade_date="2026-01-01", **extra):
    row = {
        "symbol": symbol,
        "isin": isin,
        "exchange": exchange,
        "transaction_type": transaction_type,
        "quantity": quantity,
        "price": price,
        "brokerage": brokerage,
        "taxes": taxes,
        "trade_date": trade_date,
    }
    row.update(extra)
    return row


class FifoRealizedTests(unittest.TestCase):
    def test_consumes_the_oldest_lot_first(self):
        sales = calculate_fifo_realized([
            trade("ABC", "BUY", 10, 100, trade_date="2026-01-01"),
            trade("ABC", "BUY", 10, 200, trade_date="2026-01-02"),
            trade("ABC", "SELL", 5, 250, trade_date="2026-01-03"),
        ])

        self.assertEqual(len(sales), 1)
        sale = sales[0]
        self.assertEqual(sale.quantity, 5)
        self.assertEqual(len(sale.matches), 1)
        self.assertAlmostEqual(sale.cost, 500)
        self.assertAlmostEqual(sale.proceeds, 1250)
        self.assertAlmostEqual(sale.realized_pnl, 750)

    def test_partial_sell_keeps_the_lot_unit_cost_for_later_sells(self):
        sales = calculate_fifo_realized([
            trade("ABC", "BUY", 10, 100, brokerage=10, trade_date="2026-01-01"),
            trade("ABC", "SELL", 4, 150, trade_date="2026-01-02"),
            trade("ABC", "BUY", 10, 200, trade_date="2026-01-03"),
            trade("ABC", "SELL", 8, 300, trade_date="2026-01-04"),
        ])

        first, second = sales

        # Buy charges make the lot's unit cost 101, not 100.
        self.assertAlmostEqual(first.cost, 404)
        self.assertAlmostEqual(first.realized_pnl, 196)

        # 6 shares left at 101, then 2 from the 200 lot.
        quantities = [match.quantity for match in second.matches]
        self.assertEqual(quantities, [6, 2])
        self.assertAlmostEqual(second.matches[0].cost, 606)
        self.assertAlmostEqual(second.matches[1].cost, 400)
        self.assertAlmostEqual(second.cost, 1006)
        self.assertAlmostEqual(second.realized_pnl, 1394)

    def test_sell_spanning_two_lots_splits_proceeds_by_quantity(self):
        sales = calculate_fifo_realized([
            trade("ABC", "BUY", 10, 100),
            trade("ABC", "BUY", 10, 200),
            trade("ABC", "SELL", 15, 250),
        ])

        sale = sales[0]
        self.assertEqual([match.quantity for match in sale.matches], [10, 5])
        self.assertAlmostEqual(sale.cost, 2000)
        self.assertAlmostEqual(sale.proceeds, 3750)
        self.assertAlmostEqual(sale.realized_pnl, 1750)
        self.assertAlmostEqual(
            sum(match.proceeds for match in sale.matches), sale.proceeds
        )
        self.assertAlmostEqual(
            sum(match.realized_pnl for match in sale.matches),
            sale.realized_pnl,
        )

    def test_sell_charges_reduce_proceeds(self):
        sales = calculate_fifo_realized([
            trade("ABC", "BUY", 10, 100),
            trade("ABC", "SELL", 5, 120, brokerage=10, taxes=5),
        ])

        sale = sales[0]
        self.assertAlmostEqual(sale.proceeds, 585)
        self.assertAlmostEqual(sale.cost, 500)
        self.assertAlmostEqual(sale.realized_pnl, 85)

    def test_order_of_input_rows_does_not_matter(self):
        rows = [
            trade("ABC", "BUY", 10, 100, trade_date="2026-01-01"),
            trade("ABC", "SELL", 10, 150, trade_date="2026-01-02"),
            trade("ABC", "BUY", 5, 90, trade_date="2026-01-03"),
        ]

        forward = calculate_fifo_realized(rows)
        backward = calculate_fifo_realized(list(reversed(rows)))

        self.assertEqual(len(forward), 1)
        self.assertAlmostEqual(forward[0].realized_pnl,
                               backward[0].realized_pnl)
        self.assertEqual(forward[0].cost, backward[0].cost)

    def test_uses_ids_to_break_same_day_ties(self):
        sales = calculate_fifo_realized([
            trade("ABC", "SELL", 5, 300, trade_date="2026-01-02", id=4),
            trade("ABC", "BUY", 5, 100, trade_date="2026-01-01", id=2),
            trade("ABC", "BUY", 5, 200, trade_date="2026-01-01", id=3),
        ])

        # Same trade date: the lower id is consumed first.
        self.assertAlmostEqual(sales[0].cost, 500)

    def test_matches_by_isin_before_symbol(self):
        sales = calculate_fifo_realized([
            trade("ABC", "BUY", 10, 100, isin="INE111"),
            trade("ABC", "BUY", 10, 200, isin="INE222"),
            trade("ABC", "SELL", 5, 300, isin="INE222"),
        ])

        sale = sales[0]
        self.assertAlmostEqual(sale.cost, 1000)
        self.assertAlmostEqual(sale.realized_pnl, 500)

    def test_falls_back_to_symbol_and_exchange_without_isin(self):
        sales = calculate_fifo_realized([
            trade("abc", "BUY", 10, 100, isin=None, exchange="NSE"),
            trade("ABC", "SELL", 10, 120, isin=None, exchange="NSE"),
        ])

        self.assertAlmostEqual(sales[0].cost, 1000)
        self.assertAlmostEqual(sales[0].realized_pnl, 200)

    def test_rejects_oversell(self):
        with self.assertRaisesRegex(ValueError, "only 2 are held"):
            calculate_fifo_realized([
                trade("ABC", "BUY", 2, 10),
                trade("ABC", "SELL", 3, 10),
            ])

    def test_sells_across_different_symbols_do_not_borrow_lots(self):
        with self.assertRaisesRegex(ValueError, "only 0 are held"):
            calculate_fifo_realized([
                trade("ABC", "BUY", 5, 10, isin=None),
                trade("XYZ", "SELL", 1, 10, isin=None),
            ])

    def test_rejects_unsupported_transaction_type(self):
        with self.assertRaisesRegex(ValueError, "expected BUY or SELL"):
            calculate_fifo_realized([trade("ABC", "DIVIDEND", 1, 10)])

    def test_rejects_non_finite_and_negative_values(self):
        with self.assertRaisesRegex(ValueError, "quantity must be finite"):
            calculate_fifo_realized([trade("ABC", "BUY", float("nan"), 10)])
        with self.assertRaisesRegex(ValueError, "price cannot be negative"):
            calculate_fifo_realized([trade("ABC", "BUY", 1, -10)])
        with self.assertRaisesRegex(ValueError, "quantity must be positive"):
            calculate_fifo_realized([trade("ABC", "BUY", 0, 10)])

    def test_rejects_missing_trade_date_and_symbol(self):
        with self.assertRaisesRegex(ValueError, "trade_date is required"):
            calculate_fifo_realized([trade("ABC", "BUY", 1, 10, trade_date="")])
        with self.assertRaisesRegex(ValueError, "symbol is required"):
            calculate_fifo_realized([trade(" ", "BUY", 1, 10)])

    def test_accepts_database_tuple_rows(self):
        buy = (
            1, "2026-01-01", "ABC", "ISIN-1", "NSE", "BUY", 2, 10,
            0, 0, 20, 1, 1, "2026-01-01 00:00:00",
        )
        sell = (
            2, "2026-01-02", "ABC", "ISIN-1", "NSE", "SELL", 2, 15,
            0, 0, 30, 1, 1, "2026-01-02 00:00:00",
        )

        sales = calculate_fifo_realized([sell, buy])

        self.assertEqual(len(sales), 1)
        self.assertAlmostEqual(sales[0].cost, 20)
        self.assertAlmostEqual(sales[0].realized_pnl, 10)
        self.assertEqual(sales[0].matches[0].buy_id, 1)
        self.assertEqual(sales[0].sale_id, 2)

    def test_empty_input_returns_no_sales(self):
        self.assertEqual(calculate_fifo_realized([]), [])

    def test_open_lots_without_a_sale_are_not_reported(self):
        sales = calculate_fifo_realized([trade("ABC", "BUY", 10, 100)])
        self.assertEqual(sales, [])


if __name__ == "__main__":
    unittest.main()
