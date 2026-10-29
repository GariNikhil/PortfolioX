"""Tests for asset allocation and financial-year summaries."""

import unittest

from calculations.allocation import (
    asset_allocation,
    financial_year_of,
    financial_year_summary,
    split_holdings_by_class,
)


def _holding(symbol, invested):
    return {"symbol": symbol, "invested_amount": invested}


class AssetAllocationTests(unittest.TestCase):
    def test_equity_and_fno_split_by_invested_amount(self):
        holdings = [
            _holding("RELIANCE", 5000.0),
            _holding("BANKNIFTY 45000 CE 2023-07-13", 2500.0),
            _holding("VEDANTA", 1000.0),
        ]

        allocation = asset_allocation(holdings)

        self.assertEqual(
            allocation,
            [("Equity", 6000.0), ("F&O", 2500.0)],
        )

    def test_zero_classes_are_omitted(self):
        self.assertEqual(asset_allocation([_holding("RELIANCE", 100.0)]),
                         [("Equity", 100.0)])
        self.assertEqual(asset_allocation([]), [])

    def test_missing_amounts_count_as_zero(self):
        self.assertEqual(
            asset_allocation([{"symbol": "RELIANCE", "invested_amount": None}]),
            [],
        )


class SplitHoldingsByClassTests(unittest.TestCase):
    def test_etf_stays_with_stocks_fund_tab_gets_mutual_funds(self):
        holdings = [
            _holding("RELIANCE", 5000.0),
            _holding("BANKNIFTY 45000 CE 2023-07-13", 2500.0),
            _holding("GROWWAMC - GROWWGOLD", 1000.0),
            _holding("PARAG PARIKH ELSS TAX SAVER FUND DIRECT GROWTH", 2000.0),
            _holding("VEDANTA", 1000.0),
        ]

        stocks, funds = split_holdings_by_class(holdings)

        # ETFs trade like stocks, so they stay in the stocks table;
        # only mutual funds land in the funds table.
        self.assertEqual(
            [row["symbol"] for row in stocks],
            ["RELIANCE", "BANKNIFTY 45000 CE 2023-07-13",
             "GROWWAMC - GROWWGOLD", "VEDANTA"],
        )
        self.assertEqual(
            [row["symbol"] for row in funds],
            ["PARAG PARIKH ELSS TAX SAVER FUND DIRECT GROWTH"],
        )

    def test_input_order_is_kept(self):
        holdings = [
            _holding("SBI ELSS TAX SAVER FUND DIRECT GROWTH", 10.0),
            _holding("PNB", 20.0),
        ]
        stocks, funds = split_holdings_by_class(holdings)
        self.assertEqual([row["symbol"] for row in stocks], ["PNB"])
        self.assertEqual(
            [row["symbol"] for row in funds],
            ["SBI ELSS TAX SAVER FUND DIRECT GROWTH"],
        )

    def test_empty_holdings(self):
        self.assertEqual(split_holdings_by_class([]), ([], []))


class FinancialYearTests(unittest.TestCase):
    def test_april_march_boundary(self):
        self.assertEqual(financial_year_of("2023-03-31"), "FY 2022-23")
        self.assertEqual(financial_year_of("2023-04-01"), "FY 2023-24")
        self.assertEqual(financial_year_of("2024-03-31"), "FY 2023-24")
        self.assertEqual(financial_year_of("2022-06-27"), "FY 2022-23")

    def test_summary_groups_and_sides(self):
        transactions = [
            {"trade_date": "2023-07-03", "transaction_type": "BUY",
             "quantity": 17, "price": 279.10},
            {"trade_date": "2023-07-13", "transaction_type": "BUY",
             "quantity": 35, "price": 16.05},
            {"trade_date": "2022-06-27", "transaction_type": "SELL",
             "quantity": 4, "price": 330.00},
        ]

        summary = financial_year_summary(transactions)

        self.assertEqual(
            summary,
            [
                ("FY 2023-24", {
                    "buy_count": 2, "sell_count": 0,
                    "buy_turnover": 17 * 279.10 + 35 * 16.05,
                    "sell_turnover": 0.0,
                }),
                ("FY 2022-23", {
                    "buy_count": 0, "sell_count": 1,
                    "buy_turnover": 0.0,
                    "sell_turnover": 4 * 330.00,
                }),
            ],
        )

    def test_empty_transactions_give_empty_summary(self):
        self.assertEqual(financial_year_summary([]), [])


if __name__ == "__main__":
    unittest.main()
